# PRATAMA Electrical Supply

Website source untuk **PRATAMA Electrical Supply**, operated by **PT Pratama Sukses Mandiri**, Padang, Sumatera Barat.

Website ini melayani dua jalur utama:
- B2C: customer toko listrik di Padang.
- B2B: akuisisi retailer melalui **PRATAMA MITRA** di seluruh Sumatera Barat.

## Brand

- Pratama Blue: `#0A498B`
- Signal Orange: `#F05A28`
- Ink: `#151719`
- Supply White: `#F7F7F4`
- Legal signature: `operated by PT Pratama Sukses Mandiri`

## Build

```bash
python3 build.py
```

Build menghasilkan folder `dist/` dengan **189 halaman HTML SEO-ready dari 160 produk launch**.

Preview lokal:

```bash
python3 -m http.server 8080 -d dist
```

Lalu buka `http://localhost:8080`.

## Deployment

Repository sudah dikonfigurasi untuk Vercel:
- Build command: `python3 build.py`
- Output directory: `dist`

Set environment variable `SITE_URL` ke domain production setelah domain final ditentukan. Default sementara adalah `https://pratamaelectric.com`.

## Data policy

Frontend tidak mengekspos HPP maupun jumlah stok internal exact. Customer diarahkan untuk mengecek stok dan harga melalui WhatsApp perusahaan.

## Existing-image review (2026-09-09)

The review of all 117 unique product-image blobs reachable in repository history
found **0 verified matches, 117 rejected candidates, and 160 unresolved catalog
products**. Candidate counts are file counts, not mutually exclusive product
counts. Historical filenames were incorrect: examples include anatomy art for a
VISALUX tube light, a CyberPower power outlet for a VISALUX telephone outlet, and
an analog clock illustration for a CHINT KG316T timer. No historical image was
safe to republish. Brand logos and WhatsApp UI assets are not product candidates.

`source/existing-image-review.json` records each blob, SHA-256, original source,
visual observation, and rejection. `source/product-images.json` connects each
current product to its reviewed candidate blobs or records no existing candidate.
All image workflow runs examined had no downloadable image artifacts. Run
34312264369 was still resolving images during this review; its unavailable output
is excluded from these counts.

Build and verify:

```sh
python3 build.py
python3 tools/audit_product_images.py
python3 -m unittest discover -s tests
```

Cards and product detail pages show an explicit verification placeholder until
an exact image is approved. A resolved mapping also requires an entry in the
review manifest's `approved` dictionary with brand, exact model (or an explicit
explanation when absent), key specs, source_page, visual_review and SHA-256.
The audit rejects missing identity evidence, changed image bytes, source changes,
missing product pages, missing card coverage, and unapproved rendered assets.
Human visual/source review must establish identity; presence of fields alone does
not establish a match. GitHub Pages runs this audit before deployment.

The legacy internet resolver is now manual-only so ordinary website edits do not
start a new image search or overwrite this existing-image review. Its results
must pass the same manual identity gate before publication.
