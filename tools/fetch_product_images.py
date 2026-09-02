#!/usr/bin/env python3
import json,re,sys,time,random,html as htmlmod
from io import BytesIO
from pathlib import Path
from urllib.parse import quote_plus,urlparse,parse_qs,urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image,ImageOps
from rembg import remove,new_session

ROOT=Path(__file__).resolve().parents[1]
PRODUCTS=ROOT/'dist'/'data'/'products.json'
OUT=ROOT/'source'/'product-images'; OUT.mkdir(parents=True,exist_ok=True)
MAP=ROOT/'source'/'product-images.json'; REPORT=ROOT/'source'/'product-images-report.json'
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36','Accept-Language':'id-ID,id;q=0.9,en;q=0.7'})
OFFICIAL={'ECOKING':['ecoking.co.id'],'VISALUX':['visalux.co.id'],'SCHNEIDER':['se.com','schneider-electric.com'],'CHINT':['chintglobal.com','chint.com'],'3M':['3m.co.id','3m.com'],'SIMON':['simon.co.id','simon-electric.com']}
BAD_HOSTS={'facebook.com','instagram.com','pinterest.com','tiktok.com','wikipedia.org','wikimedia.org','yumpu.com'}
PAGE_CACHE={}
VALIDATION_VERSION=2

STOP={'LAMPU','LED','PCS','SET','PUTIH','HITAM','MERAH','BIRU','GREEN','WHITE','BLACK','BULAT','PETAK','VISALUX','ECOKING','SCHNEIDER','CHINT','COSMIC','PIOLINE','SIMON','HIMAWARI','ETERNA','VINITO','SUPREME'}

def norm(s): return re.sub(r'[^A-Z0-9]+',' ',str(s).upper()).strip()
def tokens(s): return [x for x in norm(s).split() if len(x)>1 and x not in STOP]
def model_tokens(p):
    out=[]
    for x in re.findall(r'[A-Z0-9][A-Z0-9._/-]{2,}',str(p['name']).upper()):
        clean=re.sub(r'[^A-Z0-9]','',x)
        if len(clean)>=4 and re.search(r'[A-Z]',clean) and re.search(r'\d',clean): out.append(clean)
    return list(dict.fromkeys(out))

def queries(p):
    brand=p['brand']; mods=model_tokens(p); q=[]
    official=OFFICIAL.get(brand.upper(),[])
    if mods:
        key=' '.join(f'"{m}"' for m in mods[:2])
        for dom in official:q.append(f'site:{dom} "{brand}" {key}')
        q += [f'"{brand}" {key}',f'"{p["name"]}"']
    else:
        for dom in official:q.append(f'site:{dom} "{p["name"]}"')
        q += [f'"{p["name"]}" "{brand}"',f'{brand} {p["name"]}']
    return list(dict.fromkeys(q))

def host_of(u): return (urlparse(u).hostname or '').lower().removeprefix('www.')
def bad_host(host): return any(host==x or host.endswith('.'+x) for x in BAD_HOSTS)
def official_host(host,brand): return any(d in host for d in OFFICIAL.get(brand.upper(),[]))

def google_pages(q,limit=10):
    try:
        r=S.get('https://www.google.com/search',params={'q':q,'num':10,'filter':'0'},timeout=12)
        soup=BeautifulSoup(r.text,'html.parser'); out=[]
        for a in soup.select('a'):
            href=a.get('href','')
            if href.startswith('/url?'):
                href=parse_qs(urlparse(href).query).get('q',[''])[0]
            if href.startswith('http') and 'google.' not in host_of(href) and href not in out:
                out.append(href)
            if len(out)>=limit:break
        return out
    except Exception:return []

def bing_pages(q,limit=10):
    try:
        r=S.get('https://www.bing.com/search',params={'q':q,'count':10},timeout=12)
        soup=BeautifulSoup(r.text,'html.parser'); out=[]
        for a in soup.select('li.b_algo h2 a'):
            u=a.get('href','')
            if u.startswith('http') and u not in out:out.append(u)
            if len(out)>=limit:break
        return out
    except Exception:return []

