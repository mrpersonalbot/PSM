import base64
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from source.sitemap import generate_sitemap, indexable_canonical_urls


class _PageMetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.canonicals = []
        self.robots = []

    def handle_starttag(self, tag, attrs):
        attrs = {key.casefold(): value or "" for key, value in attrs}
        if tag.casefold() == "link" and "canonical" in {
            token.casefold() for token in attrs.get("rel", "").split()
        }:
            self.canonicals.append(attrs.get("href", "").strip())
        if tag.casefold() == "meta" and (
            attrs.get("name", "").casefold() == "robots"
            or "bot" in attrs.get("name", "").casefold()
        ):
            self.robots.append(attrs.get("content", ""))

    def is_noindex(self):
        directives = {
            directive.casefold()
            for content in self.robots
            for segment in content.replace(";", ",").split(",")
            for directive in segment.split()
        }
        return bool({"noindex", "none"} & directives)


class SitemapEligibilityTests(unittest.TestCase):
    def _write_page(self, root, route, canonical, robots=None):
        page = root / route.strip("/") / "index.html" if route != "/" else root / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        robots_tag = f'<meta name="robots" content="{robots}">' if robots else ""
        page.write_text(
            '<!doctype html><html><head>'
            + robots_tag
            + f'<link rel="canonical" href="{canonical}"></head><body></body></html>',
            encoding="utf-8",
        )
        return page

    def test_only_self_canonical_indexable_pages_are_returned(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = "https://example.test"
            self._write_page(root, "/", base + "/")
            self._write_page(root, "/produk/keep/", base + "/produk/keep/")
            self._write_page(
                root,
                "/produk/variant/",
                base + "/produk/variant/",
                robots="noindex,follow",
            )
            self._write_page(
                root,
                "/produk/legacy/",
                base + "/produk/",
                robots="index,follow",
            )
            self._write_page(
                root,
                "/produk/none/",
                base + "/produk/none/",
                robots="NONE, FOLLOW",
            )

            self.assertEqual(
                indexable_canonical_urls(root, base),
                [base + "/", base + "/produk/keep/"],
            )

    def test_generated_xml_excludes_noindex_and_noncanonical_pages(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = "https://example.test"
            self._write_page(root, "/", base + "/")
            self._write_page(root, "/produk/keep/", base + "/produk/keep/")
            self._write_page(
                root,
                "/produk/variant/",
                base + "/produk/variant/",
                robots="noindex,follow",
            )
            self._write_page(root, "/produk/legacy/", base + "/produk/")

            generate_sitemap(root, base)
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            locations = [
                node.text
                for node in ET.parse(root / "sitemap.xml").getroot().findall("s:url/s:loc", ns)
            ]

            self.assertEqual(locations, [base + "/", base + "/produk/keep/"])
            self.assertEqual(len(locations), len(set(locations)))

    def test_full_build_keeps_product_pages_and_excludes_variant_urls(self):
        with tempfile.TemporaryDirectory() as temp:
            build_root = Path(temp)
            shutil.copy2(ROOT / "build.py", build_root / "build.py")
            os.symlink(ROOT / "source", build_root / "source", target_is_directory=True)
            base = "https://example.test"
            env = os.environ.copy()
            env["SITE_URL"] = base
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [sys.executable, str(build_root / "build.py")],
                cwd=build_root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            dist = build_root / "dist"
            products = json.loads(
                gzip.decompress(
                    base64.b64decode(
                        (ROOT / "source/payload/products.gz.b64").read_text().strip()
                    )
                )
            )
            ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            sitemap = ET.parse(dist / "sitemap.xml").getroot()
            sitemap_urls = [node.text for node in sitemap.findall("s:url/s:loc", ns)]
            self.assertEqual(len(sitemap_urls), len(set(sitemap_urls)))

            product_urls = set()
            for product in products:
                url = base + product["url"]
                product_urls.add(url)
                page = dist / "produk" / product["slug"] / "index.html"
                self.assertTrue(page.is_file(), f"missing product page: {product['slug']}")
                metadata = _PageMetadataParser()
                metadata.feed(page.read_text(encoding="utf-8"))
                self.assertEqual(metadata.canonicals, [url])
                variant = "VARIANT" in product["strategy"]
                self.assertEqual(metadata.is_noindex(), variant, product["slug"])
                self.assertEqual(url in sitemap_urls, not variant, product["slug"])

            self.assertEqual(len(product_urls), len(products))
            index_pages = sorted(dist.rglob("index.html"))
            eligible_urls = set()
            for page in index_pages:
                parts = page.relative_to(dist).parts
                route = "/" if parts == ("index.html",) else "/" + "/".join(parts[:-1]) + "/"
                metadata = _PageMetadataParser()
                metadata.feed(page.read_text(encoding="utf-8"))
                self.assertEqual(len(metadata.canonicals), 1, str(page))
                canonical = metadata.canonicals[0]
                self.assertEqual(canonical, base + route, str(page))
                if not metadata.is_noindex():
                    eligible_urls.add(canonical)

            self.assertEqual(set(sitemap_urls), eligible_urls)
            self.assertEqual(len(sitemap_urls), len(eligible_urls))
            self.assertEqual(
                (dist / "robots.txt").read_text(encoding="utf-8"),
                f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n",
            )

    def test_missing_or_ambiguous_canonical_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            page = root / "produk" / "missing" / "index.html"
            page.parent.mkdir(parents=True)
            page.write_text('<html><head></head><body></body></html>', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly one canonical"):
                indexable_canonical_urls(root, "https://example.test")

            page.write_text(
                '<html><head><link rel="canonical" href="https://example.test/produk/missing/">'
                '<link rel="canonical" href="https://example.test/other/"></head></html>',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "exactly one canonical"):
                indexable_canonical_urls(root, "https://example.test")


if __name__ == "__main__":
    unittest.main()
