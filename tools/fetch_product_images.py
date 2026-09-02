#!/usr/bin/env python3
import json,re,sys,time,random,html as htmlmod
from io import BytesIO
from pathlib import Path
from urllib.parse import quote_plus,urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image,ImageOps
from rembg import remove,new_session

ROOT=Path(__file__).resolve().parents[1]
PRODUCTS=ROOT/'dist'/'data'/'products.json'
OUT=ROOT/'source'/'product-images'; OUT.mkdir(parents=True,exist_ok=True)
MAP=ROOT/'source'/'product-images.json'; REPORT=ROOT/'source'/'product-images-report.json'
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36','Accept-Language':'id-ID,id;q=0.9,en;q=0.7'})
OFFICIAL={'ECOKING':'ecoking.co.id','VISALUX':'visalux.co.id','SCHNEIDER':'se.com','CHINT':'chintglobal.com','3M':'3m.co.id','SIMON':'simon.co.id'}
BLOCKED={'facebook.com','instagram.com','pinterest.com','tiktok.com'}

def terms(text):
    text=re.sub(r'[^A-Za-z0-9]+',' ',str(text).upper())
    stop={'LAMPU','LED','PCS','SET','PUTIH','HITAM','MERAH','BIRU','GREEN','WHITE','BLACK'}
    return [x for x in text.split() if len(x)>1 and x not in stop]

def queries(p):
    name,brand,sku=p['name'],p['brand'],p['sku']; exact=f'"{name}" "{brand}"'
    if sku and len(str(sku))>=3: exact+=f' "{sku}"'
    q=[]; dom=OFFICIAL.get(brand.upper())
    if dom:q.append(f'site:{dom} {exact}')
    q += [exact,f'{name} {brand} product',f'{brand} {name}']
    compact=' '.join(name.split()[:8])
    if compact!=name:q.append(f'{brand} {compact}')
    return list(dict.fromkeys(q))

def google(q,limit=12):
    try:
        r=S.get('https://www.google.com/search?tbm=isch&safe=active&q='+quote_plus(q),timeout=20)
        if r.status_code!=200:return []
        txt=htmlmod.unescape(r.text); out=[]
        for pat in [r'"ou":"(https?://[^"\\]+)',r'\["(https?://[^"\\]+\.(?:jpg|jpeg|png|webp)(?:\?[^"\\]*)?)"']:
            for m in re.findall(pat,txt,re.I):
                u=m.replace('\\u003d','=').replace('\\u0026','&').replace('\\/','/')
                if u not in out:out.append(u)
                if len(out)>=limit:return out
        return out
    except Exception:return []

def bing(q,limit=15):
    try:
        r=S.get('https://www.bing.com/images/search',params={'q':q,'form':'HDRSC3'},timeout=20)
        soup=BeautifulSoup(r.text,'html.parser'); out=[]
        for a in soup.select('a.iusc'):
            try:m=json.loads(a.get('m','{}'))
            except Exception:continue
            if m.get('murl'):out.append((m['murl'],m.get('purl','')))
            if len(out)>=limit:break
        return out
    except Exception:return []

def ddg(q,limit=15):
    try:
        first=S.get('https://duckduckgo.com/',params={'q':q},timeout=20)
        m=re.search(r'vqd=["\']?([\d-]+)',first.text)
        if not m:return []
        r=S.get('https://duckduckgo.com/i.js',params={'l':'wt-wt','o':'json','q':q,'vqd':m.group(1),'f':',,,','p':'1'},headers={'Referer':'https://duckduckgo.com/'},timeout=20)
        return [(x.get('image'),x.get('url','')) for x in r.json().get('results',[])[:limit] if x.get('image')]
    except Exception:return []

def source_score(img,page,p,rank):
    score=100-rank*2; host=(urlparse(page or img).hostname or '').lower()
    if any(host.endswith(x) for x in BLOCKED):score-=45
    official=OFFICIAL.get(p['brand'].upper())
    if official and official in host:score+=80
    blob=(img+' '+page).upper(); score+=min(45,sum(5 for t in terms(p['name'])+terms(p['sku']) if t in blob))
    if any(x in blob.lower() for x in ['logo','banner','poster','catalog','brosur']):score-=20
    return score

