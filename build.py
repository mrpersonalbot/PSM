import base64, gzip, re, shutil
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).parent
AVAILABLE_BRANDS = {
    "VISALUX", "ECOKING", "PIOLINE", "HIMAWARI", "SCHNEIDER", "CHINT",
    "SIMON", "ADVANCE", "PROFAN", "DEXTA", "LUBY", "VISERO",
}
REMOVED_BRANDS = {
    "COSMIC", "HINOMARU", "NICHI", "OKACHI", "LARKIN", "WAKAMOTO", "VASINDO",
}
LOGO_EXTENSIONS = {brand.lower(): "png" for brand in AVAILABLE_BRANDS}
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
    app_js = assets / "app.js"
    if app_js.exists():
        app_text = app_js.read_text(encoding="utf-8")
        app_text = app_text.replace(
            "const q=search.value.trim().toLowerCase(), b=",
            "const q=search.value.trim().toLowerCase().replace(/\\s+electric$/,'').trim(), b=",
        )
        app_js.write_text(app_text, encoding="utf-8")
    brand_logos = root / "source" / "brand-logos"
    if brand_logos.exists():
        shutil.rmtree(assets / "brands", ignore_errors=True)
        shutil.copytree(brand_logos, assets / "brands", dirs_exist_ok=True)
    whatsapp_logo = root / "source" / "assets" / "whatsapp-floating-logo-only.png"
    if whatsapp_logo.exists():
        (assets / "whatsapp-floating-logo-only.png").unlink(missing_ok=True)
        shutil.copy2(whatsapp_logo, assets / "whatsapp-floating-logo-only.png")
    for stale_asset in ("whatsapp.svg", "whatsapp.jpg", "whatsapp.png", "whatsapp-clean.png", "whatsapp-floating.jpg", "whatsapp-floating-final.jpg", "whatsapp-floating-transparent.png"):
        (assets / stale_asset).unlink(missing_ok=True)
    for html_path in dist.rglob("*.html"): 
        text = html_path.read_text(encoding="utf-8")
        if "/assets/human-touch.css" not in text:
            text = text.replace(
                '<link rel="stylesheet" href="/assets/styles.css">',
                '<link rel="stylesheet" href="/assets/styles.css"><link rel="stylesheet" href="/assets/human-touch.css">',
            )
        # Cache-bust the override stylesheet so the current catalog presentation
        # is fetched instead of a browser's previously cached product-card CSS.
        text = text.replace('/assets/human-touch.css', '/assets/human-touch.css?v=product-list-1')
        # Brand-logo links should search the catalog with the electrical context
        # included, e.g. "VISALUX electric", rather than only applying a
        # strict brand filter.
        text = re.sub(
            r'href="/produk/\?brand=([^&"]+)"',
            lambda m: f'href="/produk/?q={m.group(1)}%20electric"',
            text,
        )
        # Remove brand tiles and filter options when no visual asset was supplied.
        for brand in REMOVED_BRANDS:
            text = re.sub(
                rf'<a class="brand-logo-tile"[^>]*?(?:brand={brand}|q={brand}%20electric)[^>]*>.*?</a>',
                "",
                text,
                flags=re.S | re.I,
            )
            text = text.replace(f'<option value="{brand}">{brand}</option>', "")
        # Update the public contact details consistently in generated pages.
        text = text.replace('6281266600800', '6281993399888')
        text = text.replace('0812-6660-0800', '081993399888')
        text = text.replace('https://www.instagram.com/psm_padan/', 'https://www.instagram.com/psm_padang/')
        text = text.replace('@psm_padan', '@psm_padang')

        # Remove the product search icon from the top navigation.
        text = re.sub(
            r'<a class="icon-btn" href="/produk/" aria-label="Cari produk">.*?</a>',
            "",
            text,
            count=1,
            flags=re.S,
        )

        # Brand links in the top navigation/brand strip should open the
        # dedicated brand page, not a filtered product-results page.
        text = re.sub(
            r'href="/produk/\?q=([^&"]+)%20electric"',
            lambda m: f'href="/brand/{m.group(1).lower()}/"',
            text,
        )
        # Keep the catalog's displayed inventory claim current.
        text = text.replace('1.000+', '2.000+')
        text = text.replace('kami tanya', 'tanya kami')

        # The supplied visual assets are PNGs, replacing the former text SVGs.
        for slug, ext in LOGO_EXTENSIONS.items():
            text = text.replace(f'/assets/brands/{slug}.svg', f'/assets/brands/{slug}.{ext}')
        # Use the supplied artwork as the only visible floating WhatsApp element.
        text = re.sub(
            r'(<a class="wa-float"[^>]*>).*?(</a>)',
            r'\1<img src="/assets/whatsapp-floating-logo-only.png" alt="Hubungi WhatsApp" width="58" height="58">\2',
            text,
            flags=re.S,
        )
        text = re.sub(
            r'(<a class="quick-wa"[^>]*>)WA(</a>)',
            r'\1Tanya stok\2',
            text,
        )
        text = text.replace(
            "7 salesman mendukung kebutuhan toko dan kunjungan langsung.",
            "Sales support mendukung kebutuhan toko dan kunjungan langsung.",
        )

        # Temporarily present every catalog as a text-only list. Product data,
        # detail routes, and WhatsApp actions remain available; only the visual
        # photo blocks are removed from catalog/category/brand/detail pages.
        text = re.sub(
            r'<a class="product-visual"[^>]*>.*?</a>',
            "",
            text,
            flags=re.S,
        )
        text = re.sub(
            r'<div class="product-detail-visual">.*?</div>',
            "",
            text,
            flags=re.S,
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
            "Dukungan 7 salesman untuk kebutuhan toko.": "Dukungan salesman untuk kebutuhan toko.",
            "<span><strong>7</strong> salesman</span>": "",
            "20+Tahun dipercaya": "20+ Tahun dipercaya",
            "1.000+SKU aktif": "1.000+ SKU aktif",
            "4,9★Google rating": "4,9 ★ Google rating",
            "PadangStore & warehouse": "Padang Store & warehouse",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        # The homepage brand strip is intentionally presentation-only: one
        # continuously moving line of logos, with no separate brand labels.
        text = re.sub(
            r'<div class="brand-wall-copy">.*?</div><div class="brand-logo-row">',
            '<div class="brand-logo-row">',
            text,
            count=1,
            flags=re.S,
        )
        row_match = re.search(r'(<div class="brand-logo-row">)(.*?)(</div>)', text, flags=re.S)
        if row_match and 'brand-logo-track' not in text:
            logo_items = row_match.group(2)
            row = (
                '<div class="brand-logo-row"><div class="brand-logo-track">'
                + logo_items + logo_items
                + '</div></div>'
            )
            text = text[:row_match.start()] + row + text[row_match.end():]

        # Temporarily hide the featured product catalog from the landing page
        # while keeping the category section and standalone catalog routes.
        text = re.sub(
            r'<section class="section">(?:(?!<section class="section">).)*?<div class="product-grid">.*?</section>',
            "",
            text,
            count=1,
            flags=re.S,
        )

        # Remove the product dropdown from the top navigation while keeping
        # product categories and catalog routes available from the page.
        text = re.sub(
            r'<div class="nav-drop"><button>Produk\s*<span>⌄</span></button><div class="drop-menu">.*?</div></div>',
            "",
            text,
            count=1,
            flags=re.S,
        )

        # The homepage product finder should start a WhatsApp conversation,
        # rather than sending visitors to the catalog search route.
        whatsapp_product = 'https://wa.me/6281993399888?text=Halo%20Pratama%2C%20saya%20ingin%20menanyakan%20produk%20listrik.'
        text = text.replace(
            'Cari barangnya. Kalau ragu, kami tanya.',
            'Cari barangnya. Kalau ragu, tanya kami.',
        )
        text = re.sub(
            r'<form class="hero-search" action="/produk/" method="get">.*?</form>',
            f'<a class="btn btn-primary hero-whatsapp" href="{whatsapp_product}">Tanya Produk</a>',
            text,
            count=1,
            flags=re.S,
        )
        text = text.replace(
            '<a class="btn btn-primary" href="/produk/">Cari Produk</a>',
            f'<a class="btn btn-primary" href="{whatsapp_product}">Tanya Produk</a>',
        )

        # Category cards now ask via WhatsApp with the selected category in
        # the prefilled message instead of opening the catalog route.
        category_messages = {
            "lampu-pencahayaan": "Lampu & Pencahayaan",
            "saklar-stop-kontak": "Saklar & Stop Kontak",
            "kabel-listrik": "Kabel & Kawat",
            "proteksi-panel-listrik": "Proteksi Listrik",
            "aksesoris-instalasi-listrik": "Aksesoris Instalasi",
            "extension-steker-adaptor": "Extension & Steker",
            "kipas-ventilasi": "Kipas & Ventilasi",
            "kontrol-otomasi": "Kontrol & Otomasi",
        }
        def category_card(match):
            slug, body = match.group(1), match.group(2)
            category = category_messages.get(slug)
            if not category:
                return match.group(0)
            href = 'https://wa.me/6281993399888?text=' + quote(
                f"Halo Pratama, saya ingin menanyakan kategori {category}."
            )
            body = body.replace("Lihat produk →", "Tanya Produk →")
            return f'<a class="category-card" href="{href}">{body}</a>'
        text = re.sub(
            r'<a class="category-card" href="/kategori/([^/]+)/">(.*?)</a>',
            category_card,
            text,
            flags=re.S,
        )

        # Use the supplied Google Maps share link for the landing-page button
        # and the footer location link.
        maps_url = 'https://share.google/nobfOiBD7ggfAbN7W'
        text = text.replace(
            'https://www.google.com/maps/search/?api=1&query=Pratama+Sukses+Mandiri+Padang',
            maps_url,
        )
        text = text.replace('>Buka Maps<', '>Google Maps<')
        text = text.replace('>Buka Google Maps →<', '>Google Maps →<')

        # Place the floating brand marquee directly above the two audience cards.
        brand_match = re.search(r'<section class="section brand-wall">.*?</section>', text, flags=re.S)
        audience_match = re.search(r'<section class="section section-tight"><div class="container audience-grid">.*?</section>', text, flags=re.S)
        if brand_match and audience_match and brand_match.start() > audience_match.start():
            brand_section = brand_match.group(0)
            audience_section = audience_match.group(0)
            text = (
                text[:audience_match.start()]
                + brand_section
                + audience_section
                + text[audience_match.end():brand_match.start()]
                + text[brand_match.end():]
            )
        home.write_text(text, encoding="utf-8")

# Persisted product images are collected by GitHub Actions and stored in
# source/product-images. Apply them after the static generator finishes so the
# same image set is used by GitHub Pages and future production deployments.
apply_images = root / "tools" / "apply_product_images.py"
if apply_images.exists():
    namespace = {"__name__": "__main__", "__file__": str(apply_images)}
    exec(compile(apply_images.read_bytes(), str(apply_images), "exec"), namespace)
