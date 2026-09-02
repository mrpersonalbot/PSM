#!/usr/bin/env python3
import json,re,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'; MAP=ROOT/'source'/'product-images.json'; SRC=ROOT/'source'/'product-images'
if not DIST.exists() or not MAP.exists() or not SRC.exists():
    raise SystemExit(0)
mp=json.loads(MAP.read_text())
resolved={slug:v for slug,v in mp.items() if v.get('status')=='resolved' and (ROOT/'source'/v.get('file','')).exists()}
if not resolved: raise SystemExit(0)
out=DIST/'assets'/'products'; out.mkdir(parents=True,exist_ok=True)
for slug,v in resolved.items():
    src=ROOT/'source'/v['file']; shutil.copy2(src,out/(slug+'.webp'))

def img_tag(slug,name='Foto produk'):
    safe=name.replace('&','&amp;').replace('"','&quot;').replace('<','&lt;').replace('>','&gt;')
    return f'<img class="catalog-product-image" src="/assets/products/{slug}.webp" alt="{safe}" loading="lazy" decoding="async">'

for page in (DIST/'produk').glob('*/index.html'):
    slug=page.parent.name
    if slug not in resolved: continue
    t=page.read_text()
    pat=r'(<div class="product-detail-visual">)(.*?)(</div><div class="product-info">)'
    v=resolved[slug]
    repl=r'\1'+f'<span>{v.get("brand","")}</span>{img_tag(slug,v.get("name","Foto produk"))}'+r'\3'
    t,n=re.subn(pat,repl,t,count=1,flags=re.S)
    if n: page.write_text(t)

card_pat=re.compile(r'(<a class="product-visual" href="/produk/([^/]+)/">)(.*?)(</a>)',re.S)
for page in DIST.rglob('*.html'):
    t=page.read_text()
    def card_repl(m):
        slug=m.group(2)
        if slug not in resolved: return m.group(0)
        v=resolved[slug]
        return m.group(1)+f'<span class="visual-brand">{v.get("brand","")}</span>'+img_tag(slug,v.get('name','Foto produk'))+m.group(4)
    nt=card_pat.sub(card_repl,t)
    if nt!=t: page.write_text(nt)

css=DIST/'assets'/'styles.css'
if css.exists():
    s=css.read_text(); marker='/* PRODUCT IMAGE PIPELINE */'
    if marker not in s:
        s += '''\n/* PRODUCT IMAGE PIPELINE */\n.catalog-product-image{display:block;width:100%;height:100%;object-fit:contain;object-position:center;background:#fff}.product-visual .catalog-product-image{position:absolute;inset:12%;width:76%;height:76%;object-fit:contain}.product-detail-visual .catalog-product-image{width:82%;height:82%;max-height:560px;object-fit:contain;margin:auto}.product-detail-visual:has(.catalog-product-image) svg,.product-detail-visual:has(.catalog-product-image) small{display:none}\n'''
        css.write_text(s)
print(f'Applied {len(resolved)} product images')
