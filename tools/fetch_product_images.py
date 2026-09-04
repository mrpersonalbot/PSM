#!/usr/bin/env python3
import json,re,sys,time,random
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse,parse_qs,urljoin
import requests
from bs4 import BeautifulSoup
from PIL import Image,ImageOps,ImageStat,ImageChops
from rembg import remove,new_session
ROOT=Path(__file__).resolve().parents[1]
PRODUCTS=ROOT/'dist'/'data'/'products.json'; OUT=ROOT/'source'/'product-images'; OUT.mkdir(parents=True,exist_ok=True)
MAP=ROOT/'source'/'product-images.json'; REPORT=ROOT/'source'/'product-images-report.json'; REVIEW=ROOT/'source'/'product-images-review.json'
POLICY=json.loads((ROOT/'source'/'product-image-policy.json').read_text()); MODE=POLICY.get('mode','semi_strict'); VALIDATION_VERSION=int(POLICY['validation_version'])
APPROVED={k.upper():[d.lower() for d in v] for k,v in POLICY.get('approved_sources',{}).items()}; MARKETPLACES=[d.lower() for d in POLICY.get('marketplace_sources',[])]; BLOCKED=[d.lower() for d in POLICY.get('blocked_sources',[])]; RULES=POLICY['rules']
CANVAS_W=int(POLICY['canvas']['width']); CANVAS_H=int(POLICY['canvas']['height']); MAX_COVERAGE=float(POLICY['canvas']['max_product_coverage'])
S=requests.Session(); S.headers.update({'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36','Accept-Language':'id-ID,id;q=0.9,en;q=0.7'}); PAGE_CACHE={}
BRANDS=set(APPROVED)|{'COSMIC','HIMAWARI','ETERNA','VINITO','SUPREME','PIOLINE','SIMON','3M','CHINT','SCHNEIDER','VISALUX','ECOKING'}
STOP={'LAMPU','LED','PCS','SET','PUTIH','HITAM','MERAH','BIRU','GREEN','WHITE','BLACK','BULAT','PETAK','WARNA','TRICOLOUR','DL','WW','RD','SQ'}|BRANDS
UNIQUE_UNITS=re.compile(r'^(?:\d+(?:\.\d+)?(?:W|K|V|A|KA|MM|CM|M|INCH)|\d+X\d+(?:\.\d+)?)$'); BAD_IMAGE_WORDS={'logo','banner','icon','favicon','header','footer','brandmark','placeholder','loading','sprite','catalog-cover','brochure-cover'}
def norm(s): return re.sub(r'[^A-Z0-9]+',' ',str(s).upper()).strip()
def compact(s): return re.sub(r'[^A-Z0-9]','',str(s).upper())
def tokens(s): return [x for x in norm(s).split() if len(x)>1 and x not in STOP]
def domain_match(host,domains): return any(host==d or host.endswith('.'+d) for d in domains)
def host_of(u): return (urlparse(u).hostname or '').lower().removeprefix('www.')
def approved_domains(brand): return APPROVED.get(str(brand).upper(),[])
def host_is_approved(host,brand): return domain_match(host,approved_domains(brand))
def source_tier(host,brand):
    if host_is_approved(host,brand): return 'official'
    if domain_match(host,BLOCKED): return 'blocked'
    if domain_match(host,MARKETPLACES): return 'marketplace'
    return 'independent'
def model_tokens(p):
    out=[]
    for raw in re.findall(r'[A-Z0-9][A-Z0-9._/-]{2,}',str(p['name']).upper()):
        c=compact(raw)
        if len(c)<4 or not re.search(r'[A-Z]',c) or not re.search(r'\d',c) or UNIQUE_UNITS.match(c): continue
        out.append(c)
    return list(dict.fromkeys(out))
def search_queries(p):
    brand=str(p['brand']).upper(); mods=model_tokens(p); name=p['name']; out=[]
    for dom in approved_domains(brand):
        if mods:
            for m in mods[:3]: out.append(f'site:{dom} "{m}"')
        out.append(f'site:{dom} "{name}"')
    if mods:
        for m in mods[:3]: out += [f'"{brand}" "{m}"',f'"{brand}" "{m}" product']
    out += [f'"{name}"',f'"{brand}" '+' '.join(tokens(name)[:9]),f'"{brand}" "{name}"']
    return list(dict.fromkeys(q for q in out if q.strip()))[:12]
def extract_links(soup,selector):
    out=[]
    for a in soup.select(selector):
        u=a.get('href','')
        if u.startswith('/url?'): u=parse_qs(urlparse(u).query).get('q',[''])[0]
        if u.startswith('http') and 'google.' not in host_of(u) and u not in out: out.append(u)
    return out
