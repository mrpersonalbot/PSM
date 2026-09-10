#!/usr/bin/env python3
"""Multi-engine, evidence-first resolver for the 160-product catalog.

Goal: maximize coverage without ever substituting a visibly different product.
Discovery uses DuckDuckGo Images, Bing Images and ordinary web search. Acceptance
requires brand + model/spec agreement, then downloaded images are normalized to
1200x1200 white canvas. OCR is used only as an additional mismatch guard, never
as the sole identity signal.
"""
import json
import random
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from rembg import new_session

import fetch_product_images as base

ENGINE = "multi-engine-evidence-v6"

SPEC_MODEL_RE = re.compile(
    r"^(?:E27|E14|T5|T8|A60|G45|R\d+|\d+(?:W|V|A|KA|MM|CM|M|INCH)|\d+X(?:AA|AAA)|\d+POLE|\d+GROUP)$",
    re.I,
)
COLORS = {
    "PUTIH", "WHITE", "HITAM", "BLACK", "MERAH", "RED", "BIRU", "BLUE",
    "KUNING", "YELLOW", "HIJAU", "GREEN", "ORANGE", "GOLD", "CREAM",
}
SHAPES = {"BULAT", "ROUND", "PETAK", "SQUARE", "SEGI", "FLAT"}
GENERIC_WORDS = {
    "LAMPU", "LED", "BULB", "DOWNLIGHT", "DL", "FITTING", "SAKLAR", "STOP",
    "KONTAK", "KABEL", "MCB", "MCCB", "BOX", "HEAD", "LIGHT", "WALL", "PILOT",
    "MULTICORD", "OUTLET", "RAKET", "NYAMUK", "FUSE", "TIME", "SWITCH",
}


def strong_model_tokens(product):
    out = []
    # Preserve punctuation while identifying catalogue-like codes.
    raws = re.findall(r"[A-Z0-9][A-Z0-9._/-]{1,}", str(product["name"]).upper())
    for raw in raws:
        c = base.compact(raw)
        if len(c) < 3 or SPEC_MODEL_RE.match(c):
            continue
        if not re.search(r"[A-Z]", c) or not re.search(r"\d", c):
            continue
        # Plain electrical sizes such as 3X1.5 or 2X0.75 are specs, not models.
        if re.match(r"^\d+X\d", c):
            continue
        out.append(c)
    # Prefer more distinctive codes first.
    out = list(dict.fromkeys(out))
    out.sort(key=lambda x: (len(x), sum(ch.isdigit() for ch in x)), reverse=True)
    return out


