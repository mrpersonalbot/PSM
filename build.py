import base64, gzip, shutil
from pathlib import Path

root = Path(__file__).parent
payload = root / "source" / "payload" / "build_impl.gz.b64"
code = gzip.decompress(base64.b64decode(payload.read_text().strip()))
exec(compile(code, "build_impl.py", "exec"))

# Human-touch layer is kept outside the generated payload so the identity can
# evolve without editing 189 generated pages by hand.
dist = root / "dist"
assets = dist / "assets"
human_css = root / "source" / "human-touch.css"
if dist.exists() and human_css.exists():
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(human_css, assets / "human-touch.css")
    brand_logos = root / "source" / "brand-logos"
    if brand_logos.exists():
        shutil.copytree(brand_logos, assets / "brands", dirs_exist_ok=True)

    for html_path in dist.rglob("*.html"):
        text = html_path.read_text(encoding="utf-8")
        if "/assets/human-touch.css" not in text:
            text = text.replace(
                '<link rel="stylesheet" href="/assets/styles.css">',
                '<link rel="stylesheet" href="/assets/styles.css"><link rel="stylesheet" href="/assets/human-touch.css">',
            )
        html_path.write_text(text, encoding="utf-8")

    # Homepage copy: more like a conversation at a long-established store,
    # less like labels inside a software dashboard.
    home = dist / "index.html"
    if home.exists():
        text = home.read_text(encoding="utf-8")
        replacements = {
            "PRATAMA / 001 · PADANG, SUMATERA BARAT": "Dari Padang · tumbuh bersama pelanggan selama lebih dari 20 tahun",
            "Lebih dari 1.000 SKU untuk rumah, toko dan bisnis. Belanja retail di Padang atau bergabung sebagai retailer Pratama Mitra di Sumatera Barat.": "Dari lampu sampai MCB, kami sudah lebih dari dua dekade membantu pelanggan menemukan barang yang mereka butuhkan. Belanja untuk rumah, atau ngobrol dengan tim kami kalau Anda punya toko.",
            "PRODUCT FINDER": "BANTU CARI PRODUK",
            "PADANG · SUMBAR": "TANYA TIM KAMI",
            "Apa yang sedang Anda cari?": "Cari barangnya. Kalau ragu, tanya kami.",
            "<span>ECOKING</span><b>Lighting</b>": "<span>SEBUT NAMA / SKU</span><b>Kami bantu cari</b>",
            "<span>VISALUX</span><b>Electrical</b>": "<span>TANYA STOK</span><b>Langsung WhatsApp</b>",
            "<span>MULTI-BRAND</span><b>1.000+ SKU</b>": "<span>BELANJA UNTUK TOKO?</span><b>Tanya harga grosir</b>",
            "Temukan kebutuhan listrik Anda.": "Mulai dari barang yang paling sering dicari.",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        home.write_text(text, encoding="utf-8")

# Persisted product images are collected by GitHub Actions and stored in
# source/product-images. Apply them after the static generator finishes so the
# same image set is used by GitHub Pages and future production deployments.
apply_images = root / "tools" / "apply_product_images.py"
if apply_images.exists():
    namespace = {"__name__": "__main__", "__file__": str(apply_images)}
    exec(compile(apply_images.read_bytes(), str(apply_images), "exec"), namespace)
