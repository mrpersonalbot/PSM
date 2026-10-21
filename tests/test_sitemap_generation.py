import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from source.sitemap import generate_sitemap, indexable_canonical_urls


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
