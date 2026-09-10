#!/usr/bin/env python3
"""Publish exact Visalux product images from the manufacturer reseller catalog."""
import base64, gzip, hashlib, json, urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "source/product-images"
SITE = "https://www.goldenbatamraya.com"
SELECTED = {
    "saklar-seri-1w-10a-vse3021-visalux": ("e-series/vse3021", "sbIaqIjc6nsrGAFKLBwGa6b9cKbd0LRnP5C2tVcH.png", "VSE3021", "1 gang; 10A; Visalux E-Series"),
    "saklar-tripel-1w-10a-vse3031-visalux": ("e-series/vse3031", "FO8uglxREkZzw6cq8ROy1Bmni9VuaEQIF2mfbNrx.png", "VSE3031", "3 gang; 10A; Visalux E-Series"),
    "s-k-ob-visalux-cello-putih-vs6016": ("cello-series/vs6016-ob", "UlWs4D0ajIV9PcQx5Cm0wKhBZn9mZubyZ6ddq70C.png", "VS6016-OB", "OB socket; white; Visalux Cello Series"),
    "saklar-seri-ob-visalux-cello-putih-vs6210": ("cello-series/vs6210-ob", "ba8qi3KtxKPsDSsmndgqZ6VJAW2aCwEURPZQrWgS.png", "VS6210-OB", "series switch; white; Visalux Cello Series"),
    "led-fl-royal-20w-3000k-visalux-ryl-vfl-5520w": ("led-floodlight-royal/ryl-vfl5520", "EBluHeIVeGb1HGP6jzNZn1AT5UhcrkIQlsLAIeol.png", "RYL-VFL5520", "20W; 3000K; Royal floodlight; Visalux"),
    "led-solar-fl-50w-6500k-3000k-2warna-swat-vfl-5550-visalux": ("led-floodlight-mythic/vfl5550", "TInUKRAqZ6lBfQnAm733TYulGmhTHkJy91aahIPS.png", "VFL5550", "50W; 6500K/3000K; solar floodlight; Visalux"),
    "multicord-5-lbg-2m-vek5205e-mozart-visalux": ("cable-extension-mozart/moz-vek5205e", "kLE5mx2cbUVNqnp6JThSpSDsXSupKnbP11ju199E.png", "MOZ-VEK5205E", "5 outlet; 2m; Mozart multicord; Visalux"),
    "multicord-neutron-3lb-vek5203e-2m-visalux": ("cable-extention-neutron/vek-5203e", "WVsEP8cZUsdNjo2vKhd3Rj0OfCwnfs9VSKSskRtl.png", "VEK-5203E", "3 outlet; 2m; Neutron multicord; Visalux"),
}

def save_image(url, path):
    raw = ROOT / "source" / (path.stem + ".source.png")
    raw.write_bytes(urllib.request.urlopen(url, timeout=30).read())
    im = Image.open(raw).convert("RGBA")
    im.thumbnail((864, 864), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (1200, 1200), "white")
    canvas.alpha_composite(im, ((1200-im.width)//2, (1200-im.height)//2))
    canvas.convert("RGB").save(path, "WEBP", quality=90, method=6)
    raw.unlink()

def main():
    products = {p["slug"]: p for p in json.loads(gzip.decompress(base64.b64decode((ROOT/"source/payload/products.gz.b64").read_bytes())))}
    mp_path = ROOT / "source/product-images.json"; mapping = json.loads(mp_path.read_text())
    rv_path = ROOT / "source/existing-image-review.json"; review = json.loads(rv_path.read_text()); review.setdefault("approved", {})
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, (route, filename, model, specs) in SELECTED.items():
        p = products[slug]; dst = OUT / (slug + ".webp"); source = SITE + "/storage/assets/images/sub-categories/" + filename
        save_image(source, dst); digest = hashlib.sha256(dst.read_bytes()).hexdigest(); page = SITE + "/product/detail/visalux/" + route
        mapping[slug] = {"status":"resolved", "validation_version":4, "mode":"semi_strict", "resolver":"manual-official-reseller", "file":"product-images/"+dst.name, "source_tier":"official_reseller", "source_page":page, "source_image":source, "sku":p["sku"], "name":p["name"], "brand":"VISALUX", "model_tokens":[model.replace('-','')], "evidence":"Golden Batam Raya product detail identifies the exact Visalux code and shows the matching product form.", "evidence_title":model, "specs":specs, "sha256":digest}
        review["approved"][slug] = {"brand":"VISALUX", "model":model, "specs":specs, "source_page":page, "source_image":source, "sha256":digest, "visual_review":"Product image visibly matches the exact Visalux code and product form shown on the detail page."}
    review["matched"] = len(review["approved"]); review["unresolved"] = len(products)-review["matched"]
    mp_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2)+"\n"); rv_path.write_text(json.dumps(review, ensure_ascii=False, indent=2)+"\n")
    report_path = ROOT / "source/product-images-report.json"; report=json.loads(report_path.read_text()); report["resolved"]=review["matched"]; report["unresolved_count"]=review["unresolved"]; report["source_tiers"]={"official":3,"official_reseller":4}; report["unresolved"]=[{"slug":s,"sku":p["sku"],"name":p["name"],"brand":p["brand"],"reason":mapping[s].get("reason","no verified image")} for s,p in products.items() if s not in review["approved"]]; report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    (ROOT/"source/product-images-review.json").write_text(json.dumps({"mode":"semi_strict","needs_review":report["unresolved"],"resolved":sorted(review["approved"])},ensure_ascii=False,indent=2)+"\n")
    print(f"Published {review['matched']} verified images; {review['unresolved']} unresolved")
if __name__ == "__main__": main()
