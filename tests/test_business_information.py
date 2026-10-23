import ast
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from source.business_information import BUSINESS_INFO, apply_business_information, has_legacy_psm_legal_entity_reference


class BusinessInformationTests(unittest.TestCase):
    def test_business_telephone_is_full_e164_and_matches_website_whatsapp(self):
        self.assertIsNotNone(re.fullmatch(r"\+[1-9]\d{7,14}", BUSINESS_INFO["telephone"]))
        build_tree = ast.parse((ROOT / "build.py").read_text(encoding="utf-8"))
        assignment = next(
            node
            for node in build_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "WHATSAPP_NUMBER"
                for target in node.targets
            )
        )
        self.assertEqual(BUSINESS_INFO["telephone"], "+" + ast.literal_eval(assignment.value))

    def test_verified_business_identity_is_shared_and_product_jsonld_is_untouched(self):
        homepage_entity = {
            "@context": "https://schema.org",
            "@type": "HardwareStore",
            "name": "Pratama Sukses Mandiri",
            "alternateName": "Pratama",
            "legalName": "CV Pratama Sukses Mandiri",
            "telephone": "+628****9888",
            "sameAs": [
                "https://www.instagram.com/psm_padang/",
                "https://www.tiktok.com/@psm.padang",
                "https://maps.google.com/?cid=unconfirmed",
            ],
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "Jl. Ujung Belakang Olo No. 14e",
                "addressLocality": "Padang",
                "addressRegion": "Sumatera Barat",
                "addressCountry": "ID",
            },
        }
        local_entity = {
            "@context": "https://schema.org",
            "@type": "ElectricalSupplyStore",
            "name": "Pratama Sukses Mandiri",
            "legalName": "PT Pratama Sukses Mandiri",
            "telephone": "+628****9888",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "Jl. Ujung Belakang Olo No. 14e",
                "addressLocality": "Padang",
                "addressRegion": "Sumatera Barat",
                "addressCountry": "ID",
            },
        }
        product = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Fixture product",
            "seller": {
                "@type": "Organization",
                "name": "PT Pratama Sukses Mandiri",
                "legalName": "PT Pratama Sukses Mandiri",
            },
        }

        def transform(node):
            source = (
                '<script type="application/ld+json">'
                + json.dumps(node, ensure_ascii=False)
                + '</script>'
            )
            updated = apply_business_information(source)
            return json.loads(updated.split(">", 1)[1].split("</script>", 1)[0])

        homepage = transform(homepage_entity)
        local_store = transform(local_entity)
        preserved_product = transform(product)
        expected_identity = {
            "@id": "https://pratamasuksesmandiri.com/#business",
            "@type": "HardwareStore",
            "name": "Pratama Sukses Mandiri",
            "legalName": "CV Pratama Sukses Mandiri",
            "url": "https://pratamasuksesmandiri.com/",
            "logo": "https://pratamasuksesmandiri.com/assets/psm-header-transparent.png",
            "telephone": "+6281993399888",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "Jl. Ujung Belakang Olo No. 14e",
                "addressLocality": "Padang",
                "addressRegion": "Sumatera Barat",
                "addressCountry": "ID",
            },
        }
        for key, value in expected_identity.items():
            with self.subTest(entity="homepage", key=key):
                self.assertEqual(homepage.get(key), value)
            with self.subTest(entity="local store", key=key):
                self.assertEqual(local_store.get(key), value)
        self.assertNotIn("alternateName", homepage)
        self.assertNotIn("sameAs", homepage)
        self.assertNotIn("alternateName", local_store)
        self.assertNotIn("sameAs", local_store)
        self.assertEqual(preserved_product, product)

    def test_address_rewrite_is_bounded_and_idempotent(self):
        source = (
            "Jl. Ujung Belakang Olo No.14, Padang; "
            "Jl. Ujung Belakang Olo No. 14, Padang; "
            "Jl. Ujung Belakang Olo No. 14e, Padang"
        )
        expected = (
            "Jl. Ujung Belakang Olo No. 14e, Padang; "
            "Jl. Ujung Belakang Olo No. 14e, Padang; "
            "Jl. Ujung Belakang Olo No. 14e, Padang"
        )
        first_pass = apply_business_information(source)
        self.assertEqual(first_pass, expected)
        self.assertEqual(apply_business_information(first_pass), expected)
        self.assertNotIn("14ee", first_pass)

    def test_legacy_entity_scanner_detects_plain_encoded_and_unicode_variants(self):
        variants = (
            "PT Pratama Sukses Mandiri",
            "PT. PRATAMA SUKSES MANDIRI",
            "P.T. Pratama Sukses Mandiri",
            "PT&#46; Pratama&#32;Sukses&#32;Mandiri",
            "PT%2E%20PRATAMA%20SUKSES%20MANDIRI",
            r"PT\u002e\u0020Pratama\u0020Sukses\u0020Mandiri",
            "ＰＴ． ＰＲＡＴＡＭＡ ＳＵＫＳＥＳ ＭＡＮＤＩＲＩ",
        )
        for value in variants:
            with self.subTest(value=value):
                self.assertTrue(has_legacy_psm_legal_entity_reference(value))
        self.assertFalse(has_legacy_psm_legal_entity_reference("CV Pratama Sukses Mandiri"))

    def test_visible_saturday_hours_update_without_changing_other_days(self):
        source = (
            "<span>Sabtu</span><b>08.00–17.00</b>"
            "<b>Sabtu:</b> 08:00–17:00"
            "Sabtu 08.00–17.00"
            "Sab 08.00–17.00"
            "Senin–Jumat 09.00–18.00; Minggu tutup"
        )
        updated = apply_business_information(source)
        self.assertEqual(updated.count("09.00–17.00"), 4)
        self.assertNotIn("08.00–17.00", updated)
        self.assertNotIn("08:00–17:00", updated)
        self.assertIn("Senin–Jumat 09.00–18.00; Minggu tutup", updated)

    def test_store_jsonld_updates_address_hours_and_map_preserving_identity(self):
        source = (
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"HardwareStore",'
            '"name":"Pratama Electrical Supply","legalName":"PT Pratama Sukses Mandiri",'
            '"telephone":"+628****9888",'
            '"address":{"@type":"PostalAddress","streetAddress":"Jl. Ujung Belakang Olo No.14",'
            '"addressLocality":"Padang","addressRegion":"Sumatera Barat","addressCountry":"ID"},'
            '"openingHoursSpecification":['
            '{"@type":"OpeningHoursSpecification","dayOfWeek":["Monday","Tuesday","Wednesday","Thursday","Friday"],"opens":"09:00","closes":"18:00"},'
            '{"@type":"OpeningHoursSpecification","dayOfWeek":"Saturday","opens":"08:00","closes":"17:00"},'
            '{"@type":"OpeningHoursSpecification","dayOfWeek":"Sunday","opens":"09:00","closes":"12:00"}],'
            '"sameAs":["https://www.instagram.com/psm_padang/"]}'
            '</script>'
        )
        updated = apply_business_information(source)
        jsonld = updated.split(">", 1)[1].split("</script>", 1)[0]
        entity = json.loads(jsonld)

        self.assertEqual(entity["address"]["streetAddress"], BUSINESS_INFO["street_address"])
        self.assertEqual(entity["hasMap"], BUSINESS_INFO["maps_url"])
        self.assertEqual(entity["legalName"], BUSINESS_INFO["legal_name"])
        self.assertEqual(entity["@id"], BUSINESS_INFO["business_id"])
        self.assertEqual(entity["@type"], "HardwareStore")
        self.assertEqual(entity["name"], BUSINESS_INFO["public_name"])
        self.assertEqual(entity["url"], BUSINESS_INFO["url"])
        self.assertEqual(entity["logo"], BUSINESS_INFO["logo_url"])
        self.assertEqual(entity["telephone"], BUSINESS_INFO["telephone"])
        self.assertNotIn("sameAs", entity)
        self.assertNotIn("alternateName", entity)
        self.assertEqual(
            entity["openingHoursSpecification"][0],
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "opens": "09:00",
                "closes": "18:00",
            },
        )
        saturday = [
            spec for spec in entity["openingHoursSpecification"]
            if spec.get("dayOfWeek") == "Saturday"
        ]
        self.assertEqual(len(saturday), 1)
        self.assertEqual((saturday[0]["opens"], saturday[0]["closes"]), ("09:00", "17:00"))
        self.assertFalse(
            any("Sunday" in spec.get("dayOfWeek", []) if isinstance(spec.get("dayOfWeek"), list)
                else spec.get("dayOfWeek") == "Sunday"
                for spec in entity["openingHoursSpecification"])
        )

    def test_missing_store_hours_are_added_for_local_landing_schema(self):
        source = (
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"ElectricalSupplyStore",'
            '"name":"Pratama Electrical Supply","legalName":"PT Pratama Sukses Mandiri",'
            '"telephone":"+628****9888",'
            '"address":{"@type":"PostalAddress","streetAddress":"Jl. Ujung Belakang Olo No.14"}}'
            '</script>'
        )
        updated = apply_business_information(source)
        entity = json.loads(updated.split(">", 1)[1].split("</script>", 1)[0])
        specs = entity["openingHoursSpecification"]
        self.assertEqual(len(specs), 2)
        self.assertEqual(specs[0]["dayOfWeek"], ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        self.assertEqual((specs[0]["opens"], specs[0]["closes"]), ("09:00", "18:00"))
        self.assertEqual(specs[1]["dayOfWeek"], "Saturday")
        self.assertEqual((specs[1]["opens"], specs[1]["closes"]), ("09:00", "17:00"))
        self.assertEqual(entity["legalName"], BUSINESS_INFO["legal_name"])
        self.assertEqual(entity["@type"], "HardwareStore")
        self.assertEqual(entity["@id"], BUSINESS_INFO["business_id"])

    def test_organization_is_canonicalized_without_touching_product_sellers(self):
        source = (
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@graph":['
            '{"@type":"Organization","name":"PT. PRATAMA SUKSES MANDIRI",'
            '"legalName":"PT Pratama Sukses Mandiri"},'
            '{"@type":"Product","name":"Example product",'
            '"seller":{"@type":"Organization","name":"PT PRATAMA SUKSES MANDIRI",'
            '"legalName":"PT. Pratama Sukses Mandiri"}},'
            '{"@type":"Product","name":"Another product",'
            '"seller":"PT Pratama Sukses Mandiri"},'
            '{"@type":"Product","name":"PT Pratama Sukses Mandiri",'
            '"brand":{"@type":"Brand","name":"PT Pratama Sukses Mandiri"}}]}'
            '</script>'
        )
        updated = apply_business_information(source)
        graph = json.loads(updated.split(">", 1)[1].split("</script>", 1)[0])["@graph"]

        self.assertEqual(BUSINESS_INFO["legal_name"], "CV Pratama Sukses Mandiri")
        self.assertEqual(graph[0]["@type"], "HardwareStore")
        self.assertEqual(graph[0]["@id"], BUSINESS_INFO["business_id"])
        self.assertEqual(graph[0]["name"], BUSINESS_INFO["public_name"])
        self.assertEqual(graph[0]["legalName"], BUSINESS_INFO["legal_name"])
        self.assertEqual(graph[1]["name"], "Example product")
        self.assertEqual(graph[1]["seller"]["name"], "PT PRATAMA SUKSES MANDIRI")
        self.assertEqual(graph[1]["seller"]["legalName"], "PT. Pratama Sukses Mandiri")
        self.assertEqual(graph[2]["seller"], "PT Pratama Sukses Mandiri")
        self.assertEqual(graph[3]["name"], "PT Pratama Sukses Mandiri")
        self.assertEqual(graph[3]["brand"]["name"], "PT Pratama Sukses Mandiri")

    def test_product_identity_correction_preserves_catalog_fields_and_whatsapp(self):
        source = (
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Product",'
            '"name":"Kabel NYM 2 x 2.5 mm",'
            '"sku":"SKU-PSM-001","category":"Kabel & Kawat",'
            '"url":"https://pratamasuksesmandiri.com/produk/kabel-nym-2x25/",'
            '"image":"https://pratamasuksesmandiri.com/assets/products/item.jpg",'
            '"description":"Kabel NYM 2 x 2.5 mm",'
            '"brand":{"@type":"Brand","name":"PROFAN"},'
            '"offers":{"@type":"Offer",'
            '"url":"https://pratamasuksesmandiri.com/produk/kabel-nym-2x25/",'
            '"price":"12345","priceCurrency":"IDR",'
            '"availability":"https://schema.org/InStock"},'
            '"seller":{"@type":"Organization","name":"PT Pratama Sukses Mandiri"}}'
            '</script>'
            '<link rel="canonical" href="https://pratamasuksesmandiri.com/produk/kabel-nym-2x25/">'
            '<a href="https://wa.me/6281993399888?text=SKU%20PSM-001">Tanya stok</a>'
        )
        updated = apply_business_information(source)
        entity = json.loads(updated.split(">", 1)[1].split("</script>", 1)[0])

        self.assertEqual(entity["seller"]["name"], "PT Pratama Sukses Mandiri")
        self.assertEqual(entity["name"], "Kabel NYM 2 x 2.5 mm")
        self.assertEqual(entity["sku"], "SKU-PSM-001")
        self.assertEqual(entity["category"], "Kabel & Kawat")
        self.assertEqual(entity["url"], "https://pratamasuksesmandiri.com/produk/kabel-nym-2x25/")
        self.assertEqual(entity["image"], "https://pratamasuksesmandiri.com/assets/products/item.jpg")
        self.assertEqual(entity["description"], "Kabel NYM 2 x 2.5 mm")
        self.assertEqual(entity["brand"], {"@type": "Brand", "name": "PROFAN"})
        self.assertEqual(
            entity["offers"],
            {
                "@type": "Offer",
                "url": "https://pratamasuksesmandiri.com/produk/kabel-nym-2x25/",
                "price": "12345",
                "priceCurrency": "IDR",
                "availability": "https://schema.org/InStock",
            },
        )
        self.assertIn(
            '<link rel="canonical" href="https://pratamasuksesmandiri.com/produk/kabel-nym-2x25/">',
            updated,
        )
        self.assertIn(
            '<a href="https://wa.me/6281993399888?text=SKU%20PSM-001">Tanya stok</a>',
            updated,
        )

    def test_only_psm_store_map_links_change(self):
        source = (
            '<a href="https://www.google.com/maps/search/?api=1&amp;query=Pratama+Sukses+Mandiri+Padang">Store</a>'
            "<a href='https://www.google.com/maps/search/?api=1&query=Jl+Ujung+Belakang+Olo'>Store</a>"
            '<a href="https://share.google/nobfOiBD7ggfAbN7W">Old Listing</a>'
            '<a href="https://www.google.com/maps/search/?api=1&amp;query=Other+Place">Other</a>'
        )
        updated = apply_business_information(source)
        self.assertEqual(updated.count(BUSINESS_INFO["maps_url"]), 3)
        self.assertIn("query=Other+Place", updated)
        self.assertNotIn("maps/search/?api=1&amp;query=Pratama+Sukses+Mandiri+Padang", updated)
        self.assertNotIn("https://share.google/nobfOiBD7ggfAbN7W", updated)


if __name__ == "__main__":
    unittest.main()