def google_pages(q,limit=12):
    try:return extract_links(BeautifulSoup(S.get('https://www.google.com/search',params={'q':q,'num':20,'filter':'0'},timeout=15).text,'html.parser'),'a')[:limit]
    except Exception:return []
def bing_pages(q,limit=12):
    try:return extract_links(BeautifulSoup(S.get('https://www.bing.com/search',params={'q':q,'count':20},timeout=15).text,'html.parser'),'li.b_algo h2 a')[:limit]
    except Exception:return []
def duck_pages(q,limit=12):
    try:return extract_links(BeautifulSoup(S.get('https://html.duckduckgo.com/html/',params={'q':q},timeout=15).text,'html.parser'),'a.result__a')[:limit]
    except Exception:return []
def bing_image_pages(q,limit=16):
    try:
        soup=BeautifulSoup(S.get('https://www.bing.com/images/search',params={'q':q},timeout=15).text,'html.parser'); out=[]
        for a in soup.select('a.iusc'):
            try:m=json.loads(a.get('m','{}'))
            except Exception: continue
            if m.get('purl') and m.get('murl'): out.append((m['purl'],m['murl']))
            if len(out)>=limit: break
        return out
    except Exception:return []
def page_info(url):
    if url in PAGE_CACHE:return PAGE_CACHE[url]
    info={'url':url,'host':host_of(url),'text':'','title':'','images':[]}
    try:
        r=S.get(url,timeout=16,allow_redirects=True); info['url']=r.url; info['host']=host_of(r.url)
        if r.status_code!=200 or 'text/html' not in r.headers.get('content-type',''): PAGE_CACHE[url]=info; return info
        soup=BeautifulSoup(r.text,'html.parser'); title=soup.title.get_text(' ',strip=True) if soup.title else ''
        desc=' '.join(x.get('content','') for x in soup.select('meta[name="description"],meta[property="og:description"]'))
        images=[]
        for sel,attr,kind in [('meta[property="og:image"]','content','og'),('meta[name="twitter:image"]','content','twitter')]:
            for tag in soup.select(sel):
                u=tag.get(attr,'');
                if u: images.append({'url':urljoin(r.url,u),'meta':'','kind':kind})
        for tag in soup.select('script[type="application/ld+json"]'):
            try:
                data=json.loads(tag.string or tag.get_text() or '{}'); stack=data if isinstance(data,list) else [data]
                for d in stack:
                    if not isinstance(d,dict): continue
                    imgs=d.get('image') or d.get('contentUrl')
                    if isinstance(imgs,str): imgs=[imgs]
                    if isinstance(imgs,list):
                        for u in imgs:
                            if isinstance(u,str): images.append({'url':urljoin(r.url,u),'meta':'jsonld','kind':'jsonld'})
            except Exception: pass
        for img in soup.select('img'):
            u=img.get('data-zoom-image') or img.get('data-src') or img.get('src') or ''
            if not u or u.startswith('data:'): continue
            meta=' '.join([img.get('alt',''),img.get('title',''),' '.join(img.get('class',[])) if isinstance(img.get('class'),list) else str(img.get('class',''))])
            images.append({'url':urljoin(r.url,u),'meta':meta,'kind':'img'})
            if len(images)>=80: break
        for x in soup(['script','style','noscript']): x.decompose()
        body=soup.get_text(' ',strip=True)[:90000]
        info={'url':r.url,'host':info['host'],'text':norm(title+' '+desc+' '+body),'title':norm(title),'images':images}
    except Exception: pass
    PAGE_CACHE[url]=info; return info
