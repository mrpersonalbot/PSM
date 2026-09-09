"""Fail closed on unreviewed images; audit catalog, sources, and rendered images."""
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verified_mapping(root=ROOT):
    products = json.loads(gzip.decompress(base64.b64decode((root/'source/payload/products.gz.b64').read_bytes())))
    catalog = {p['slug']: p for p in products}
    mapping = json.loads((root/'source/product-images.json').read_text())
    review = json.loads((root/'source/existing-image-review.json').read_text())
    assert len(catalog) == 160 and set(mapping) == set(catalog), 'Catalog/mapping mismatch'
    approved = review['approved']
    resolved = {}
    for slug, entry in mapping.items():
        if entry.get('status') != 'resolved':
            continue
        evidence = approved.get(slug)
        assert evidence, f'{slug}: manual identity review required'
        assert all(evidence.get(k) for k in ('brand', 'model', 'specs', 'source_page', 'sha256', 'visual_review')), f'{slug}: incomplete evidence'
        assert evidence['brand'] == catalog[slug]['brand'], f'{slug}: wrong brand'
        path = (root/'source'/entry['file']).resolve()
        assert path.is_relative_to((root/'source/product-images').resolve()) and path.is_file(), f'{slug}: invalid image path'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence['sha256'], f'{slug}: image changed after review'
        assert evidence['source_page'] == entry.get('source_page'), f'{slug}: source changed'
        resolved[slug] = entry
    assert set(approved) == set(resolved), 'Approved/mapping mismatch'
    return catalog, resolved


def audit(root=ROOT):
    catalog, resolved = verified_mapping(root)
    dist = root/'dist'
    cards = set()
    images = 0
    for page in dist.rglob('*.html'):
        text = page.read_text()
        for slug in re.findall(r'<a class="product-visual" href="(?:/PSM)?/produk/([^/]+)/"', text):
            cards.add(slug)
        for slug in re.findall(r'<img[^>]+src="(?:/PSM)?/assets/products/([^"/]+)\.webp"', text):
            assert slug in resolved, f'{page}: unapproved image {slug}'
            images += 1
        for src in re.findall(r'<img[^>]+src="([^"]+)"', text):
            if src.startswith('/'):
                target = src.removeprefix('/PSM').lstrip('/')
                assert (dist/target).is_file(), f'{page}: missing {src}'
    assert cards == set(catalog), 'Missing catalog cards'
    for slug in catalog:
        page = dist/'produk'/slug/'index.html'
        text = page.read_text()
        if slug in resolved:
            assert f'/assets/products/{slug}.webp' in text, f'{slug}: missing detail image'
        else:
            assert 'product-image-placeholder detail' in text, f'{slug}: missing fallback'
    assets = {p.stem for p in (dist/'assets/products').glob('*.webp')}
    assert assets == set(resolved), 'Unexpected or missing product assets'
    result = dict(products=len(catalog), matched=len(resolved), unresolved=len(catalog)-len(resolved), product_image_references=images, html_pages=len(list(dist.rglob('*.html'))))
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    audit()
