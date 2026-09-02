#!/usr/bin/env python3
import json,re,shutil,html
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'; MAP=ROOT/'source'/'product-images.json'; SRC=ROOT/'source'/'product-images'; POLICY=ROOT/'source'/'product-image-policy.json'
if not DIST.exists() or not MAP.exists() or not POLICY.exists(): raise SystemExit(0)
policy=json.loads(POLICY.read_text()); version=int(policy['validation_version']); mode=policy.get('mode','semi_strict'); fallback=policy['rules']['unverified_fallback']
mp=json.loads(MAP.read_text())
resolved={slug:v for slug,v in mp.items() if v.get('status')=='resolved' and v.get('validation_version')==version and (ROOT/'source'/v.get('file','')).exists()}

out=DIST/'assets'/'products'
if out.exists(): shutil.rmtree(out)
out.mkdir(parents=True,exist_ok=True)
for slug,v in resolved.items(): shutil.copy2(ROOT/'source'/v['file'],out/(slug+'.webp'))

def esc(s): return html.escape(str(s),quote=True)
def img_tag(slug,name):
    return f'<img class="catalog-product-image" src="/assets/products/{slug}.webp" alt="{esc(name)}" loading="lazy" decoding="async">'
def placeholder(brand=''):
    label=f'<span class="visual-brand">{esc(brand)}</span>' if brand else ''
    return label+f'<div class="product-image-placeholder"><span>Foto produk</span><strong>sedang diverifikasi</strong></div>'

for page in (DIST/'produk').glob('*/index.html'):
    slug=page.parent.name; t=page.read_text(); v=mp.get(slug,{}); brand=v.get('brand','')
    if slug in resolved:
        inner=f'<span>{esc(brand)}</span>{img_tag(slug,v.get("name","Foto produk"))}'
    else:
        inner=f'<span>{esc(brand)}</span><div class="product-image-placeholder detail"><span>Foto produk</span><strong>sedang diverifikasi</strong><small>Kami menahan gambar yang belum cukup cocok dengan produk ini.</small></div>'
    pat=r'(<div class="product-detail-visual">)(.*?)(</div><div class="product-info">)'
    t,n=re.subn(pat,lambda m:m.group(1)+inner+m.group(3),t,count=1,flags=re.S)
    if n: page.write_text(t)

card_pat=re.compile(r'(<a class="product-visual" href="/produk/([^/]+)/">)(.*?)(</a>)',re.S)
for page in DIST.rglob('*.html'):
    t=page.read_text()
    def card_repl(m):
        slug=m.group(2); v=mp.get(slug,{})
        body=(f'<span class="visual-brand">{esc(v.get("brand",""))}</span>'+img_tag(slug,v.get('name','Foto produk'))) if slug in resolved else placeholder(v.get('brand',''))
        return m.group(1)+body+m.group(4)
    nt=card_pat.sub(card_repl,t)
    if nt!=t: page.write_text(nt)

css=DIST/'assets'/'styles.css'
if css.exists():
    s=css.read_text(); marker='/* SEMI-STRICT PRODUCT IMAGE PIPELINE */'
    s=re.sub(r'/\* (?:STRICT |SEMI-STRICT )?PRODUCT IMAGE PIPELINE \*/.*?(?=/\* (?:STRICT |SEMI-STRICT )?PRODUCT IMAGE PIPELINE \*/|\Z)','',s,flags=re.S)
    s += '''\n/* SEMI-STRICT PRODUCT IMAGE PIPELINE */\n.catalog-product-image{display:block;width:100%;height:100%;object-fit:contain;object-position:center;background:#fff}.product-visual .catalog-product-image{position:absolute;inset:6%;width:88%;height:88%;object-fit:contain}.product-detail-visual .catalog-product-image{width:92%;height:92%;max-height:600px;object-fit:contain;margin:auto}.product-detail-visual:has(.catalog-product-image) svg,.product-detail-visual:has(.catalog-product-image)>small{display:none}.product-image-placeholder{position:absolute;inset:12%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;background:#fff;border:1px dashed rgba(21,23,25,.22);border-radius:18px;color:#6d6f72;padding:18px}.product-image-placeholder span{font-size:.76rem;letter-spacing:.04em;text-transform:uppercase}.product-image-placeholder strong{font-family:inherit;font-size:.98rem;color:#25272a;margin-top:3px}.product-image-placeholder.detail{position:relative;inset:auto;width:82%;min-height:330px;margin:auto}.product-image-placeholder.detail small{display:block!important;max-width:280px;margin-top:10px;line-height:1.45;color:#85878a}.product-visual:has(.product-image-placeholder) svg,.product-visual:has(.product-image-placeholder)>small{display:none}\n'''
    css.write_text(s)
print(f'Applied {len(resolved)} {mode} product images; {max(0,len(mp)-len(resolved))} held for review')
