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
from urllib.parse import parse_qs, urlsplit

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


class _CommercialPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.description = []
        self.headings = []
        self.links = []
        self.jsonld = []
        self.form_names = []
        self._in_title = False
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        attrs = {key.casefold(): value or "" for key, value in attrs}
        tag = tag.casefold()
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.headings.append(True)
        elif tag == "meta" and attrs.get("name", "").casefold() == "description":
            self.description.append(attrs.get("content", ""))
        elif tag == "a":
            self.links.append(attrs.get("href", ""))
        elif tag == "script" and attrs.get("type", "").casefold() == "application/ld+json":
            self._in_jsonld = True
            self.jsonld.append([])
        if tag in {"input", "select", "textarea"} and attrs.get("name"):
            self.form_names.append(attrs["name"])

    def handle_data(self, data):
        if self._in_title:
            self.title.append(data)
        if self._in_jsonld:
            self.jsonld[-1].append(data)

    def handle_endtag(self, tag):
        if tag.casefold() == "title":
            self._in_title = False
        elif tag.casefold() == "script":
            self._in_jsonld = False


COMMERCIAL_PAGES = {
    "/toko-listrik-padang/": {
        "title": "Toko Listrik Padang untuk Kebutuhan Rumah | Pratama",
        "description": "Temukan kategori alat listrik untuk kebutuhan rumah di Padang. Jelajahi katalog, tanyakan harga atau ketersediaan lewat WhatsApp, atau lihat alamat dan jam operasional toko.",
        "whatsapp_hint": "kebutuhan rumah di Padang",
    },
    "/distributor-alat-listrik-sumbar/": {
        "title": "Pengadaan Alat Listrik Sumatera Barat untuk Toko dan Proyek | Pratama",
        "description": "Informasi pengadaan alat listrik untuk toko retail dan kebutuhan proyek di Sumatera Barat. Siapkan kategori, nama atau SKU, jumlah, dan lokasi kebutuhan; tanyakan ketersediaan serta penawaran melalui WhatsApp.",
        "whatsapp_hint": "pengadaan alat listrik",
    },
    "/jadi-mitra-retailer/": {
        "title": "Kemitraan Retailer Alat Listrik Sumatera Barat | Pratama Mitra",
        "description": "Untuk pemilik atau calon pemilik toko listrik di Sumatera Barat. Sampaikan lokasi toko, status persiapan, dan kategori produk yang diminati melalui formulir yang dilanjutkan ke WhatsApp.",
        "whatsapp_hint": "kemitraan retailer",
    },
}


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
            variant_routes = {
                product["url"] for product in products if "VARIANT" in product["strategy"]
            }
            self.assertEqual(len(variant_routes), 94)
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

            for route, expected in COMMERCIAL_PAGES.items():
                page = dist / route.strip("/") / "index.html"
                self.assertTrue(page.is_file(), f"missing commercial landing page: {route}")
                html = page.read_text(encoding="utf-8")
                metadata = _PageMetadataParser()
                metadata.feed(html)
                parsed = _CommercialPageParser()
                parsed.feed(html)
                title = "".join(parsed.title)
                self.assertEqual(title, expected["title"], route)
                self.assertEqual(parsed.description, [expected["description"]], route)
                self.assertEqual(metadata.canonicals, [base + route], route)
                self.assertEqual(metadata.robots, ["index,follow"], route)
                self.assertEqual(len(parsed.headings), 1, route)
                self.assertGreaterEqual(len(parsed.jsonld), 1, route)
                schemas = [json.loads("".join(block)) for block in parsed.jsonld]
                breadcrumbs = [item for item in schemas if item.get("@type") == "BreadcrumbList"]
                self.assertEqual(len(breadcrumbs), 1, route)
                self.assertEqual(
                    breadcrumbs[0]["itemListElement"][-1]["item"],
                    base + route,
                    route,
                )
                self.assertEqual(
                    breadcrumbs[0]["itemListElement"][-1]["name"],
                    title,
                    route,
                )

                hrefs = parsed.links
                self.assertIn("https://share.google/WOR9AeR91epH32LOo", hrefs, route)
                for href in hrefs:
                    if href.startswith("https://wa.me/"):
                        self.assertEqual(urlsplit(href).netloc, "wa.me", route)
                        self.assertEqual(urlsplit(href).path, "/6281993399888", route)
                messages = [
                    parse_qs(urlsplit(href).query).get("text", [""])[0].casefold()
                    for href in hrefs
                    if href.startswith("https://wa.me/6281993399888")
                ]
                self.assertTrue(
                    any(expected["whatsapp_hint"].casefold() in message for message in messages),
                    f"missing qualified WhatsApp message for {route}",
                )

                for href in hrefs:
                    if href.startswith("/kategori/") or href == "/produk/" or href in {
                        "/distributor-alat-listrik-sumbar/",
                        "/jadi-mitra-retailer/",
                    }:
                        target = dist / href.strip("/") / "index.html"
                        self.assertTrue(target.is_file(), f"broken internal link {route} -> {href}")

                for unsupported_claim in (
                    "reseller resmi",
                    "distributor resmi",
                    "2.000+ sku",
                    "7 sales",
                    "stok luas",
                    "harga kompetitif",
                    "harga bertingkat",
                    "harga khusus berdasarkan produk",
                    "program reward",
                    "termin",
                    "pengiriman ke berbagai kota",
                    "layanan distribusi ke berbagai wilayah",
                ):
                    self.assertNotIn(unsupported_claim, html.casefold(), route)
                self.assertIn("CV Pratama Sukses Mandiri", html, route)
                self.assertIn("?v=pratama-commercial-pages-2", html, route)

            partner_html = (dist / "jadi-mitra-retailer" / "index.html").read_text(encoding="utf-8")
            partner = _CommercialPageParser()
            partner.feed(partner_html)
            self.assertTrue(
                {"nama", "toko", "whatsapp", "kota", "produk", "status"}.issubset(
                    set(partner.form_names)
                )
            )
            self.assertIn('name="produk" required', partner_html)
            self.assertIn('name="status" required', partner_html)
            self.assertIn("Lanjutkan ke WhatsApp", partner_html)

            # Product route metadata must retain the existing stylesheet token;
            # only the three authorized landing pages get the new cache-buster.
            for route in variant_routes:
                page = dist / "produk" / route.strip("/").split("/")[-1] / "index.html"
                self.assertTrue(page.is_file(), f"missing variant page: {route}")
                html = page.read_text(encoding="utf-8")
                self.assertNotIn("pratama-commercial-pages-2", html, route)

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
