import base64, gzip, json, re, shutil
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).parent
AVAILABLE_BRANDS = {
    "VISALUX", "ECOKING", "PIOLINE", "HIMAWARI", "SCHNEIDER", "CHINT",
    "SIMON", "ADVANCE", "PROFAN", "DEXTA", "LUBY", "VISERO",
}
TOP_BAR_BRANDS = (
    ("Ecoking", "ecoking"), ("Pioline", "pioline"), ("Himawari", "himawari"),
    ("Schneider", "schneider"), ("Chint", "chint"), ("Simon", "simon"),
    ("Advance", "advance"), ("Profan", "profan"), ("Dexta", "dexta"),
    ("Luby", "luby"), ("Visero", "visero"), ("Visalux", "visalux"),
)
REMOVED_BRANDS = {
    "COSMIC", "HINOMARU", "NICHI", "OKACHI", "LARKIN", "WAKAMOTO", "VASINDO",
}
LOGO_EXTENSIONS = {brand.lower(): "png" for brand in AVAILABLE_BRANDS}
# GitHub Pages is the currently resolvable public site. Keep all crawl signals
# on the published origin until a verified custom domain is configured.
SEO_SITE_URL = "https://mrpersonalbot.github.io/PSM"
SEO_PAGES = {
    "/": {
        "title": "Supplier & Toko Alat Listrik Padang | Retail & Proyek | Pratama",
        "description": "Supplier alat listrik di Padang untuk toko retail, kebutuhan rumah, dan proyek. Tanya stok, harga grosir, kabel, lampu, MCB, saklar, dan kebutuhan listrik di Sumatera Barat.",
    },
    "/produk/": {
        "title": "Katalog Alat Listrik untuk Retail & Proyek | Pratama Padang",
        "description": "Cari kabel, lampu, MCB, saklar, stop kontak, dan kebutuhan listrik berdasarkan nama, SKU, brand, atau kategori. Untuk rumah, toko retail, dan proyek di Sumatera Barat.",
    },
    "/toko-listrik-padang/": {
        "title": "Toko Alat Listrik Padang untuk Rumah & Retail | Pratama",
        "description": "Toko alat listrik di Padang untuk kebutuhan rumah, teknisi, dan toko retail: lampu, kabel, MCB, saklar, dan perlengkapan instalasi. Tanya stok melalui WhatsApp.",
    },
    "/distributor-alat-listrik-sumbar/": {
        "title": "Supplier Alat Listrik Sumatera Barat untuk Toko & Proyek | Pratama",
        "description": "Supplier alat listrik di Sumatera Barat untuk toko retail dan kebutuhan proyek. Diskusikan stok, kebutuhan barang, dan pengadaan kabel, lampu, MCB, saklar, serta aksesoris instalasi.",
    },
    "/jadi-mitra-retailer/": {
        "title": "Supplier Alat Listrik untuk Toko Retail Sumatera Barat | Pratama",
        "description": "Daftar sebagai mitra toko retail alat listrik di Sumatera Barat. Hubungi Pratama untuk membahas kebutuhan produk, harga grosir, dan dukungan pengadaan.",
    },
    "/kontak/": {
        "title": "Hubungi Supplier Alat Listrik Padang | Pratama",
        "description": "Hubungi Pratama Electrical Supply di Padang untuk kebutuhan alat listrik rumah, toko retail, dan proyek di Sumatera Barat. Cek lokasi, jam operasional, stok, dan harga lewat WhatsApp.",
    },
    "/tentang-kami/": {
        "title": "Pratama, Supplier Alat Listrik di Padang & Sumatera Barat",
        "description": "Kenali Pratama Electrical Supply, supplier alat listrik di Padang yang melayani kebutuhan rumah, toko retail, dan proyek di Sumatera Barat.",
    },
}
payload = root / "source" / "payload" / "build_impl.gz.b64"
product_payload = root / "source" / "payload" / "products.gz.b64"
database_sku_counts_path = root / "source" / "database-sku-counts.json"

