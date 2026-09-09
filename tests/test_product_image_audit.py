import importlib.util
import json
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit', ROOT/'tools/audit_product_images.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class ImageAuditTests(unittest.TestCase):
    def test_current_site(self):
        self.assertEqual(audit.audit()['products'], 160)

    def test_unreviewed_image_cannot_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT/'source', root/'source')
            path = root/'source/product-images.json'
            mapping = json.loads(path.read_text())
            unresolved = next(slug for slug, entry in mapping.items() if entry.get('status') != 'resolved')
            mapping[unresolved]['status'] = 'resolved'
            path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(AssertionError, 'manual identity review required'):
                audit.verified_mapping(root)

    def test_missing_product_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT/'source', root/'source')
            path = root/'source/product-images.json'
            mapping = json.loads(path.read_text())
            mapping.pop(next(iter(mapping)))
            path.write_text(json.dumps(mapping))
            with self.assertRaisesRegex(AssertionError, 'Catalog/mapping mismatch'):
                audit.verified_mapping(root)

if __name__ == '__main__':
    unittest.main()