def bing_image_pages(q,limit=12):
    try:
        r=S.get('https://www.bing.com/images/search',params={'q':q,'form':'HDRSC3'},timeout=12)
        soup=BeautifulSoup(r.text,'html.parser'); out=[]
        for a in soup.select('a.iusc'):
            try:m=json.loads(a.get('m','{}'))
            except Exception:continue
            purl=m.get('purl'); murl=m.get('murl')
            if purl and murl:out.append((purl,murl))
            if len(out)>=limit:break
        return out
    except Exception:return []

def page_info(url):
    if url in PAGE_CACHE:return PAGE_CACHE[url]
    info={'url':url,'host':host_of(url),'text':'','title':'','images':[]}
    if not url.startswith('http') or bad_host(info['host']): PAGE_CACHE[url]=info; return info
    try:
        r=S.get(url,timeout=12,allow_redirects=True)
        if r.status_code!=200 or 'text/html' not in r.headers.get('content-type',''):PAGE_CACHE[url]=info;return info
        soup=BeautifulSoup(r.text,'html.parser')
        title=(soup.title.get_text(' ',strip=True) if soup.title else '')
        desc=' '.join(x.get('content','') for x in soup.select('meta[name="description"],meta[property="og:description"]'))
        for x in soup(['script','style','noscript']):x.decompose()
        body=soup.get_text(' ',strip=True)[:50000]
        text=norm(title+' '+desc+' '+body)
        images=[]
        for sel,attr in [('meta[property="og:image"]','content'),('meta[name="twitter:image"]','content'),('meta[property="twitter:image"]','content')]:
            for tag in soup.select(sel):
                u=tag.get(attr,'')
                if u:images.append(urljoin(r.url,u))
        for img in soup.select('img'):
            u=img.get('data-src') or img.get('data-zoom-image') or img.get('src') or ''
            if u and not u.startswith('data:'):images.append(urljoin(r.url,u))
            if len(images)>=30:break
        info={'url':r.url,'host':host_of(r.url),'text':text,'title':title,'images':list(dict.fromkeys(images))}
    except Exception:pass
    PAGE_CACHE[url]=info;return info

def page_score(info,p):
    text=info['text']; host=info['host']; brand=norm(p['brand']); mods=model_tokens(p); name_terms=tokens(p['name'])
    if bad_host(host):return -999
    score=0
    if official_host(host,p['brand']):score+=90
    if brand and brand in text:score+=35
    exactmods=[m for m in mods if m in text.replace(' ','') or m in norm(info['url']).replace(' ','')]
    score+=65*len(exactmods)
    if norm(p['sku']) and norm(p['sku']) in text:score+=15
    hits=sum(1 for t in name_terms if t in text); coverage=hits/max(1,len(name_terms)); score+=round(45*coverage)
    if mods and not exactmods and not (official_host(host,p['brand']) and coverage>=0.55):return -999
    if not mods and brand not in text and not official_host(host,p['brand']):return -999
    if coverage<0.25 and not exactmods:return -999
    return score

def get_image(url):
    try:
        r=S.get(url,timeout=12,headers={'Referer':'https://www.google.com/'})
        ctype=r.headers.get('content-type','')
        if r.status_code!=200 or len(r.content)<8000 or len(r.content)>15_000_000 or ('image' not in ctype and not re.search(r'\.(png|jpe?g|webp)(\?|$)',url,re.I)):return None
        im=Image.open(BytesIO(r.content));im.load();im=ImageOps.exif_transpose(im).convert('RGBA')
        if min(im.size)<180 or max(im.size)/max(1,min(im.size))>4:return None
        return im
    except Exception:return None

def image_score(im):
    w,h=im.size; score=min(w,h)/10
    ar=max(w,h)/max(1,min(w,h)); score-=max(0,ar-1.8)*60
    return score

