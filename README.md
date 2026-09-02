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
