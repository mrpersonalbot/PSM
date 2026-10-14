import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from source.business_information import BUSINESS_INFO, apply_business_information


class BusinessInformationTests(unittest.TestCase):
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
        self.assertEqual(entity["legalName"], "PT Pratama Sukses Mandiri")
        self.assertEqual(entity["telephone"], "+628****9888")
        self.assertEqual(entity["sameAs"], ["https://www.instagram.com/psm_padang/"])
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
        self.assertEqual(entity["legalName"], "PT Pratama Sukses Mandiri")

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
