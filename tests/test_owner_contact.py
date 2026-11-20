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
OWNER_LOCAL = "0811666027"
OWNER_INTERNATIONAL = "62811666027"
OWNER_E164 = "+62811666027"
BUSINESS_ID = "https://pratamasuksesmandiri.com/#business"
MAPS_URL = "https://share.google/WOR9AeR91epH32LOo"
OBSOLETE_OWNER_VALUES = ("6281993399888", "081993399888")
ADMIN_VALUES = ("6281266600800", "0812-6660-0800")


class OwnerContactRegressionTests(unittest.TestCase):
    """Pin the website Owner number and keep the Admin Maps identity separate."""

    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory()
        build_root = Path(cls._temp.name)
        shutil.copy2(ROOT / "build.py", build_root / "build.py")
        os.symlink(ROOT / "source", build_root / "source", target_is_directory=True)
        env = os.environ.copy()
        env["SITE_URL"] = "https://example.test"
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
        cls.pages = sorted(cls.dist.rglob("*.html"))
        cls.app_js = (cls.dist / "assets" / "app.js").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def test_owner_number_is_in_visible_header_and_every_business_entity(self):
        business_entities = []
        for page in self.pages:
            html = page.read_text(encoding="utf-8")
            self.assertIn(
                f"WhatsApp {OWNER_LOCAL}",
                html,
                f"visible Owner number missing from {page.relative_to(self.dist)}",
            )
            for match in re.finditer(
                r'<script type="application/ld\+json">(.*?)</script>', html, re.S
            ):
                data = json.loads(match.group(1))
                stack = [data]
                while stack:
                    node = stack.pop()
                    if isinstance(node, list):
                        stack.extend(node)
                        continue
                    if not isinstance(node, dict):
                        continue
                    types = node.get("@type", [])
                    if isinstance(types, str):
                        types = [types]
                    normalized = {
                        str(value).rsplit("/", 1)[-1].casefold() for value in types
                    }
                    if normalized & {"hardwarestore"}:
                        business_entities.append((page, node))
                    stack.extend(node.values())
        self.assertEqual(len(business_entities), 2, "expected home + Padang business nodes")
        for page, entity in business_entities:
            self.assertEqual(entity.get("@id"), BUSINESS_ID, page)
            self.assertEqual(entity.get("telephone"), OWNER_E164, page)
            self.assertEqual(entity.get("hasMap"), MAPS_URL, page)
            self.assertEqual(entity.get("legalName"), "CV Pratama Sukses Mandiri", page)
            self.assertEqual(entity.get("name"), "Pratama Sukses Mandiri", page)

    def test_every_whatsapp_destination_uses_the_owner_number(self):
        for page in self.pages:
            html = page.read_text(encoding="utf-8")
            for href in re.findall(r'href="(https://wa\.me/[^"]+)"', html):
                self.assertEqual(
                    href.split("?", 1)[0],
                    f"https://wa.me/{OWNER_INTERNATIONAL}",
                    f"unexpected WhatsApp destination on {page.relative_to(self.dist)}",
                )
        for href in re.findall(r"https://wa\.me/[0-9]+", self.app_js):
            self.assertEqual(href, f"https://wa.me/{OWNER_INTERNATIONAL}")

    def test_obsolete_owner_and_admin_numbers_are_not_website_contacts(self):
        combined = "\n".join(page.read_text(encoding="utf-8") for page in self.pages)
        combined += "\n" + self.app_js
        for value in OBSOLETE_OWNER_VALUES:
            self.assertNotIn(value, combined, f"obsolete Owner number still published: {value}")
        for value in ADMIN_VALUES:
            self.assertNotIn(
                value,
                combined,
                f"Admin/Maps number must not be published as a website contact: {value}",
            )

    def test_source_payloads_no_longer_carry_the_previous_owner_number(self):
        for relative in (
            "source/payload/home.gz.b64",
            "source/payload/build_impl.gz.b64",
            "source/payload/app.gz.b64",
        ):
            raw = gzip.decompress(
                base64.b64decode((ROOT / relative).read_text().strip())
            ).decode("utf-8")
            self.assertIn(OWNER_INTERNATIONAL, raw, relative)
            for value in OBSOLETE_OWNER_VALUES + ADMIN_VALUES:
                self.assertNotIn(value, raw, f"{relative} still contains {value}")


if __name__ == "__main__":
    unittest.main()
