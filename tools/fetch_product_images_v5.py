#!/usr/bin/env python3
"""Fast evidence-first product image resolver for the 160-product catalog.

Uses Bing Images result metadata as a fallback when the source product page is
not fetchable from a GitHub runner. It never trusts the search query itself as
evidence: acceptance is based on returned title/source URL, brand, model tokens,
source tier, and the existing image normalization policy.
"""
import json
import random
import time
from pathlib import Path

from bs4 import BeautifulSoup
from rembg import new_session

import fetch_product_images as base


def bing_hits(query, limit=24):
    try:
        r = base.S.get(
            "https://www.bing.com/images/search",
            params={"q": query},
            timeout=14,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for a in soup.select("a.iusc"):
            try:
                m = json.loads(a.get("m", "{}"))
            except Exception:
                continue
            page = m.get("purl") or ""
            image = m.get("murl") or ""
            if not page or not image:
                continue
            title = (
                m.get("t")
                or m.get("title")
                or m.get("desc")
                or a.get("aria-label")
                or ""
            )
            out.append(
                {
                    "page": page,
                    "image": image,
                    "title": str(title),
                    "query": query,
                }
            )
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def evidence(hit, product):
    brand = str(product["brand"]).upper()
    source_page = hit["page"]
    host = base.host_of(source_page)
    tier = base.source_tier(host, brand)

    if tier == "blocked":
        return False, 0, tier, "blocked_source"

    title = base.norm(hit.get("title", ""))
    evidence_text = base.norm(hit.get("title", "") + " " + source_page)
    compact_evidence = base.compact(evidence_text)
    mods = base.model_tokens(product)
    terms = base.tokens(product["name"])
    exact_models = [m for m in mods if m in compact_evidence]
    coverage = sum(t in evidence_text for t in terms) / max(1, len(terms))
    brand_match = brand in evidence_text or base.host_is_approved(host, brand)

    if not brand_match:
        return False, 0, tier, "brand_mismatch"

    if tier == "marketplace":
        if (
            not base.RULES.get("allow_marketplace_with_exact_model", False)
            or not mods
            or not exact_models
        ):
            return False, 0, tier, "marketplace_requires_exact_model"
        compact_title = base.compact(title)
        if brand not in title or not any(m in compact_title for m in mods):
            return False, 0, tier, "marketplace_title_mismatch"
        min_cov = float(
            base.RULES.get("marketplace_min_name_coverage", 0.50)
        )
        if coverage < min_cov:
            return False, 0, tier, "weak_name_match"
        return (
            True,
            250 + 100 * len(exact_models) + round(coverage * 80),
            tier,
            "bing_exact_model",
        )

    if mods:
        if not exact_models:
            return False, 0, tier, "model_not_found"
        min_cov = (
            0.18
            if tier == "official"
            else float(
                base.RULES.get(
                    "independent_min_name_coverage_with_model", 0.40
                )
            )
        )
        if coverage < min_cov:
            return False, 0, tier, "weak_name_match"
        if tier == "independent" and brand not in title and coverage < 0.60:
            return False, 0, tier, "weak_product_title"
        score = (
            (360 if tier == "official" else 280)
            + 100 * len(exact_models)
            + round(coverage * 90)
        )
        return True, score, tier, "bing_exact_model"

    # No manufacturer/model token: only allow very strong textual agreement.
    # Generic marketplace listings remain intentionally unresolved.
    if tier == "marketplace":
        return False, 0, tier, "generic_marketplace_not_allowed"

    min_cov = (
        0.62
        if tier == "official"
        else max(
            0.82,
            float(
                base.RULES.get(
                    "independent_min_name_coverage_without_model", 0.78
                )
            ),
        )
    )
    if coverage < min_cov:
        return False, 0, tier, "weak_name_match"
    if tier == "independent" and brand not in title:
        return False, 0, tier, "weak_product_title"
    score = (300 if tier == "official" else 220) + round(coverage * 100)
    return True, score, tier, "bing_strong_title"


def resolve(product, session):
    queries = base.search_queries(product)
    accepted = []
    rejected = []
    seen = set()

    # Four queries per product keeps a 160-product run comfortably below the
    # previous 330-minute timeout while still covering model/name variants.
    for query in queries[:4]:
        for hit in bing_hits(query):
            key = (hit["page"], hit["image"])
            if key in seen:
                continue
            seen.add(key)
            ok, score, tier, reason = evidence(hit, product)
            if ok:
                accepted.append((score, tier, hit))
            elif len(rejected) < 20:
                rejected.append(
                    {
                        "page": hit["page"],
                        "title": hit["title"][:300],
                        "reason": reason,
                        "tier": tier,
                    }
                )

    accepted.sort(reverse=True, key=lambda x: x[0])
    image_rejections = []

    for page_score, tier, hit in accepted[:20]:
        image = base.download_image(hit["image"], hit["page"])
        if image is None:
            continue

        entry = {
            "url": hit["image"],
            "meta": hit["title"],
            "kind": "jsonld",  # strong metadata-equivalent evidence for scoring
        }
        image_score = base.source_image_score(entry, image, product, tier)
        if image_score <= -500:
            continue

        normalized, reason = base.normalize_product(image, session)
        if normalized is None:
            if len(image_rejections) < 20:
                image_rejections.append(
                    {"image": hit["image"], "reason": reason}
                )
            continue

        path = base.OUT / (product["slug"] + ".webp")
        normalized.save(path, "WEBP", quality=90, method=6)

        return {
            "status": "resolved",
            "validation_version": base.VALIDATION_VERSION,
            "mode": base.MODE,
            "file": f'product-images/{product["slug"]}.webp',
            "source_tier": tier,
            "source_page": hit["page"],
            "source_image": hit["image"],
            "page_score": page_score,
            "image_score": round(image_score, 1),
            "model_tokens": base.model_tokens(product),
            "query": hit["query"],
            "search_fallback": True,
            "evidence": "bing_result_title_and_source_url",
            "evidence_title": hit["title"][:500],
        }

    return {
        "status": "unresolved",
        "validation_version": base.VALIDATION_VERSION,
        "mode": base.MODE,
        "reason": (
            "no_strong_search_evidence"
            if not accepted
            else "no_uncropped_valid_image"
        ),
        "queries": queries,
        "page_rejections": rejected,
        "image_rejections": image_rejections,
    }


def write_report(mapping, products):
    unresolved = []
    tiers = {}
    resolved = 0

    for p in products:
        v = mapping.get(p["slug"], {})
        if v.get("status") == "resolved":
            resolved += 1
            t = v.get("source_tier", "unknown")
            tiers[t] = tiers.get(t, 0) + 1
        else:
            unresolved.append(
                {
                    "slug": p["slug"],
                    "sku": p["sku"],
                    "name": p["name"],
                    "brand": p["brand"],
                    "reason": v.get("reason", "unresolved"),
                }
            )

    report = {
        "validation_version": base.VALIDATION_VERSION,
        "mode": base.MODE,
        "resolver": "bing-evidence-v5",
        "total": len(products),
        "resolved": resolved,
        "unresolved_count": len(unresolved),
        "source_tiers": tiers,
        "unresolved": unresolved,
    }
    base.REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    base.REVIEW.write_text(
        json.dumps(
            {"mode": base.MODE, "needs_review": unresolved},
            ensure_ascii=False,
            indent=2,
        )
    )
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
            previous = {}

    # Preserve only already-validated files from the same validation version.
    mapping = {
        slug: value
        for slug, value in previous.items()
        if value.get("status") == "resolved"
        and value.get("validation_version") == base.VALIDATION_VERSION
        and (base.ROOT / "source" / value.get("file", "")).exists()
    }

    referenced = {
        Path(v["file"]).name for v in mapping.values() if v.get("file")
    }
    for f in base.OUT.glob("*.webp"):
        if f.name not in referenced:
            f.unlink()

    pending = [p for p in products if p["slug"] not in mapping]
    print(
        f"{base.MODE} v{base.VALIDATION_VERSION} / bing-evidence-v5: "
        f"{len(mapping)} validated, {len(pending)} pending, "
        f"{len(products)} total",
        flush=True,
    )

    session = new_session("u2netp")

    for i, product in enumerate(pending, 1):
        print(
            f'[{i}/{len(pending)}] {product["brand"]} | '
            f'{product["name"]} | {product["sku"]}',
            flush=True,
        )
        mapping[product["slug"]] = {
            **resolve(product, session),
            "sku": product["sku"],
            "name": product["name"],
            "brand": product["brand"],
        }
        base.MAP.write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2)
        )
        if i % 20 == 0:
            partial = write_report(mapping, products)
            print(
                f'checkpoint: {partial["resolved"]}/'
                f'{partial["total"]} resolved',
                flush=True,
            )
        time.sleep(random.uniform(0.05, 0.12))

    report = write_report(mapping, products)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