def get_image(url):
    try:
        r=S.get(url,timeout=25,headers={'Referer':'https://www.google.com/'})
        if r.status_code!=200 or len(r.content)<8000 or len(r.content)>15_000_000:return None
        im=Image.open(BytesIO(r.content)); im.load(); im=ImageOps.exif_transpose(im).convert('RGBA')
        if min(im.size)<180 or max(im.size)/max(1,min(im.size))>3.8:return None
        return im
    except Exception:return None

def clean(im,session):
    try:
        cut=remove(im,session=session,alpha_matting=False)
        if not isinstance(cut,Image.Image):cut=Image.open(BytesIO(cut)).convert('RGBA')
        cut=cut.convert('RGBA')
    except Exception:cut=im.convert('RGBA')
    bbox=cut.getchannel('A').getbbox() or (0,0,*cut.size); cut=cut.crop(bbox)
    canvas=Image.new('RGB',(1200,1200),'white'); scale=min(960/max(1,cut.width),960/max(1,cut.height),1.8)
    nw,nh=max(1,int(cut.width*scale)),max(1,int(cut.height*scale)); cut=cut.resize((nw,nh),Image.Resampling.LANCZOS)
    canvas.paste(cut.convert('RGB'),((1200-nw)//2,(1200-nh)//2),cut.getchannel('A'))
    return canvas

def resolve(p,session):
    cand=[]
    for qi,q in enumerate(queries(p)):
        for rank,u in enumerate(google(q)):cand.append((source_score(u,'',p,rank)-qi*4,u,'','google',q))
        if len(cand)<5:
            for rank,(u,page) in enumerate(bing(q)):cand.append((source_score(u,page,p,rank)-qi*5,u,page,'bing',q))
        if len(cand)<5:
            for rank,(u,page) in enumerate(ddg(q)):cand.append((source_score(u,page,p,rank)-qi*6,u,page,'duckduckgo',q))
        if cand:break
        time.sleep(random.uniform(.35,.8))
    cand.sort(reverse=True,key=lambda x:x[0]); tried=set()
    for score,u,page,engine,q in cand[:20]:
        if not u or u in tried:continue
        tried.add(u); im=get_image(u)
        if im is None:continue
        try:
            clean(im,session).save(OUT/(p['slug']+'.webp'),'WEBP',quality=88,method=6)
            return {'status':'resolved','file':f'product-images/{p["slug"]}.webp','engine':engine,'source_image':u,'source_page':page,'query':q,'score':score}
        except Exception:continue
    return {'status':'unresolved','queries':queries(p)}

def main():
    if not PRODUCTS.exists():print('Run build.py first',file=sys.stderr);return 2
    products=json.loads(PRODUCTS.read_text()); mapping={}
    if MAP.exists():
        try:mapping=json.loads(MAP.read_text())
        except Exception:mapping={}
    mapping={k:v for k,v in mapping.items() if v.get('status')=='resolved' and (ROOT/'source'/v.get('file','')).exists()}
    pending=[p for p in products if p['slug'] not in mapping]
    print(f'{len(mapping)} existing, {len(pending)} pending, {len(products)} total',flush=True)
    session=new_session('u2netp')
    for i,p in enumerate(pending,1):
        print(f'[{i}/{len(pending)}] {p["brand"]} | {p["name"]} | {p["sku"]}',flush=True)
        mapping[p['slug']]={**resolve(p,session),'sku':p['sku'],'name':p['name'],'brand':p['brand']}
        MAP.write_text(json.dumps(mapping,ensure_ascii=False,indent=2)); time.sleep(random.uniform(.25,.65))
    resolved=sum(mapping.get(p['slug'],{}).get('status')=='resolved' for p in products)
    unresolved=[{'slug':p['slug'],'sku':p['sku'],'name':p['name'],'brand':p['brand']} for p in products if mapping.get(p['slug'],{}).get('status')!='resolved']
    report={'total':len(products),'resolved':resolved,'unresolved_count':len(unresolved),'unresolved':unresolved}; REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False)); return 0
if __name__=='__main__':raise SystemExit(main())
