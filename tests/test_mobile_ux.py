import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


class MobileUXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (ROOT / "source" / "human-touch.css").read_text(encoding="utf-8")

    def test_only_the_named_internal_routes_receive_page_scopes(self):
        for route, expected in (
            ("toko-listrik-padang", 'data-page="padang-store"'),
            ("kontak", 'data-page="contact"'),
            ("distributor-alat-listrik-sumbar", 'data-page="b2b-procurement"'),
            ("jadi-mitra-retailer", 'data-page="retailer-partnership"'),
        ):
            html = (DIST / route / "index.html").read_text(encoding="utf-8")
            start = html.find("<body")
            end = html.find(">", start)
            body_tag = html[start : end + 1] if start >= 0 and end >= 0 else ""
            self.assertTrue(expected in body_tag, f"{route}: route scope missing from {body_tag!r}")
            cache_key = (
                "pratama-commercial-pages-2"
                if route in {"toko-listrik-padang", "distributor-alat-listrik-sumbar", "jadi-mitra-retailer"}
                else "pratama-mobile-ux-1"
            )
            self.assertIn(
                f"/assets/human-touch.css?v={cache_key}",
                html,
                f"{route}: stylesheet cache key missing",
            )

    def test_home_and_padang_mobile_heroes_allow_content_to_reflow(self):
        for selector in (
            "body.homepage .hero-grid",
            ".homepage .hero-copy",
            ".homepage .hero-copy h1",
            'body[data-page="padang-store"] .page-hero h1',
            ".homepage .hero-actions",
        ):
            self.assertTrue(selector in self.css, f"Missing scoped selector: {selector}")
        for declaration in (
            "grid-template-columns:minmax(0, 1fr)",
            "overflow-wrap:anywhere",
            "min-width:0",
        ):
            self.assertTrue(declaration in self.css, f"Missing responsive declaration: {declaration}")

    def test_padang_hero_actions_contrast_with_blue_hero(self):
        for rule in (
            'body[data-page="padang-store"] .page-hero .hero-actions .btn-primary',
            'body[data-page="padang-store"] .page-hero .hero-actions .btn-secondary',
            'body[data-page="padang-store"] .page-hero .hero-actions .btn:focus-visible',
            ".b2b-hero .hero-actions .btn:focus-visible{outline:3px solid #fff;outline-offset:3px}",
            ".b2b-hero .btn-signal{background:#c1481f;color:#fff;border-color:#c1481f}",
            ".b2b-hero .btn-signal:hover{background:#a83c1c;border-color:#a83c1c}",
            "background:#c1481f",
            "border:1px solid rgba(255,255,255,.48)",
            "outline:3px solid #fff",
        ):
            self.assertIn(rule, self.css)

    def test_contact_dock_is_in_flow_and_reserves_only_its_bottom_safe_area(self):
        body_selector = 'body[data-page="contact"]'
        body_start = self.css.find(body_selector)
        body_open = self.css.find("{", body_start)
        body_close = self.css.find("}", body_open)
        body_rule = self.css[body_open + 1 : body_close] if body_start >= 0 and body_open >= 0 and body_close >= 0 else ""
        self.assertIn("padding-bottom:0", body_rule.replace(" ", ""))

        dock_selector = body_selector + " .mobile-action-dock"
        dock_start = self.css.find(dock_selector)
        dock_open = self.css.find("{", dock_start)
        dock_close = self.css.find("}", dock_open)
        dock_rule = self.css[dock_open + 1 : dock_close] if dock_start >= 0 and dock_open >= 0 and dock_close >= 0 else ""
        for declaration in (
            "position:static",
            "bottom:auto",
            "margin:12px10pxcalc(10px+env(safe-area-inset-bottom,0px))",
        ):
            self.assertIn(declaration, dock_rule.replace(" ", ""), f"Contact dock missing {declaration}")

        self.assertNotIn("@media (max-width: 980px) and (max-height: 420px)", self.css)

    def test_commercial_mobile_action_docks_stay_in_flow_and_clear_content(self):
        for scope in ("padang-store", "b2b-procurement", "retailer-partnership"):
            body_selector = f'body[data-page="{scope}"]'
            self.assertIn(body_selector + "{padding-bottom:0}", self.css.replace(" ", ""))
            dock_selector = body_selector + " .mobile-action-dock"
            dock_start = self.css.find(dock_selector)
            dock_open = self.css.find("{", dock_start)
            dock_close = self.css.find("}", dock_open)
            dock_rule = self.css[dock_open + 1 : dock_close] if dock_start >= 0 and dock_open >= 0 and dock_close >= 0 else ""
            for declaration in (
                "position:static",
                "bottom:auto",
                "margin:12px10pxcalc(10px+env(safe-area-inset-bottom,0px))",
            ):
                self.assertIn(declaration, dock_rule.replace(" ", ""), f"{scope} dock missing {declaration}")

    def test_mobile_conversion_destinations_remain_unchanged(self):
        home = (DIST / "index.html").read_text(encoding="utf-8")
        padang = (DIST / "toko-listrik-padang" / "index.html").read_text(encoding="utf-8")
        contact = (DIST / "kontak" / "index.html").read_text(encoding="utf-8")
        app = (DIST / "assets" / "app.js").read_text(encoding="utf-8")

        self.assertIn('>Tanya Produk</a>', home)
        self.assertIn('href="https://wa.me/6281993399888?text=Halo%20Pratama%2C%20saya%20ingin%20menanyakan%20produk%20listrik."', home)
        self.assertIn('href="/jadi-mitra-retailer/"', home)
        self.assertIn('href="/produk/"', padang)
        self.assertIn('https://share.google/WOR9AeR91epH32LOo', padang)
        self.assertIn('https://share.google/WOR9AeR91epH32LOo', contact)
        self.assertIn('https://wa.me/6281993399888', contact)
        self.assertIn('dock.innerHTML=\'<a href="/produk/">Cari Produk</a>', app)
        self.assertIn('<a class="wa-float" href="https://wa.me/6281993399888', contact)


if __name__ == "__main__":
    unittest.main()