def clean(im,session):
    try:
        cut=remove(im,session=session,alpha_matting=False)
        if not isinstance(cut,Image.Image):cut=Image.open(BytesIO(cut)).convert('RGBA')
        cut=cut.convert('RGBA')
    except Exception:cut=im.convert('RGBA')
    bbox=cut.getchannel('A').getbbox() or (0,0,*cut.size);cut=cut.crop(bbox)
    canvas=Image.new('RGB',(1200,1200),'white');scale=min(960/max(1,cut.width),960/max(1,cut.height),1.8)
    nw,nh=max(1,int(cut.width*scale)),max(1,int(cut.height*scale));cut=cut.resize((nw,nh),Image.Resampling.LANCZOS)
    canvas.paste(cut.convert('RGB'),((1200-nw)//2,(1200-nh)//2),cut.getchannel('A'));return canvas

def resolve(p,session):
    pages=[]; direct_images={}
    for qi,q in enumerate(queries(p)):
        gp=google_pages(q); bp=bing_pages(q)
        for rank,u in enumerate(gp+bp):
            if u not in pages:pages.append(u)
        for page,img in bing_image_pages(q):
            if page not in pages:pages.append(page)
            direct_images.setdefault(page,[]).append(img)
        if len(pages)>=12:break
    ranked=[]
    for page in pages[:35]:
        info=page_info(page); sc=page_score(info,p)
        if sc<70:continue
        imgs=list(direct_images.get(page,[]))+info['images']
        ranked.append((sc,info,imgs))
    ranked.sort(reverse=True,key=lambda x:x[0])
    for pscore,info,imgs in ranked[:10]:
        candidates=[]
        for u in imgs[:25]:
            im=get_image(u)
            if im is not None:candidates.append((image_score(im),u,im))
        candidates.sort(reverse=True,key=lambda x:x[0])
        for iscore,u,im in candidates[:4]:
            try:
                clean(im,session).save(OUT/(p['slug']+'.webp'),'WEBP',quality=88,method=6)
                return {'status':'resolved','validation_version':VALIDATION_VERSION,'file':f'product-images/{p["slug"]}.webp','source_page':info['url'],'source_image':u,'page_score':pscore,'image_score':round(iscore,1),'query':queries(p)[0]}
            except Exception:continue
    return {'status':'unresolved','validation_version':VALIDATION_VERSION,'queries':queries(p)}

def main():
    if not PRODUCTS.exists():print('Run build.py first',file=sys.stderr);return 2
    products=json.loads(PRODUCTS.read_text());mapping={}
    if MAP.exists():
        try:mapping=json.loads(MAP.read_text())
        except Exception:mapping={}
    mapping={k:v for k,v in mapping.items() if v.get('status')=='resolved' and v.get('validation_version')==VALIDATION_VERSION and (ROOT/'source'/v.get('file','')).exists()}
    pending=[p for p in products if p['slug'] not in mapping]
    print(f'Validated v{VALIDATION_VERSION}: {len(mapping)} existing, {len(pending)} pending, {len(products)} total',flush=True)
    session=new_session('u2netp')
    for i,p in enumerate(pending,1):
        print(f'[{i}/{len(pending)}] {p["brand"]} | {p["name"]} | {p["sku"]}',flush=True)
        mapping[p['slug']]={**resolve(p,session),'sku':p['sku'],'name':p['name'],'brand':p['brand']}
        MAP.write_text(json.dumps(mapping,ensure_ascii=False,indent=2));time.sleep(random.uniform(.15,.4))
    resolved=sum(mapping.get(p['slug'],{}).get('status')=='resolved' for p in products)
    unresolved=[{'slug':p['slug'],'sku':p['sku'],'name':p['name'],'brand':p['brand']} for p in products if mapping.get(p['slug'],{}).get('status')!='resolved']
    report={'validation_version':VALIDATION_VERSION,'total':len(products),'resolved':resolved,'unresolved_count':len(unresolved),'unresolved':unresolved}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
