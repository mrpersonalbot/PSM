import base64
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PADANG = "/toko-listrik-padang/"
DISTRIBUTOR = "/distributor-alat-listrik-sumbar/"

DUPLICATE_SLUGS = (
    "chint-m365-mcb-3-pole-63a-6ka-chint",
    "chint-m779-mcb-3-pole-63a-6ka-chint",
    "chint-m752-mcb-3-pole-25a-6ka-chint",
    "chint-m775-mcb-3-pole-25a-6ka-chint",
    "chint-m753-mcb-3-pole-40a-6ka-chint",
    "chint-m777-mcb-3-pole-40a-6ka-chint",
    "chint-m760-mcb-3-pole-32a-6ka-chint",
    "chint-m776-mcb-3-pole-32a-6ka-chint",
)


def _search(pattern: str, text: str, flags: int = 0):
    match = re.search(pattern, text, flags)
    if match is None:
        raise AssertionError(f"pattern not found: {pattern}")
    return match


def _text(html: str) -> str:
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()


class LocalSeoRegressionTests(unittest.TestCase):
    """Regression cover for the approved P1/P2 local SEO changes."""

    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory()
        build_root = Path(cls._temp.name)
        shutil.copy2(ROOT / "build.py", build_root / "build.py")
        os.symlink(ROOT / "source", build_root / "source", target_is_directory=True)
        cls.base = "https://example.test"
        env = os.environ.copy()
        env["SITE_URL"] = cls.base
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, str(build_root / "build.py")],
            cwd=build_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)
        cls.dist = build_root / "dist"
        cls.pages = sorted(cls.dist.rglob("index.html"))

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def _page(self, route: str) -> str:
        rel = route.strip("/")
        path = self.dist / rel / "index.html" if rel else self.dist / "index.html"
        return path.read_text(encoding="utf-8")

    def test_footer_links_to_local_page_without_touching_main_navigation(self):
        for page in self.pages:
            html = page.read_text(encoding="utf-8")
            footer = _search(r"<footer.*?</footer>", html, re.S)
            self.assertIsNotNone(footer, page)
            self.assertEqual(
                footer.group(0).count(f'href="{PADANG}"'),
                1,
                f"footer must link to the local landing page once: {page}",
            )
            nav = _search(r'<nav class="nav".*?</nav>', html, re.S)
            self.assertIsNotNone(nav, page)
            self.assertNotIn(
                PADANG,
                nav.group(0),
                f"local landing page must not be added to the main navigation: {page}",
            )

    def test_every_page_has_absolute_open_graph_image(self):
        asset = self.dist / "assets" / "psm-og-cover.png"
        self.assertTrue(asset.is_file())
        self.assertGreater(asset.stat().st_size, 5000)
        expected = self.base + "/assets/psm-og-cover.png"
        for page in self.pages:
            html = page.read_text(encoding="utf-8")
            images = re.findall(r'<meta property="og:image" content="([^"]+)"', html)
            self.assertEqual(images, [expected], page)
            self.assertIn('<meta property="og:image:width" content="1200">', html)
            self.assertIn('<meta property="og:image:height" content="630">', html)
            self.assertIn('<meta name="twitter:image" content="' + expected + '">', html)

    def test_local_landing_page_structure(self):
        html = self._page(PADANG)
        self.assertIn(
            "<title>Toko Listrik Padang untuk Rumah, Toko, dan Proyek | Pratama</title>",
            html,
        )
        headings = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        self.assertEqual(len(headings), 1)
        self.assertEqual(
            _text(headings[0]),
            "Toko listrik di Padang untuk rumah, toko, dan proyek.",
        )
        self.assertIn(f'<link rel="canonical" href="{self.base}{PADANG}">', html)
        categories = set(re.findall(r'href="(/kategori/[a-z0-9-]+/)"', html))
        self.assertGreaterEqual(len(categories), 9, categories)
        brands = set(re.findall(r'href="(/brand/[a-z0-9-]+/)"', html))
        self.assertGreaterEqual(len(brands), 8, brands)
        self.assertIn("Jl. Ujung Belakang Olo No. 14e", html)
        self.assertIn("Senin–Jumat 09.00–18.00", html)
        self.assertIn("HardwareStore", html)
        self.assertIn('"@id":"https://pratamasuksesmandiri.com/#business"', html)
        self.assertGreaterEqual(len(_text(_search(r"<main.*?</main>", html, re.S).group(0)).split()), 250)

    def test_category_pages_carry_contextual_local_link(self):
        category_pages = sorted(self.dist.glob("kategori/*/index.html"))
        self.assertEqual(len(category_pages), 9)
        for page in category_pages:
            html = page.read_text(encoding="utf-8")
            self.assertEqual(
                html.count(f'href="{PADANG}"'),
                2,
                f"expected footer link + contextual link on {page}",
            )
            self.assertIn("untuk kebutuhan di Padang", html)

    def test_distributor_page_targets_regional_distributor_intent(self):
        html = self._page(DISTRIBUTOR)
        title = _search(r"<title>(.*?)</title>", html, re.S).group(1)
        self.assertIn("Distributor Alat Listrik Sumatera Barat", title)
        h1 = _text(re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)[0])
        self.assertTrue(h1.lower().startswith("distributor alat listrik"), h1)
        self.assertIn(f'<link rel="canonical" href="{self.base}{DISTRIBUTOR}">', html)
        main = _text(_search(r"<main.*?</main>", html, re.S).group(0))
        self.assertLessEqual(main.lower().count("distributor"), 6, "avoid keyword stuffing")

    def test_duplicate_product_metadata_is_disambiguated(self):
        products = json.loads(
            gzip.decompress(
                base64.b64decode((ROOT / "source/payload/products.gz.b64").read_text().strip())
            )
        )
        by_slug = {p["slug"]: p for p in products}
        titles, descriptions = [], []
        for slug in DUPLICATE_SLUGS:
            html = (self.dist / "produk" / slug / "index.html").read_text(encoding="utf-8")
            title = _search(r"<title>(.*?)</title>", html, re.S).group(1)
            description = _search('<meta name="description" content="([^"]*)"', html).group(1)
            self.assertIn(by_slug[slug]["sku"], title, slug)
            self.assertIn(by_slug[slug]["sku"], description, slug)
            titles.append(title)
            descriptions.append(description)
        self.assertEqual(len(set(titles)), len(DUPLICATE_SLUGS))
        self.assertEqual(len(set(descriptions)), len(DUPLICATE_SLUGS))


if __name__ == "__main__":
    unittest.main()
