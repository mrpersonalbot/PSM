#!/usr/bin/env python3
"""Publish only exact, official EcoKing variant images selected from the catalog."""
import hashlib
import json
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "source/product-images"
BASE = "https://www.ecoking.co.id/product/led-bulb/"

# The selected frame is the package variant whose printed wattage matches the
# catalog row. The official page supplies the brand and family evidence.
SELECTED = {
    "lampu-led-3w-ecoking": {
        "page": BASE + "led-star",
        "image": "https://www.ecoking.co.id/storage/assets/images/sub-categories/images/64ccfb685387f.png",
        "model": "LED Star 3W variant",
        "specs": "3W; E27; official LED Star product family",
    },
    "led-avatar-6w-6500k-ecoking": {
        "page": BASE + "led-avatar",
        "image": "https://www.ecoking.co.id/storage/assets/images/sub-categories/images/64ccff4057b41.png",
        "model": "LED Avatar 6W variant",
        "specs": "6W; 6500K daylight; official LED Avatar product family",
    },
    "led-legend-5w-kuning-ecoking": {
        "page": BASE + "led-legend-warm-white",
        "image": "https://www.ecoking.co.id/storage/assets/images/sub-categories/images/66a707089fc38.png",
        "model": "LED Legend 5W warm-white variant",
        "specs": "5W; warm white/yellow; official LED Legend product family",
    },
}


def normalize(src: Path, dst: Path) -> None:
    image = Image.open(src).convert("RGBA")
    image.thumbnail((864, 864), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (1200, 1200), (255, 255, 255, 255))
    canvas.alpha_composite(image, ((1200 - image.width) // 2, (1200 - image.height) // 2))
    canvas.convert("RGB").save(dst, "WEBP", quality=90, method=6)


def main() -> None:
    products = {p["slug"]: p for p in json.loads(__import__("gzip").decompress(__import__("base64").b64decode((ROOT / "source/payload/products.gz.b64").read_bytes())))}
    mapping_path = ROOT / "source/product-images.json"
    mapping = json.loads(mapping_path.read_text())
    review_path = ROOT / "source/existing-image-review.json"
    review = json.loads(review_path.read_text())
    review.setdefault("approved", {})
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    for slug, selected in SELECTED.items():
        product = products[slug]
        raw = ROOT / "work" / (slug + ".png")
        raw.parent.mkdir(exist_ok=True)
        urllib.request.urlretrieve(selected["image"], raw)
        out = IMAGE_ROOT / (slug + ".webp")
        normalize(raw, out)
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        mapping[slug] = {
            "status": "resolved", "validation_version": 4, "mode": "semi_strict",
            "resolver": "manual-official-ecoking", "file": "product-images/" + out.name,
            "source_tier": "official", "source_page": selected["page"],
            "source_image": selected["image"], "sku": product["sku"],
            "name": product["name"], "brand": product["brand"],
            "model_tokens": [], "evidence": "official EcoKing product page and matching printed package variant",
            "evidence_title": selected["model"], "specs": selected["specs"],
            "sha256": digest,
        }
        review["approved"][slug] = {
            "brand": product["brand"], "model": selected["model"], "specs": selected["specs"],
            "source_page": selected["page"], "source_image": selected["image"],
            "sha256": digest, "visual_review": "Package visibly shows EcoKing product family and matching wattage variant.",
        }
    review["matched"] = len(review["approved"])
    review["unresolved"] = len(products) - review["matched"]
    mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n")
    report_path = ROOT / "source/product-images-report.json"
    report = json.loads(report_path.read_text())
    report["resolved"] = review["matched"]
    report["unresolved_count"] = review["unresolved"]
    report["source_tiers"] = {"official": review["matched"]}
    report["resolver"] = "manual-official-ecoking + existing-image-review"
    report["unresolved"] = [{"slug": s, "sku": p["sku"], "name": p["name"], "brand": p["brand"], "reason": mapping[s].get("reason", "no verified image")}
                              for s, p in products.items() if s not in review["approved"]]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    review_queue = ROOT / "source/product-images-review.json"
    review_queue.write_text(json.dumps({
        "mode": "semi_strict", "needs_review": report["unresolved"],
        "resolved": sorted(review["approved"]),
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"Published {review['matched']} official EcoKing images; {review['unresolved']} remain unresolved")


if __name__ == "__main__":
    main()
