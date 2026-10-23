"""Focused regression tests for the PSM public brand and committed logo assets."""
from __future__ import annotations

import json
import re
import struct
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BRAND = "Pratama Sukses Mandiri"
LEGAL = "CV Pratama Sukses Mandiri"
OLD_BRAND = re.compile(r"Pratama Electrical Supply", re.IGNORECASE)


def png_info(path: Path) -> tuple[int, int, int, bytes]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"Not a PNG: {path}")
    pos = 8
    width = height = color_type = None
    compressed = []
    while pos < len(data):
        size = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + size]
        pos += 12 + size
        if kind == b"IHDR":
            width, height, depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if depth != 8 or compression != 0 or filtering != 0 or interlace != 0:
                raise AssertionError(f"Unexpected PNG encoding: {path}")
        elif kind == b"IDAT":
            compressed.append(payload)
        elif kind == b"IEND":
            break
    if width is None or height is None or color_type != 6:
        raise AssertionError(f"Logo must be 8-bit RGBA PNG: {path}")
    return width, height, color_type, zlib.decompress(b"".join(compressed))


def jsonld_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from jsonld_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from jsonld_objects(child)


class BrandIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DIST / "index.html").exists():
            raise RuntimeError("Run python3 build.py before the brand-identity tests")
        cls.home = (DIST / "index.html").read_text(encoding="utf-8")

    def test_canonical_assets_are_true_rgba_and_compatibility_aliases_match(self):
        assets = DIST / "assets"
        pairs = [
            ("psm-header-transparent.png", "pratama-brand-wordmark-home-transparent.png", 3538, 1297, 769, 231),
            ("psm-footer-transparent.png", "pratama-brand-footer-transparent.png", 1656, 537, 326, 156),
        ]
        for canonical, alias, expected_width, expected_height, core_x, core_y in pairs:
            canonical_path = assets / canonical
            alias_path = assets / alias
            self.assertTrue(canonical_path.is_file())
            self.assertTrue(alias_path.is_file())
            self.assertEqual(canonical_path.read_bytes(), alias_path.read_bytes())
            width, height, color_type, raw = png_info(canonical_path)
            self.assertEqual((width, height, color_type), (expected_width, expected_height, 6))
            stride = width * 4
            scanline_stride = stride + 1
            self.assertTrue(
                any(0 < raw[y * scanline_stride + 1 + x * 4 + 3] < 255 for y in range(height) for x in range(width)),
                f"Antialiased transparency must be retained: {canonical}",
            )
            self.assertEqual(raw[0], 0, "PNG scanline filter should be directly verifiable")
            self.assertEqual(raw[1 + 3], 0, "Outer canvas corner must be transparent")
            self.assertEqual(raw[1 + (height - 1) * (stride + 1) + width * 4 - 1], 0)
            core_alpha = core_y * (stride + 1) + 1 + core_x * 4 + 3
            self.assertGreater(raw[core_alpha], 240, "Logo core artwork must remain opaque")
            if canonical == "psm-footer-transparent.png":
                self.assertTrue(
                    any(
                        raw[(y * scanline_stride) + 1 + (x * 4)] >= 240
                        and raw[(y * scanline_stride) + 1 + (x * 4) + 1] >= 240
                        and raw[(y * scanline_stride) + 1 + (x * 4) + 2] >= 240
                        and raw[(y * scanline_stride) + 1 + (x * 4) + 3] > 240
                        for y in range(height // 2, height)
                        for x in range(width)
                    ),
                    "Footer white tagline artwork must remain visible and opaque",
                )

    def test_header_logo_path_home_link_accessible_name_and_geometry(self):
        pattern = (
            r'<a class="wordmark wordmark-final" href="/" aria-label="Pratama Sukses Mandiri home">'
            r'<img src="/assets/pratama-brand-wordmark-home-transparent\.png" '
            r'alt="Pratama Sukses Mandiri logo" width="260" height="95"></a>'
        )
        self.assertRegex(self.home, pattern)

    def test_footer_logo_path_alt_and_legal_entity(self):
        expected = (
            '<img class="footer-logo" src="/assets/pratama-brand-footer-transparent.png" '
            'alt="Pratama Sukses Mandiri logo" width="260" height="85">'
            f'<p class="footer-legal">{LEGAL}</p>'
        )
        self.assertIn(expected, self.home)

    def test_public_pages_use_new_brand_and_no_retired_brand(self):
        pages = list(DIST.rglob("*.html"))
        self.assertTrue(pages, "The build should generate HTML pages")
        for page in pages:
            html = page.read_text(encoding="utf-8")
            self.assertIsNone(OLD_BRAND.search(html), f"Retired public brand remains in {page.relative_to(DIST)}")
            self.assertIn('content="Pratama Sukses Mandiri"', html, f"Missing og:site_name in {page.relative_to(DIST)}")

    def test_structured_data_uses_brand_name_and_preserves_cv_legal_name(self):
        page = (DIST / "toko-listrik-padang" / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r'<script\b[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S | re.I)
        values = [json.loads(script) for script in scripts]
        businesses = [
            item for value in values for item in jsonld_objects(value)
            if "electricalsupplystore" in str(item.get("@type", "")).casefold()
        ]
        self.assertTrue(businesses)
        self.assertEqual(businesses[0].get("name"), BRAND)
        self.assertEqual(businesses[0].get("legalName"), LEGAL)

    def test_social_brand_is_updated_without_changing_page_intent(self):
        contact = (DIST / "kontak" / "index.html").read_text(encoding="utf-8")
        self.assertIn('property="og:site_name" content="Pratama Sukses Mandiri"', contact)
        self.assertIn("Hubungi Pratama Sukses Mandiri di Padang", contact)
        self.assertIn('href="https://pratamasuksesmandiri.com/kontak/"', contact)


if __name__ == "__main__":
    unittest.main()