# Every brand rendered in the supplied logo directory and top-bar menu must have
# at least one catalog record. This keeps each visible brand page useful as
# inventory grows and prevents the menu from drifting from the catalog.
top_bar_brand_codes = {name.upper() for name, _ in TOP_BAR_BRANDS}
if top_bar_brand_codes != AVAILABLE_BRANDS:
    raise RuntimeError("Top-bar brands must match the visible brand directory")
source_products = json.loads(gzip.decompress(base64.b64decode(product_payload.read_text().strip())))
source_brands = {product["brand"] for product in source_products}
source_brand_counts = Counter(product["brand"] for product in source_products)
database_sku_snapshot = json.loads(database_sku_counts_path.read_text(encoding="utf-8"))
database_brand_sku_counts = database_sku_snapshot["counts"]
missing_database_brands = sorted(AVAILABLE_BRANDS - set(database_brand_sku_counts))
if missing_database_brands:
    raise RuntimeError(
        "Database SKU counts missing visible brand(s): " + ", ".join(missing_database_brands)
    )
missing_catalog_brands = sorted(AVAILABLE_BRANDS - source_brands)
underfilled_catalog_brands = sorted(
    brand for brand in AVAILABLE_BRANDS if source_brand_counts[brand] < 12
)
if missing_catalog_brands:
    raise RuntimeError(
        "Visible brand(s) missing catalog products: " + ", ".join(missing_catalog_brands)
    )