def watt_values(text):
    return {m.group(1).replace(",", ".") for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*W\b", str(text), re.I)}


def cct_values(text):
    return {m.group(1) for m in re.finditer(r"\b(\d{4})\s*K\b", str(text), re.I)}


def amp_values(text):
    return {m.group(1) for m in re.finditer(r"\b(\d+(?:[.,]\d+)?)\s*A\b", str(text), re.I)}


def color_words(text):
    n = base.norm(text)
    return {c for c in COLORS if re.search(r"(?:^| )" + re.escape(c) + r"(?: |$)", n)}


def shape_words(text):
    n = base.norm(text)
    return {c for c in SHAPES if re.search(r"(?:^| )" + re.escape(c) + r"(?: |$)", n)}


def conflict_guard(product, evidence_text, require_specs=False):
    p = product["name"]
    checks = ((watt_values(p), watt_values(evidence_text), "watt"),
              (cct_values(p), cct_values(evidence_text), "cct"))
    for wanted, seen, label in checks:
        if wanted and seen and wanted.isdisjoint(seen):
            return False, f"conflicting_{label}"
        if require_specs and wanted and not (wanted & seen):
            return False, f"missing_{label}"
    # Amperage is important for breakers/contactors but not every product.
    if any(k in base.norm(p) for k in ("MCB", "MCCB", "AMPER", "STARTER", "FUSE")):
        wanted, seen = amp_values(p), amp_values(evidence_text)
        if wanted and seen and wanted.isdisjoint(seen):
            return False, "conflicting_amp"
        if require_specs and wanted and not (wanted & seen):
            return False, "missing_amp"
    pc, ec = color_words(p), color_words(evidence_text)
    if pc and ec and pc.isdisjoint(ec):
        return False, "conflicting_color"
    ps, es = shape_words(p), shape_words(evidence_text)
    if ps and es and ps.isdisjoint(es):
        return False, "conflicting_shape"
    return True, "ok"


def ddg_vqd(query):
    try:
        r = base.S.get("https://duckduckgo.com/", params={"q": query}, timeout=14)
        for pat in (r'vqd=["\']?([\d-]+)', r'vqd\s*[:=]\s*["\']([\d-]+)'):
            m = re.search(pat, r.text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def ddg_hits(query, limit=40):
    token = ddg_vqd(query)
    if not token:
        return []
    try:
        r = base.S.get(
            "https://duckduckgo.com/i.js",
            params={"l": "id-id", "o": "json", "q": query, "vqd": token, "f": ",,,", "p": "1"},
            headers={"Referer": "https://duckduckgo.com/"},
            timeout=18,
        )
        data = r.json()
        out = []
        for item in data.get("results", []):
            page = item.get("url") or ""
            image = item.get("image") or ""
            if not page or not image:
                continue
            out.append({
                "page": page,
                "image": image,
                "title": str(item.get("title") or ""),
                "query": query,
                "engine": "duckduckgo",
            })
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def bing_hits(query, limit=32):
    try:
        r = base.S.get("https://www.bing.com/images/search", params={"q": query, "form": "HDRSC3"}, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for a in soup.select("a.iusc"):
            try:
                m = json.loads(a.get("m", "{}"))
            except Exception:
                continue
            page, image = m.get("purl") or "", m.get("murl") or ""
            if not page or not image:
                continue
            out.append({
                "page": page,
                "image": image,
                "title": str(m.get("t") or m.get("title") or m.get("desc") or a.get("aria-label") or ""),
                "query": query,
                "engine": "bing",
            })
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def page_hits(query, product, limit=20):
    """Turn ordinary web-search result pages into image candidates."""
    urls = []
    for fn in (base.google_pages, base.bing_pages, base.duck_pages):
        try:
            for u in fn(query, limit=8):
                if u not in urls:
                    urls.append(u)
        except Exception:
            pass
    out = []
    for u in urls[:limit]:
        if base.source_tier(base.host_of(u), product["brand"]) == "blocked":
            continue
        info = base.page_info(u)
        if not info.get("text"):
            continue
        for entry in info.get("images", [])[:20]:
            img = entry.get("url") or ""
            if not img:
                continue
            out.append({
                "page": info.get("url", u),
                "image": img,
                "title": info.get("title", ""),
                "page_text": info.get("text", "")[:12000],
                "query": query,
                "engine": "web-page",
                "kind": entry.get("kind", "img"),
                "meta": entry.get("meta", ""),
            })
    return out


def evidence(hit, product):
    brand = str(product["brand"]).upper()
    host = base.host_of(hit["page"])
    tier = base.source_tier(host, brand)
    if tier == "blocked":
        return False, 0, tier, "blocked_source"

    title = base.norm(hit.get("title", ""))
    page_text = base.norm(hit.get("page_text", ""))
    text = base.norm(" ".join([title, hit.get("page", ""), hit.get("meta", ""), page_text]))
    compact_text = base.compact(text)
    models = strong_model_tokens(product)
    matched_models = [m for m in models if m in compact_text]
    terms = [t for t in base.tokens(product["name"]) if t not in COLORS and t not in SHAPES]
    coverage = sum(t in text for t in terms) / max(1, len(terms))
    brand_match = brand in text or base.host_is_approved(host, brand)
    if not brand_match:
        return False, 0, tier, "brand_mismatch"

    if models:
        if not matched_models:
            return False, 0, tier, "model_not_found"
        ok, reason = conflict_guard(product, text, require_specs=False)
        if not ok:
            return False, 0, tier, reason
        # Marketplace requires the exact model in the returned title/URL, not
        # merely somewhere in a long scraped product page.
        title_url = base.compact(title + " " + hit.get("page", ""))
        if tier == "marketplace" and not any(m in title_url for m in models):
            return False, 0, tier, "marketplace_model_not_in_title"
        min_cov = 0.12 if tier == "official" else (0.26 if tier == "marketplace" else 0.24)
        if coverage < min_cov:
            return False, 0, tier, "weak_name_match"
        score = (520 if tier == "official" else 430 if tier == "marketplace" else 390)
        score += 130 * len(matched_models) + round(coverage * 100)
        if hit.get("kind") in {"og", "jsonld", "twitter"}:
            score += 50
        return True, score, tier, "exact_model_and_specs"

    # Products with no catalogue code must match their descriptive identity.
    # Require exact numerical specs where present so a 5W image cannot be used
    # for a 20W row, etc.
    ok, reason = conflict_guard(product, text, require_specs=True)
    if not ok:
        return False, 0, tier, reason
    min_cov = 0.58 if tier == "official" else 0.76 if tier == "marketplace" else 0.72
    if coverage < min_cov:
        return False, 0, tier, "weak_generic_match"
    # Generic marketplace pages are acceptable only if the title itself carries
    # the brand and most descriptive terms/specs.
    title_terms = sum(t in title for t in terms) / max(1, len(terms))
    if tier == "marketplace" and (brand not in title or title_terms < 0.68):
        return False, 0, tier, "weak_marketplace_title"
    score = (400 if tier == "official" else 320 if tier == "marketplace" else 300)
    score += round(coverage * 120) + round(title_terms * 80)
    return True, score, tier, "strong_brand_spec_match"


def ocr_text(image):
    """Best-effort OCR; failures are deliberately non-fatal."""
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            image.convert("RGB").save(f.name)
            cp = subprocess.run(
                ["tesseract", f.name, "stdout", "--psm", "6"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=12,
                check=False,
            )
            return base.norm(cp.stdout[:5000])
    except Exception:
        return ""


def ocr_guard(product, text):
    if not text:
        return True, "ocr_empty"
    brand = str(product["brand"]).upper()
    # Reject a clearly different known brand printed on the image when the
    # target brand itself is absent.
    printed = {b for b in base.BRANDS if b in text}
    if printed and brand not in printed:
        return False, "ocr_other_brand"
    models = strong_model_tokens(product)
    # If OCR happens to read a target model, that is a strong positive. If not,
    # source evidence still governs because many product photos have no label.
    ok, reason = conflict_guard(product, text, require_specs=False)
    if not ok:
        return False, "ocr_" + reason
    return True, "ocr_ok_model" if any(m in base.compact(text) for m in models) else "ocr_ok"


def discovery_queries(product):
    brand = str(product["brand"]).upper()
    models = strong_model_tokens(product)
    name = product["name"]
    out = []
    for m in models[:3]:
        out += [f'"{brand}" "{m}"', f'{brand} {m}', f'"{m}" product image']
    out += [f'"{name}"', f'{brand} {name}', f'{brand} ' + " ".join(base.tokens(name)[:10])]
    for dom in base.approved_domains(brand):
        if models:
            out.insert(0, f'site:{dom} "{models[0]}"')
        out.insert(0, f'site:{dom} "{name}"')
    return list(dict.fromkeys(q for q in out if q.strip()))[:8]


def resolve(product, session):
    queries = discovery_queries(product)
    accepted, rejected, seen = [], [], set()
    engine_counts = {"duckduckgo": 0, "bing": 0, "web-page": 0}

    for qi, query in enumerate(queries):
        hits = ddg_hits(query) + bing_hits(query)
        # Use slower page discovery only for the first few high-quality queries.
        if qi < 3:
            hits += page_hits(query, product)
        for hit in hits:
            key = (hit.get("page"), hit.get("image"))
            if not all(key) or key in seen:
                continue
            seen.add(key)
            engine_counts[hit.get("engine", "unknown")] = engine_counts.get(hit.get("engine", "unknown"), 0) + 1
            ok, score, tier, reason = evidence(hit, product)
            if ok:
                accepted.append((score, tier, hit, reason))
            elif len(rejected) < 35:
                rejected.append({
                    "page": hit.get("page", ""),
                    "title": str(hit.get("title", ""))[:300],
                    "reason": reason,
                    "tier": tier,
                    "engine": hit.get("engine"),
                })
        # Once we have several strong exact-model candidates, stop discovery.
        if len(accepted) >= 8:
            break

    accepted.sort(reverse=True, key=lambda x: x[0])
    image_rejections = []
    for page_score, tier, hit, evidence_reason in accepted[:30]:
        image = base.download_image(hit["image"], hit["page"])
        if image is None:
            if len(image_rejections) < 30:
                image_rejections.append({"image": hit["image"], "reason": "download_failed"})
            continue

        # Use real result metadata, never the search query itself, for scoring.
        entry = {"url": hit["image"], "meta": str(hit.get("title", "")) + " " + str(hit.get("meta", "")), "kind": hit.get("kind", "image_search")}
        image_score = base.source_image_score(entry, image, product, tier)
        if image_score <= -500:
            continue

        # OCR is expensive; use it only when source evidence is borderline.
        ocr = ""
        ocr_reason = "ocr_skipped_strong_evidence"
        if page_score < 520 or image_score < 0:
            ocr = ocr_text(image)
            ok, ocr_reason = ocr_guard(product, ocr)
            if not ok:
                if len(image_rejections) < 30:
                    image_rejections.append({"image": hit["image"], "reason": ocr_reason, "ocr": ocr[:500]})
                continue

        normalized, reason = base.normalize_product(image, session)
        if normalized is None:
            if len(image_rejections) < 30:
                image_rejections.append({"image": hit["image"], "reason": reason})
            continue

        path = base.OUT / (product["slug"] + ".webp")
        normalized.save(path, "WEBP", quality=90, method=6)
        return {
            "status": "resolved",
            "validation_version": base.VALIDATION_VERSION,
            "mode": base.MODE,
            "resolver": ENGINE,
            "file": f'product-images/{product["slug"]}.webp',
            "source_tier": tier,
            "source_page": hit["page"],
            "source_image": hit["image"],
            "page_score": page_score,
            "image_score": round(image_score, 1),
            "model_tokens": strong_model_tokens(product),
            "query": hit["query"],
            "search_fallback": hit.get("engine") != "web-page",
            "evidence": evidence_reason,
            "evidence_title": str(hit.get("title", ""))[:500],
            "engine": hit.get("engine"),
            "ocr_evidence": ocr_reason,
            "ocr_text": ocr[:800],
        }

    return {
        "status": "unresolved",
        "validation_version": base.VALIDATION_VERSION,
        "mode": base.MODE,
        "resolver": ENGINE,
        "reason": "no_strong_search_evidence" if not accepted else "all_candidate_images_rejected",
        "queries": queries,
        "engine_counts": engine_counts,
        "page_rejections": rejected,
        "image_rejections": image_rejections,
    }


def write_report(mapping, products):
    unresolved, tiers, engines = [], {}, {}
    resolved = 0
    for p in products:
        v = mapping.get(p["slug"], {})
        if v.get("status") == "resolved":
            resolved += 1
            tiers[v.get("source_tier", "unknown")] = tiers.get(v.get("source_tier", "unknown"), 0) + 1
            engines[v.get("engine", "unknown")] = engines.get(v.get("engine", "unknown"), 0) + 1
        else:
            unresolved.append({
                "slug": p["slug"], "sku": p["sku"], "name": p["name"],
                "brand": p["brand"], "reason": v.get("reason", "unresolved")
            })
    report = {
        "validation_version": base.VALIDATION_VERSION,
        "mode": base.MODE,
        "resolver": ENGINE,
        "total": len(products), "resolved": resolved,
        "unresolved_count": len(unresolved), "source_tiers": tiers,
        "engines": engines, "unresolved": unresolved,
    }
    base.REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    base.REVIEW.write_text(json.dumps({"mode": base.MODE, "needs_review": unresolved}, ensure_ascii=False, indent=2))
    return report


def main():
    if not base.PRODUCTS.exists():
        print("Run build.py first")
        return 2
    products = json.loads(base.PRODUCTS.read_text())
    previous = {}
    if base.MAP.exists():
        try:
            previous = json.loads(base.MAP.read_text())
        except Exception:
            pass
    mapping = {
        slug: value for slug, value in previous.items()
        if value.get("status") == "resolved"
        and value.get("validation_version") == base.VALIDATION_VERSION
        and (base.ROOT / "source" / value.get("file", "")).exists()
    }
    referenced = {Path(v["file"]).name for v in mapping.values() if v.get("file")}
    for f in base.OUT.glob("*.webp"):
        if f.name not in referenced:
            f.unlink()
    pending = [p for p in products if p["slug"] not in mapping]
    print(f"{base.MODE} v{base.VALIDATION_VERSION} / {ENGINE}: {len(mapping)} validated, {len(pending)} pending, {len(products)} total", flush=True)
    session = new_session("u2netp")
    # Resolve independent SKUs concurrently. Each future is bounded so one
    # slow source cannot hold the entire catalog hostage.
    workers = min(10, max(1, len(pending)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(resolve, product, session): product for product in pending}
        for i, future in enumerate(as_completed(futures), 1):
            product = futures[future]
            try:
                result = future.result(timeout=95)
            except Exception as exc:
                result = {"status": "unresolved", "validation_version": base.VALIDATION_VERSION,
                          "mode": base.MODE, "resolver": ENGINE, "reason": f"timeout_or_error:{type(exc).__name__}"}
            mapping[product["slug"]] = {**result, "sku": product["sku"], "name": product["name"], "brand": product["brand"]}
            base.MAP.write_text(json.dumps(mapping, ensure_ascii=False, indent=2))
            if i % 5 == 0 or i == len(pending):
                r = write_report(mapping, products)
                print(f'checkpoint: {i}/{len(pending)} processed, {r["resolved"]}/{r["total"]} resolved', flush=True)
    report = write_report(mapping, products)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