def page_validation(info,p):
    brand=str(p['brand']).upper(); host=info['host']; tier=source_tier(host,brand); text=info['text']; title=info['title']; mods=model_tokens(p); terms=tokens(p['name'])
    if tier=='blocked': return False,'blocked_source',0,tier
    if not text: return False,'empty_page',0,tier
    ctext=compact(text+' '+info['url']); ctitle=compact(title); exactmods=[m for m in mods if m in ctext]; brand_match=(brand in text) or host_is_approved(host,brand); coverage=sum(1 for t in terms if t in text)/max(1,len(terms)); title_cov=sum(1 for t in terms if t in title)/max(1,len(terms))
    if not brand_match:return False,'brand_mismatch',0,tier
    if tier=='official':
        if mods and not exactmods:return False,'model_not_found',0,tier
        if mods and coverage<0.20:return False,'weak_name_match',0,tier
        if not mods and coverage<0.40:return False,'weak_name_match',0,tier
        return True,'ok',260+80*len(exactmods)+round(coverage*100),tier
    if tier=='marketplace':
        if not RULES.get('allow_marketplace_with_exact_model',False) or not mods or not exactmods:return False,'marketplace_requires_exact_model',0,tier
        if brand not in title or not any(m in ctitle for m in mods):return False,'marketplace_title_mismatch',0,tier
        if coverage<float(RULES.get('marketplace_min_name_coverage',0.50)):return False,'weak_name_match',0,tier
        return True,'ok',145+90*len(exactmods)+round(coverage*70),tier
    if not RULES.get('allow_independent_product_pages',False):return False,'independent_disabled',0,tier
    if mods:
        if not exactmods:return False,'model_not_found',0,tier
        if coverage<float(RULES.get('independent_min_name_coverage_with_model',0.40)):return False,'weak_name_match',0,tier
        if brand not in title and title_cov<0.35:return False,'weak_product_title',0,tier
        return True,'ok',175+90*len(exactmods)+round(coverage*80),tier
    if coverage<float(RULES.get('independent_min_name_coverage_without_model',0.78)):return False,'weak_name_match',0,tier
    if brand not in title or title_cov<0.55:return False,'weak_product_title',0,tier
    return True,'ok',155+round(coverage*90)+round(title_cov*50),tier