if underfilled_catalog_brands:
    raise RuntimeError(
        "Visible brand(s) require at least 12 catalog products: "
        + ", ".join(underfilled_catalog_brands)
    )

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
        # Keep every client-side inquiry path on the current public WhatsApp
        # number, including dynamically created product and mobile actions.
        app_text = app_text.replace("6281266600800", "6281993399888")
        # The retailer form does not collect an address field, so do not send an
        # empty field in its WhatsApp lead payload.
        app_text = app_text.replace("\\nAlamat: ${fd.get('alamat')||'-'}", "")
        app_js.write_text(app_text, encoding="utf-8")
    brand_logos = root / "source" / "brand-logos"
    if brand_logos.exists():
        shutil.rmtree(assets / "brands", ignore_errors=True)
        shutil.copytree(brand_logos, assets / "brands", dirs_exist_ok=True)
    for stale_asset in ("whatsapp.svg", "whatsapp.jpg", "whatsapp.png", "whatsapp-clean.png", "whatsapp-floating.jpg", "whatsapp-floating-final.jpg", "whatsapp-floating-transparent.png", "whatsapp-floating-logo-only.png"):
        (assets / stale_asset).unlink(missing_ok=True)
    top_bar_brand_menu = (
        '<div class="nav-drop"><button>Brand <span>⌄</span></button><div class="drop-menu">'
        + "".join(f'<a href="/brand/{slug}/">{name}</a>' for name, slug in TOP_BAR_BRANDS)
        + '<a class="all-link" href="/produk/?view=brands">Semua brand →</a></div></div>'
    )
    for html_path in dist.rglob("*.html"): 
        text = html_path.read_text(encoding="utf-8")
        relative_parts = html_path.relative_to(dist).parts
        route = "/" if relative_parts == ("index.html",) else "/" + "/".join(relative_parts[:-1]) + "/"

        # Give core audience pages search-focused titles/descriptions, while all
        # generated pages receive an absolute canonical and social preview data.
        seo = SEO_PAGES.get(route)
        if seo:
            text = re.sub(r"<title>.*?</title>", f"<title>{escape(seo['title'])}</title>", text, count=1, flags=re.S)
            text = re.sub(
                r'<meta name="description" content="[^"]*">',
                f'<meta name="description" content="{escape(seo["description"], quote=True)}">',
                text,
                count=1,
            )
        title_match = re.search(r"<title>(.*?)</title>", text, flags=re.S)
        description_match = re.search(r'<meta name="description" content="([^"]*)">', text)
        page_title = title_match.group(1) if title_match else "Pratama Electrical Supply"
        page_description = description_match.group(1) if description_match else "Supplier alat listrik di Padang dan Sumatera Barat."
        canonical_url = SEO_SITE_URL + route
        text = re.sub(
            r'<link rel="canonical" href="[^"]*">',
            f'<link rel="canonical" href="{canonical_url}">',
            text,
            count=1,
        )
        social_meta = (
            f'<meta property="og:locale" content="id_ID"><meta property="og:site_name" content="Pratama Electrical Supply">'
            f'<meta property="og:type" content="website"><meta property="og:title" content="{page_title}">'
            f'<meta property="og:description" content="{page_description}"><meta property="og:url" content="{canonical_url}">'
            f'<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{page_title}">'
            f'<meta name="twitter:description" content="{page_description}">'
        )
        breadcrumb_schema = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Beranda", "item": SEO_SITE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": re.sub(r"<[^>]+>", "", page_title), "item": canonical_url},
            ],
        }
        structured_data = json.dumps(breadcrumb_schema, ensure_ascii=False, separators=(",", ":"))
        text = text.replace("</head>", social_meta + f'<script type="application/ld+json">{structured_data}</script></head>', 1)
        if "/assets/human-touch.css" not in text:
            text = text.replace(
                '<link rel="stylesheet" href="/assets/styles.css">',
                '<link rel="stylesheet" href="/assets/styles.css"><link rel="stylesheet" href="/assets/human-touch.css">',
            )
        # Cache-bust the override stylesheet after matching the finder button to site-wide CTA sizing.
        text = text.replace('/assets/human-touch.css', '/assets/human-touch.css?v=homepage-product-search-site-cta-size-1')
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

        # Render the requested catalog brands in the top-bar Brand menu, each
        # linked to its dedicated brand route. This replaces the payload's
        # shorter default list consistently on every generated page.
        text = re.sub(
            r'<div class="nav-drop"><button>Brand\s*<span>⌄</span></button><div class="drop-menu">.*?</div></div>',
            top_bar_brand_menu,
            text,
            count=1,
            flags=re.S,
        )

        # Keep the search button in the header, but remove the separate
        # product dropdown from the top bar; catalog routes remain available.
        text = re.sub(
            r'<div class="nav-drop"><button>Produk\s*<span>⌄</span></button><div class="drop-menu">.*?</div></div>',
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
        # Remove the persistent floating WhatsApp logo site-wide. Product-card
        # "Tanya stok" links and other inquiry CTAs stay available.
        text = re.sub(r'<a class="wa-float"[^>]*>.*?</a>', "", text, flags=re.S)
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

        # Every brand page uses the same catalog-availability statement rather
        # than exposing its warehouse snapshot or its number of published cards.
        relative_parts = html_path.relative_to(dist).parts
        if len(relative_parts) == 3 and relative_parts[0] == "brand" and relative_parts[2] == "index.html":
            brand_slug = relative_parts[1]
            brand_name = next((name for name, slug in TOP_BAR_BRANDS if slug == brand_slug), None)
            if brand_name:
                text = re.sub(
                    r'<h2>\d+ produk pilihan\.</h2>',
                    '<h2>Lebih dari 100 SKU terdaftar di katalog.</h2>',
                    text,
                    count=1,
                )
                inquiry_section = (
                    '<section class="section soft-section brand-more-products"><div class="container">'
                    '<div class="split-card"><div><span class="eyebrow">BUTUH BANTUAN?</span>'
                    '<h2>Masih mencari produk lainnya?</h2>'
                    '<p>Langsung tanyakan kepada tim kami untuk cek produk, stok, dan harga terbaru.</p>'
                    '</div><div><a class="btn btn-primary" href="/kontak/">Tanyakan Produk</a></div>'
                    '</div></div></section>'
                )
                text = text.replace('</main>', inquiry_section + '</main>', 1)
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

        # Restore the homepage finder as a real catalog search. It keeps the
        # familiar panel but now submits the entered product/SKU/brand query to
        # the catalog through a clearly labelled "Cari Produk" button.
        text = re.sub(
            r'<form class="hero-search" action="/produk/" method="get">.*?</form>',
            '<form class="hero-search" action="/produk/" method="get"><input name="q" placeholder="Nama produk, SKU atau brand..." aria-label="Cari produk"><button type="submit">Cari Produk</button></form>',
            text,
            count=1,
            flags=re.S,
        )
        # The primary homepage CTA remains a direct WhatsApp inquiry.
        whatsapp_product = 'https://wa.me/6281993399888?text=Halo%20Pratama%2C%20saya%20ingin%20menanyakan%20produk%20listrik.'
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

        # A concise, visible local-service section supports the search intent of
        # retail stores, direct buyers, and project procurement without hiding
        # keywords solely in metadata.
        seo_supplier_section = (
            '<section class="section soft-section seo-supplier"><div class="container">'
            '<div class="section-head"><div><span class="eyebrow">SUPPLIER ALAT LISTRIK SUMATERA BARAT</span>'
            '<h2>Untuk toko retail, kebutuhan rumah, dan proyek.</h2></div></div>'
            '<div class="seo-supplier-grid">'
            '<article><h3>Untuk toko retail</h3><p>Butuh partner pengadaan alat listrik untuk toko? Diskusikan kebutuhan barang dan ketersediaan produk bersama tim Pratama.</p><a href="/jadi-mitra-retailer/">Lihat informasi mitra →</a></article>'
            '<article><h3>Untuk kebutuhan langsung</h3><p>Cari lampu, kabel, saklar, MCB, stop kontak, atau perlengkapan instalasi untuk rumah dan usaha? Mulai dari katalog atau tanyakan stok.</p><a href="/toko-listrik-padang/">Kunjungi toko listrik Padang →</a></article>'
            '<article><h3>Untuk kebutuhan proyek</h3><p>Siapkan daftar kebutuhan listrik proyek Anda, lalu hubungi kami untuk membahas produk dan pengadaan di Padang serta Sumatera Barat.</p><a href="/distributor-alat-listrik-sumbar/">Hubungi supplier proyek →</a></article>'
            '</div></div></section>'
        )
        category_section_marker = '<section class="section"><div class="container"><div class="section-head"><div><span class="eyebrow">KATEGORI PRODUK</span>'
        if 'class="section soft-section seo-supplier"' not in text:
            text = text.replace(category_section_marker, seo_supplier_section + category_section_marker, 1)

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

# Publish crawlable discovery files from the same generated route set.
sitemap_urls = []
for page in sorted(dist.rglob("index.html")):
    parts = page.relative_to(dist).parts
    route = "/" if parts == ("index.html",) else "/" + "/".join(parts[:-1]) + "/"
    sitemap_urls.append(SEO_SITE_URL + route)
sitemap = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "\n".join(f"  <url><loc>{escape(url)}</loc></url>" for url in sitemap_urls)
    + "\n</urlset>\n"
)
(dist / "sitemap.xml").write_text(sitemap, encoding="utf-8")
(dist / "robots.txt").write_text(
    "User-agent: *\nAllow: /\n\nSitemap: " + SEO_SITE_URL + "/sitemap.xml\n",
    encoding="utf-8",
)

# Persisted product images are collected by GitHub Actions and stored in
# source/product-images. Apply them after the static generator finishes so the
# same image set is used by GitHub Pages and future production deployments.
apply_images = root / "tools" / "apply_product_images.py"
if apply_images.exists():
    namespace = {"__name__": "__main__", "__file__": str(apply_images)}
    exec(compile(apply_images.read_bytes(), str(apply_images), "exec"), namespace)
