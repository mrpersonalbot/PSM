import base64
import gzip
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote

from source.business_information import (
    BUSINESS_INFO,
    apply_business_information,
    has_legacy_psm_legal_entity_reference,
)
from source.sitemap import generate_sitemap

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
# Canonical URLs, structured data, and sitemap entries use the production origin.
SEO_SITE_URL = os.environ.get("SITE_URL", "https://pratamasuksesmandiri.com").rstrip("/")
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
        "title": "Toko Listrik Padang untuk Kebutuhan Rumah | Pratama",
        "description": "Temukan kategori alat listrik untuk kebutuhan rumah di Padang. Jelajahi katalog, tanyakan harga atau ketersediaan lewat WhatsApp, atau lihat alamat dan jam operasional toko.",
    },
    "/distributor-alat-listrik-sumbar/": {
        "title": "Pengadaan Alat Listrik Sumatera Barat untuk Toko dan Proyek | Pratama",
        "description": "Informasi pengadaan alat listrik untuk toko retail dan kebutuhan proyek di Sumatera Barat. Siapkan kategori, nama atau SKU, jumlah, dan lokasi kebutuhan; tanyakan ketersediaan serta penawaran melalui WhatsApp.",
    },
    "/jadi-mitra-retailer/": {
        "title": "Kemitraan Retailer Alat Listrik Sumatera Barat | Pratama Mitra",
        "description": "Untuk pemilik atau calon pemilik toko listrik di Sumatera Barat. Sampaikan lokasi toko, status persiapan, dan kategori produk yang diminati melalui formulir yang dilanjutkan ke WhatsApp.",
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

WHATSAPP_NUMBER = "6281993399888"


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {label} marker, found {count}")
    return text.replace(old, new, 1)


def replace_commercial_block(text, pattern, replacement, route, label):
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Expected one {label} block on {route}, found {count}")
    return updated


def commercial_whatsapp_url(message):
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={quote(message, safe='')}"


def apply_commercial_landing_content(text, route):
    """Give the three approved commercial routes distinct, evidence-bounded journeys."""
    if route not in {
        "/toko-listrik-padang/",
        "/distributor-alat-listrik-sumbar/",
        "/jadi-mitra-retailer/",
    }:
        return text

    # Remove unverified authorization and service-area assertions from these
    # routes without changing shared pages outside the approved scope.
    text = replace_once(
        text,
        "Distributor resmi EcoKing &amp; Visalux · Sumatera Barat",
        "Pratama Electrical Supply · Padang, Sumatera Barat",
        f"{route} top strip",
    )
    text = replace_once(
        text,
        "Distributor dan toko alat listrik di Padang dengan layanan distribusi ke berbagai wilayah Sumatera Barat.",
        "Pratama Electrical Supply di Padang, operated by CV Pratama Sukses Mandiri.",
        f"{route} footer summary",
    )

    category_links = (
        '<nav aria-label="Kategori produk"><ul class="commercial-link-grid">'
        '<li><a href="/kategori/lampu-pencahayaan/">Lampu &amp; Pencahayaan</a></li>'
        '<li><a href="/kategori/kabel-listrik/">Kabel &amp; Kawat</a></li>'
        '<li><a href="/kategori/saklar-stop-kontak/">Saklar &amp; Stop Kontak</a></li>'
        '<li><a href="/kategori/proteksi-panel-listrik/">Proteksi Listrik</a></li>'
        '</ul></nav>'
    )

    if route == "/toko-listrik-padang/":
        local_wa = commercial_whatsapp_url(
            "Halo Pratama, saya ingin bertanya tentang produk untuk kebutuhan rumah di Padang. "
            "Produk atau SKU: ____. Jumlah: ____. Mohon informasi harga dan ketersediaan."
        )
        text = replace_once(text, "<h1>Toko alat listrik lengkap di Padang.</h1>", "<h1>Alat listrik untuk kebutuhan rumah di Padang.</h1>", f"{route} H1")
        text = replace_once(
            text,
            "<p>Lebih dari 20 tahun melayani kebutuhan rumah, toko dan bisnis dengan 2.000+ SKU aktif serta berbagai brand terpercaya.</p>",
            "<p>Cari kategori atau produk di katalog. Untuk harga dan ketersediaan saat ini, tanyakan melalui WhatsApp atau kunjungi toko di Padang.</p>",
            f"{route} introduction",
        )
        text = replace_once(text, '<a class="btn btn-primary" href="/produk/">Cari Produk</a>', '<a class="btn btn-primary" href="/produk/">Lihat Katalog</a>', f"{route} catalog CTA")
        text = replace_commercial_block(
            text,
            r'<a class="btn btn-secondary" href="[^"]*">Tanya Stok</a>',
            f'<a class="btn btn-secondary" href="{local_wa}">Tanya Produk via WhatsApp</a>',
            route,
            "local WhatsApp CTA",
        )
        local_categories = (
            '<section class="section commercial-section local-categories"><div class="container">'
            '<div class="section-head"><div><span class="eyebrow">TELUSURI KATALOG</span>'
            '<h2>Mulai dari kategori produk.</h2>'
            '<p>Jelajahi kategori, lalu tanyakan nama atau SKU dan jumlah yang Anda perlukan.</p>'
            '</div></div>'
            + category_links
            + '<p class="commercial-crosslink">Belanja untuk toko atau proyek? '
            '<a href="/distributor-alat-listrik-sumbar/">Lihat informasi pengadaan B2B</a>. '
            'Punya atau sedang menyiapkan toko listrik? '
            '<a href="/jadi-mitra-retailer/">Tanyakan kemitraan retailer</a>.</p>'
            '</div></section>'
        )
        text = replace_commercial_block(
            text,
            r'<section class="section"><div class="container trust-grid">.*?</section>',
            local_categories,
            route,
            "local trust/statistics section",
        )
        local_inquiry = (
            '<h3>Perlu menanyakan harga atau ketersediaan?</h3>'
            '<p>Sertakan nama produk atau SKU jika ada, jumlah, dan pertanyaan Anda. WhatsApp akan terbuka dengan pesan awal untuk ditinjau.</p>'
            f'<a class="text-link" href="{local_wa}">Tanyakan produk via WhatsApp</a>'
        )
        text = replace_commercial_block(
            text,
            r'<h3>Tidak menemukan barang di katalog\?</h3><p>.*?</p><a class="text-link" href="[^"]*">Kirim pertanyaan →</a>',
            local_inquiry,
            route,
            "local inquiry section",
        )
        return text

    if route == "/distributor-alat-listrik-sumbar/":
        b2b_wa = commercial_whatsapp_url(
            "Halo Pratama, saya ingin bertanya tentang pengadaan alat listrik untuk toko atau proyek. "
            "Kategori, nama produk atau SKU: ____. Jumlah kebutuhan: ____. Kota/kabupaten: ____. "
            "Mohon informasi ketersediaan dan penawaran."
        )
        b2b_hero = (
            '<section class="b2b-hero"><div class="container b2b-grid"><div>'
            '<span class="eyebrow signal">PENGADAAN ALAT LISTRIK · SUMATERA BARAT</span>'
            '<h1>Pengadaan alat listrik untuk toko dan proyek.</h1>'
            '<p>Halaman ini ditujukan untuk pertanyaan pengadaan toko retail dan proyek. Siapkan nama atau SKU, jumlah kebutuhan, serta lokasi; tanyakan ketersediaan dan penawaran kepada tim Pratama.</p>'
            '<div class="hero-actions">'
            f'<a class="btn btn-signal" href="{b2b_wa}">Tanya Pengadaan via WhatsApp</a>'
            '<a class="btn btn-ghost-light" href="/jadi-mitra-retailer/">Informasi Kemitraan Retailer</a>'
            '</div></div><div class="mitra-panel"><span>UNTUK TOKO DAN PROYEK</span>'
            '<strong>RINCIAN KEBUTUHAN B2B</strong>'
            '<p>Produk atau SKU · jumlah kebutuhan · lokasi</p></div></div></section>'
        )
        text = replace_commercial_block(text, r'<section class="b2b-hero">.*?</section>', b2b_hero, route, "B2B hero")
        procurement = (
            '<section class="section commercial-section procurement-section"><div class="container">'
            '<div class="section-head"><div><span class="eyebrow">SEBELUM BERTANYA</span>'
            '<h2>Siapkan rincian kebutuhan pengadaan.</h2>'
            '<p>Bagikan informasi yang sudah tersedia. Harga, ketersediaan, persyaratan, dan cakupan layanan perlu dikonfirmasi langsung.</p>'
            '</div></div>'
            '<div class="commercial-info-grid">'
            '<article><h3>Jenis kebutuhan</h3><p>Toko retail atau proyek.</p></article>'
            '<article><h3>Produk dan jumlah</h3><p>Nama produk, SKU, kategori, dan jumlah kebutuhan jika sudah diketahui.</p></article>'
            '<article><h3>Lokasi kebutuhan</h3><p>Sebutkan kota atau kabupaten agar konteks pertanyaan jelas.</p></article>'
            '</div>'
            + category_links
            + '<p class="commercial-crosslink">Mencari informasi untuk membuka atau mengembangkan toko retail? '
            '<a href="/jadi-mitra-retailer/">Lihat halaman kemitraan Pratama Mitra</a>.</p>'
            '</div></section>'
        )
        text = replace_commercial_block(text, r'<section class="section"><div class="container">.*?</section>', procurement, route, "B2B feature section")
        return text

    partner_wa = commercial_whatsapp_url(
        "Halo Pratama, saya ingin bertanya tentang kemitraan retailer alat listrik. "
        "Kota/kabupaten toko: ____. Status toko: ____. Kategori atau brand yang diminati: ____."
    )
    partner_hero = (
        '<section class="b2b-hero"><div class="container b2b-grid"><div>'
        '<span class="eyebrow signal">KEMITRAAN RETAILER · SUMATERA BARAT</span>'
        '<h1>Kemitraan retailer alat listrik di Sumatera Barat.</h1>'
        '<p>Untuk pemilik atau calon pemilik toko listrik yang ingin menanyakan proses kemitraan. Sampaikan kota atau kabupaten, status toko, serta kategori atau brand yang diminati.</p>'
        '<div class="hero-actions">'
        '<a class="btn btn-signal" href="#daftar">Isi Formulir Kemitraan</a>'
        f'<a class="btn btn-ghost-light" href="{partner_wa}">Tanya Kemitraan via WhatsApp</a>'
        '</div></div><div class="mitra-panel"><span>INFORMASI TOKO</span>'
        '<strong>SUDAH ADA / SEDANG DISIAPKAN</strong>'
        '<p>Lokasi · status toko · kategori atau brand yang diminati</p></div></div></section>'
    )
    text = replace_commercial_block(text, r'<section class="b2b-hero">.*?</section>', partner_hero, route, "retailer hero")
    partner_steps = (
        '<section class="section commercial-section partner-preparation"><div class="container">'
        '<div class="section-head"><div><span class="eyebrow">SEBELUM MENGHUBUNGI</span>'
        '<h2>Siapkan informasi awal toko.</h2>'
        '<p>Informasi ini membantu menyusun pertanyaan kemitraan; persyaratan dan ketentuan komersial perlu dibahas langsung.</p>'
        '</div></div>'
        '<div class="commercial-info-grid">'
        '<article><h3>Status toko</h3><p>Pilih apakah toko sudah dimiliki atau sedang dipersiapkan.</p></article>'
        '<article><h3>Lokasi</h3><p>Masukkan kota atau kabupaten tempat toko berada atau direncanakan.</p></article>'
        '<article><h3>Minat produk</h3><p>Pilih kategori atau brand yang ingin dibicarakan.</p></article>'
        '</div>'
        + category_links
        + '<p class="commercial-crosslink">Untuk pertanyaan pengadaan proyek, '
        '<a href="/distributor-alat-listrik-sumbar/">lihat informasi pengadaan B2B</a>.</p>'
        '</div></section>'
    )
    text = replace_commercial_block(text, r'<section class="section"><div class="container">.*?</section>', partner_steps, route, "retailer benefit section")
    text = replace_once(text, '<section id="daftar" class="section soft-section">', '<section id="daftar" class="section soft-section commercial-application">', f"{route} application section")
    text = replace_once(text, '<span class="eyebrow">DAFTAR MITRA</span>', '<span class="eyebrow">KEMITRAAN RETAILER</span>', f"{route} form eyebrow")
    text = replace_once(text, '<h2>Punya atau sedang menyiapkan toko listrik?</h2>', '<h2>Bagikan informasi toko Anda.</h2>', f"{route} form heading")
    text = replace_once(
        text,
        '<p>Isi data singkat. Setelah dikirim, WhatsApp akan terbuka dengan data pendaftaran yang siap dikirim ke admin Pratama.</p>',
        '<p>Lengkapi informasi toko. WhatsApp akan terbuka dengan pesan yang sudah diisi; tinjau datanya, lalu tekan Kirim di WhatsApp.</p>',
        f"{route} form instructions",
    )
    text = replace_once(text, '<label for="partner-interest">Produk yang diminati</label>', '<label for="partner-interest">Kategori / brand yang diminati</label>', f"{route} product-interest label")
    text = replace_once(
        text,
        '<select id="partner-interest" name="produk"><option>EcoKing</option><option>Visalux</option><option>Kabel</option><option>Saklar &amp; Stop Kontak</option><option>MCB &amp; Proteksi</option><option>Beragam Produk</option></select>',
        '<select id="partner-interest" name="produk" required><option value="" selected disabled>Pilih kategori / brand</option><option>EcoKing</option><option>Visalux</option><option>Kabel</option><option>Saklar &amp; Stop Kontak</option><option>MCB &amp; Proteksi</option><option>Beragam Produk</option></select>',
        f"{route} product-interest options",
    )
    text = replace_once(
        text,
        '<select id="partner-status" name="status"><option>Sudah memiliki toko</option><option>Sedang mempersiapkan toko</option></select>',
        '<select id="partner-status" name="status" required><option value="" selected disabled>Pilih status toko</option><option>Sudah memiliki toko</option><option>Sedang mempersiapkan toko</option></select>',
        f"{route} status options",
    )
    text = replace_once(text, 'type="submit">Kirim Pendaftaran via WhatsApp</button>', 'type="submit">Lanjutkan ke WhatsApp</button>', f"{route} form CTA")
    return text

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
    # Use the supplied logo with its white background keyed to alpha. Preserve
    # the white-background source asset separately; do not redraw or upscale it.
    supplied_wordmark = root / "source" / "assets" / "pratama-brand-wordmark-home-transparent.png"
    if not supplied_wordmark.exists():
        raise RuntimeError("Missing transparent supplied homepage wordmark asset")
    shutil.copy2(supplied_wordmark, assets / "pratama-brand-wordmark-home-transparent.png")
    footer_logo = root / "source" / "assets" / "pratama-brand-footer-transparent.png"
    if not footer_logo.exists():
        raise RuntimeError("Missing transparent supplied footer logo asset")
    shutil.copy2(footer_logo, assets / "pratama-brand-footer-transparent.png")
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
        app_text = replace_once(
            app_text,
            "Halo Pratama, saya ingin mendaftar PRATAMA MITRA.",
            "Halo Pratama, saya ingin bertanya tentang kemitraan retailer alat listrik.",
            "partner WhatsApp message introduction",
        )
        app_text = replace_once(
            app_text,
            "\\n\\nMohon informasi kerja sama, harga grosir, dan program retailer.",
            "\\n\\nMohon informasi mengenai proses kemitraan.",
            "partner WhatsApp message close",
        )
        app_js.write_text(app_text, encoding="utf-8")
    brand_logos = root / "source" / "brand-logos"
    if brand_logos.exists():
        shutil.rmtree(assets / "brands", ignore_errors=True)
        shutil.copytree(brand_logos, assets / "brands", dirs_exist_ok=True)
    for stale_asset in ("whatsapp.svg", "whatsapp.jpg", "whatsapp.png", "whatsapp-clean.png", "whatsapp-floating.jpg", "whatsapp-floating-final.jpg", "whatsapp-floating-transparent.png", "whatsapp-floating-logo-only.png"):
        (assets / stale_asset).unlink(missing_ok=True)
    whatsapp_icon = root / "source" / "assets" / "whatsapp-floating.jpg"
    if not whatsapp_icon.exists():
        raise RuntimeError("Missing verified WhatsApp logo asset for the desktop floating action")
    shutil.copy2(whatsapp_icon, assets / "whatsapp-floating.jpg")
    top_bar_brand_menu = (
        '<a href="/produk/">Produk</a>'
        '<div class="nav-drop"><button>Brand <span>⌄</span></button><div class="drop-menu">'
        + "".join(f'<a href="/brand/{slug}/">{name}</a>' for name, slug in TOP_BAR_BRANDS)
        + '<a class="all-link" href="/produk/?view=brands">Semua brand →</a></div></div>'
    )
    for html_path in dist.rglob("*.html"): 
        text = html_path.read_text(encoding="utf-8")
        relative_parts = html_path.relative_to(dist).parts
        route = "/" if len(relative_parts) == 1 else "/" + "/".join(relative_parts[:-1]) + "/"
        route_scope = {
            "/toko-listrik-padang/": "padang-store",
            "/kontak/": "contact",
            "/distributor-alat-listrik-sumbar/": "b2b-procurement",
            "/jadi-mitra-retailer/": "retailer-partnership",
        }.get(route)
        if route_scope:
            if "<body" not in text:
                raise RuntimeError(f"Generated page has no body element: {html_path}")
            text = text.replace("<body", f'<body data-page="{route_scope}"', 1)

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
                '<link rel="stylesheet" href="/assets/styles.css"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet"><link rel="stylesheet" href="/assets/human-touch.css">',
            )
        commercial_routes = {
            "/toko-listrik-padang/",
            "/distributor-alat-listrik-sumbar/",
            "/jadi-mitra-retailer/",
        }
        cache_key = (
            "pratama-commercial-pages-2"
            if route in commercial_routes
            else "pratama-mobile-ux-1"
        )
        text = text.replace(
            '/assets/human-touch.css',
            f'/assets/human-touch.css?v={cache_key}',
        )
        text = text.replace('/assets/pratama-logo.svg', '/assets/pratama-brand-wordmark-home-transparent.png')
        legal_name = BUSINESS_INFO["legal_name"]
        footer_brand_block = (
            '<div class="footer-brand">PRATAMA</div>'
            '<div class="footer-descriptor">ELECTRICAL SUPPLY</div>'
            f'<p class="footer-legal">operated by {legal_name}</p>'
        )
        footer_logo_tag = (
            '<img class="footer-logo" src="/assets/pratama-brand-footer-transparent.png" '
            f'alt="Pratama Electrical Supply — operated by {legal_name}" '
            'width="260" height="75">'
        )
        if footer_brand_block not in text:
            raise RuntimeError(f"Generated footer brand block missing in {html_path}")
        text = text.replace(footer_brand_block, footer_logo_tag, 1)
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
        # Restore the authentic WhatsApp mark as a fixed desktop action on every
        # generated route. The mobile utility dock remains the small-screen action.
        desktop_whatsapp = (
            '<a class="wa-float" href="https://wa.me/6281993399888?text=Halo%20Pratama%2C%20saya%20ingin%20bertanya." '
            'aria-label="Hubungi Pratama via WhatsApp" title="Hubungi Pratama via WhatsApp" '
            'target="_blank" rel="noopener noreferrer">'
            '<img src="/assets/whatsapp-floating.jpg" width="52" height="52" alt=""></a>'
        )
        text, float_count = re.subn(
            r'<a class="wa-float"[^>]*>.*?</a>',
            lambda _: desktop_whatsapp,
            text,
            count=1,
            flags=re.S,
        )
        if not float_count:
            if "</body>" not in text:
                raise RuntimeError(f"Generated page has no body closing tag: {html_path}")
            text = text.replace("</body>", desktop_whatsapp + "</body>", 1)
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
                brand_sku_count = database_brand_sku_counts[brand_name.upper()]
                text = re.sub(
                    r'<h2>\d+ produk pilihan\.</h2>',
                    f'<h2>{brand_sku_count} SKU terdaftar di katalog.</h2>',
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
        text = apply_business_information(text)
        text = apply_commercial_landing_content(text, route)
        html_path.write_text(text, encoding="utf-8")

    # Homepage copy: more like a conversation at a long-established store,
    # less like labels inside a software dashboard.
    home = dist / "index.html"
    if home.exists():
        text = home.read_text(encoding="utf-8")
        if '<body class="">' not in text:
            raise RuntimeError('Homepage body class marker changed; update homepage contrast scope.')
        text = text.replace('<body class="">', '<body class="homepage">', 1)
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
        maps_url = BUSINESS_INFO["maps_url"]
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

# Publish only generated pages whose robots and canonical metadata make them
# eligible; this final pass must not re-add noindex product variants.
generate_sitemap(dist, SEO_SITE_URL)
(dist / "robots.txt").write_text(
    "User-agent: *\nAllow: /\n\nSitemap: " + SEO_SITE_URL + "/sitemap.xml\n",
    encoding="utf-8",
)

# Publish the RFC 9116 security contact. The current public contact channel is
# the site's Contact page; keep the expiry refreshed on each production build.
well_known = dist / ".well-known"
well_known.mkdir(parents=True, exist_ok=True)
security_txt = (
    "Contact: " + SEO_SITE_URL + "/kontak/\r\n"
    "Expires: " + (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ") + "\r\n"
    "Preferred-Languages: id, en\r\n"
    "Canonical: " + SEO_SITE_URL + "/.well-known/security.txt\r\n"
)
(well_known / "security.txt").write_bytes(security_txt.encode("utf-8"))

# Persisted product images are collected by GitHub Actions and stored in
# source/product-images. Apply them after the static generator finishes so the
# same image set is used by GitHub Pages and future production deployments.
apply_images = root / "tools" / "apply_product_images.py"
if apply_images.exists():
    namespace = {"__name__": "__main__", "__file__": str(apply_images)}
    exec(compile(apply_images.read_bytes(), str(apply_images), "exec"), namespace)

# Fail the build if a generated public text asset still names the incorrect entity.
public_text_extensions = {".html", ".css", ".js", ".json", ".xml", ".svg", ".txt", ".webmanifest"}
legacy_identity_paths = []
for public_asset in dist.rglob("*"):
    if not public_asset.is_file() or public_asset.suffix.casefold() not in public_text_extensions:
        continue
    try:
        public_text = public_asset.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    if has_legacy_psm_legal_entity_reference(public_text):
        legacy_identity_paths.append(str(public_asset.relative_to(dist)))
if legacy_identity_paths:
    raise RuntimeError(
        "Generated public assets contain the incorrect legal entity name: "
        + ", ".join(legacy_identity_paths)
    )