def near_white_background(im):
    rgb=im.convert('RGB');w,h=rgb.size;s=max(6,min(w,h)//12);good=0
    for b in [(0,0,s,s),(w-s,0,w,s),(0,h-s,s,h),(w-s,h-s,w,h)]:
        m=ImageStat.Stat(rgb.crop(b)).mean
        if min(m)>238 and max(m)-min(m)<14:good+=1
    return good>=3
def white_foreground_bbox(im): return ImageChops.difference(im.convert('RGB'),Image.new('RGB',im.size,'white')).convert('L').point(lambda p:255 if p>18 else 0).getbbox()
def bbox_touches_edge(bbox,size,margin_ratio=.012):
    if not bbox:return True
    w,h=size;x0,y0,x1,y1=bbox;mx=max(2,int(w*margin_ratio));my=max(2,int(h*margin_ratio));return x0<=mx or y0<=my or x1>=w-mx or y1>=h-my
def download_image(url,referer):
    try:
        r=S.get(url,timeout=18,headers={'Referer':referer});
        if r.status_code!=200 or len(r.content)<6000 or len(r.content)>18_000_000:return None
        im=Image.open(BytesIO(r.content));im.load();im=ImageOps.exif_transpose(im).convert('RGBA')
        if min(im.size)<220 or max(im.size)/max(1,min(im.size))>4.2:return None
        return im
    except Exception:return None
def source_image_score(entry,im,p,tier):
    meta=(entry.get('url','')+' '+entry.get('meta','')).lower();cm=compact(meta);mods=model_tokens(p)
    if any(x in meta for x in BAD_IMAGE_WORDS):return -999
    score=min(im.size)/8; score+=100*sum(1 for m in mods if m in cm); score+=sum(8 for t in tokens(p['name']) if t.lower() in meta)
    if entry.get('kind') in {'og','jsonld'}:score+=45
    if tier=='official':score+=50
    if tier=='marketplace' and mods and not any(m in cm for m in mods) and entry.get('kind') not in {'og','jsonld'}:return -999
    ar=max(im.size)/max(1,min(im.size)); return score-max(0,ar-2.2)*100
def normalize_product(im,session):
    original=im.convert('RGBA')
    if near_white_background(original):
        bbox=white_foreground_bbox(original)
        if bbox_touches_edge(bbox,original.size):return None,'source_object_touches_edge'
        cut=original.crop(bbox);working=Image.new('RGBA',cut.size,(255,255,255,255));working.alpha_composite(cut)
    else:
        try:
            removed=remove(original,session=session,alpha_matting=False);cut=removed if isinstance(removed,Image.Image) else Image.open(BytesIO(removed)).convert('RGBA');cut=cut.convert('RGBA');bbox=cut.getchannel('A').getbbox()
            if bbox_touches_edge(bbox,cut.size):return None,'segmented_object_touches_edge'
            if not bbox:return None,'empty_segmentation'
            working=cut.crop(bbox)
        except Exception:return None,'background_removal_failed'
    if working.width<20 or working.height<20:return None,'object_too_small'
    tw=int(CANVAS_W*MAX_COVERAGE);th=int(CANVAS_H*MAX_COVERAGE);scale=min(tw/working.width,th/working.height,2.0);nw=max(1,int(working.width*scale));nh=max(1,int(working.height*scale));working=working.resize((nw,nh),Image.Resampling.LANCZOS)
    canvas=Image.new('RGB',(CANVAS_W,CANVAS_H),'white');canvas.paste(working.convert('RGB'),((CANVAS_W-nw)//2,(CANVAS_H-nh)//2),working.getchannel('A') if working.mode=='RGBA' else None);return canvas,'ok'
def resolve(p,session):
    pages=[];direct={};queries=search_queries(p)
    for q in queries:
        found=[]
        for u in google_pages(q)+bing_pages(q)+duck_pages(q):
            if source_tier(host_of(u),p['brand'])!='blocked' and u not in found:found.append(u)
        for page,img in bing_image_pages(q):
            if source_tier(host_of(page),p['brand'])!='blocked':
                if page not in found:found.append(page)
                direct.setdefault(page,[]).append({'url':img,'meta':q,'kind':'image_search'})
        for u in found:
            if u not in pages:pages.append(u)
        if len(pages)>=60:break
    ranked=[];reject=[]
    for page in pages[:70]:
        info=page_info(page);ok,reason,score,tier=page_validation(info,p)
        if ok:ranked.append((score,info,tier))
        else:reject.append({'page':page,'reason':reason,'tier':tier})
    ranked.sort(reverse=True,key=lambda x:x[0]);image_rejections=[]
    for pscore,info,tier in ranked[:18]:
        entries=list(direct.get(info['url'],[]))+info['images'];candidates=[]
        for entry in entries[:100]:
            im=download_image(entry['url'],info['url'])
            if im is None:continue
            sc=source_image_score(entry,im,p,tier)
            if sc>-500:candidates.append((sc,entry,im))
        candidates.sort(reverse=True,key=lambda x:x[0])
        for iscore,entry,im in candidates[:15]:
            normalized,reason=normalize_product(im,session)
            if normalized is None:image_rejections.append({'image':entry['url'],'reason':reason});continue
            path=OUT/(p['slug']+'.webp');normalized.save(path,'WEBP',quality=90,method=6)
            return {'status':'resolved','validation_version':VALIDATION_VERSION,'mode':MODE,'file':f'product-images/{p["slug"]}.webp','source_tier':tier,'source_page':info['url'],'source_image':entry['url'],'page_score':pscore,'image_score':round(iscore,1),'model_tokens':model_tokens(p),'query':queries[0] if queries else ''}
    return {'status':'unresolved','validation_version':VALIDATION_VERSION,'mode':MODE,'reason':'no_validated_page' if not ranked else 'no_uncropped_valid_image','queries':queries,'page_rejections':reject[:20],'image_rejections':image_rejections[:20]}
def main():
    if not PRODUCTS.exists():print('Run build.py first',file=sys.stderr);return 2
    products=json.loads(PRODUCTS.read_text());old={}
    if MAP.exists():
        try:old=json.loads(MAP.read_text())
        except Exception:old={}
    mapping={k:v for k,v in old.items() if v.get('status')=='resolved' and v.get('validation_version')==VALIDATION_VERSION and (ROOT/'source'/v.get('file','')).exists()};referenced={Path(v['file']).name for v in mapping.values() if v.get('file')}
    for f in OUT.glob('*.webp'):
        if f.name not in referenced:f.unlink()
    pending=[p for p in products if p['slug'] not in mapping];print(f'{MODE} v{VALIDATION_VERSION}: {len(mapping)} validated, {len(pending)} pending, {len(products)} total',flush=True);session=new_session('u2netp')
    for i,p in enumerate(pending,1):
        print(f'[{i}/{len(pending)}] {p["brand"]} | {p["name"]} | {p["sku"]}',flush=True);mapping[p['slug']]={**resolve(p,session),'sku':p['sku'],'name':p['name'],'brand':p['brand']};MAP.write_text(json.dumps(mapping,ensure_ascii=False,indent=2));time.sleep(random.uniform(.08,.18))
    resolved=sum(mapping.get(p['slug'],{}).get('status')=='resolved' for p in products);unresolved=[];tiers={}
    for p in products:
        v=mapping.get(p['slug'],{})
        if v.get('status')!='resolved':unresolved.append({'slug':p['slug'],'sku':p['sku'],'name':p['name'],'brand':p['brand'],'reason':v.get('reason','unresolved')})
        else:tiers[v.get('source_tier','unknown')]=tiers.get(v.get('source_tier','unknown'),0)+1
    report={'validation_version':VALIDATION_VERSION,'mode':MODE,'total':len(products),'resolved':resolved,'unresolved_count':len(unresolved),'source_tiers':tiers,'unresolved':unresolved};REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2));REVIEW.write_text(json.dumps({'mode':MODE,'needs_review':unresolved},ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
