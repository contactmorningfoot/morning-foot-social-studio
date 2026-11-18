import os,re,json,hashlib,datetime,io,html
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests,feedparser
from bs4 import BeautifulSoup
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]; DOCS=ROOT/'docs'; ASSETS=DOCS/'assets'; ASSETS.mkdir(parents=True,exist_ok=True)
FEED='https://morning-foot.com/feed/'
S=requests.Session(); S.headers.update({'User-Agent':'MorningFootSocialStudio/2.0 (+https://morning-foot.com)'})
def get(url):
 try:
  r=S.get(url,timeout=22);r.raise_for_status();return r
 except Exception as e: print('FETCH ERROR',url,e);return None
def txt(s):return ' '.join(BeautifulSoup(s or '','html.parser').stripped_strings)
def category(t):
 s=t.lower()
 if any(x in s for x in ['datascout','statistique','chiffre','classement','record','performance']):return 'STATS'
 if any(x in s for x in ['mercato','transfert','recrut','prolong','contrat']):return 'MERCATO'
 if any(x in s for x in ['match','victoire','défaite','but','ligue 1','ligue 2']):return 'MATCH'
 return 'DÉBAT'
def image_candidates(soup):
 body=soup.select_one('.entry-content, .post-content, article .content, .et_pb_post .entry-content, article') or soup
 for img in body.select('img'):
  src=img.get('data-src') or img.get('data-lazy-src') or img.get('src') or ''
  if not src or src.startswith('data:'):continue
  yield urljoin('https://morning-foot.com',src),img

def save_image(url,stem):
 r=get(url)
 if not r:return None
 try:
  im=Image.open(io.BytesIO(r.content));im.load()
  if im.width<320 or im.height<240:return None
  im.thumbnail((1500,1900)); out=ASSETS/(stem+'.jpg'); im.convert('RGB').save(out,quality=86,optimize=True)
  return 'assets/'+out.name
 except Exception as e:print('IMAGE ERROR',e);return None

def parse(entry):
 url=entry.get('link',''); id=hashlib.sha1(url.encode()).hexdigest()[:14]; title=txt(entry.get('title',''))
 page=get(url); soup=BeautifulSoup(page.text,'html.parser') if page else BeautifulSoup('','html.parser')
 article=soup.select_one('.entry-content, .post-content, article .content, .et_pb_post .entry-content, article') or soup
 
 for unwanted in article.select('nav, .breadcrumb, .breadcrumbs, .yoast-breadcrumb, script, style, .sharedaddy, .jp-relatedposts'):
  unwanted.decompose()
 text=txt(str(article))[:5000]; imgs=list(image_candidates(soup)); reports=[]; featured=[]
 for src,tag in imgs:
  desc=(src+' '+tag.get('alt','')).lower(); w=int(tag.get('width','0') or 0);h=int(tag.get('height','0') or 0)
  is_report=bool(re.search(r'(report[-_]|datascout|fiche[-_])',desc))
  if is_report:reports.append(src)
  elif not any(x in desc for x in ['logo','avatar','icon','emoji']):featured.append(src)
 report=reports[0] if reports else None
 image=save_image(report,id+'-report') if report else None
 # Ne pas reutiliser de photos sans verification des droits.
 # Les fiches DataScout autorisees restent les seules images exportables.

 c=category(title+' '+text[:450]); score=0; reasons=[]
 if report:score+=35;reasons.append('Fiche statistique')
 if c=='STATS':score+=20;reasons.append('Statistiques')
 if c=='MERCATO':score+=14;reasons.append('Mercato')
 if any(k in title.lower() for k in ['psg','asse','marseille','lens','lyon','griezmann','mbappé','nantes','lille','monaco']):score+=15;reasons.append('Sujet populaire')
 if any(k in title.lower() for k in ['?', 'record','incroyable','révélation','surprise','explose','pourquoi','combien']):score+=12;reasons.append('Angle de discussion')
 if image:score+=8
 score+=min(10,max(0,len(text)//350))
 score=min(100,score)
 date=entry.get('published_parsed') or entry.get('updated_parsed'); day=datetime.date(*date[:3]).isoformat() if date else datetime.date.today().isoformat()
 hook=title.rstrip(' .!?'); question={'STATS':'Quel chiffre vous impressionne le plus ?','MERCATO':'Ce serait une bonne opération selon vous ?','MATCH':'Vous partagez cette analyse ?','DÉBAT':'Vous êtes d’accord ?'}[c]
 caption=f'{hook}\n\nUne analyse à découvrir sur Morning Foot.\n\n💬 {question}\n\n📊 Visuel : DataScout (si présent). Article complet sur Morning-Foot.com — lien en bio.'
 return {'id':id,'title':title,'url':url,'date':day,'category':c,'score':score,'reasons':reasons,'report':bool(report and image),'image':image,'caption':caption,'question':question,'status':'brouillon'}

def main():
 r=get(FEED)
 if not r:raise SystemExit('RSS inaccessible : aucun changement publié')
 feed=feedparser.parse(r.content)
 if not feed.entries:raise SystemExit('RSS vide')
 previous=[]; p=DOCS/'posts.json'
 if p.exists():
  try:previous=json.loads(p.read_text(encoding='utf8'))
  except:pass
 byurl={p['url']:p for p in previous}
 for e in feed.entries[:25]:
  if e.get('link') not in byurl:
   try:byurl[e.link]=parse(e)
   except Exception as ex:print('ARTICLE ERROR',e.get('link'),ex)
 items=sorted(byurl.values(),key=lambda x:(x['score'],x['date']),reverse=True)[:120]
 # Selection globale par potentiel parmi les articles recents, sans photo non autorisee.
 recent=sorted(items,key=lambda x:x['date'],reverse=True)[:35]
 eligible=sorted((x for x in recent if x.get('report') and x.get('image')),key=lambda x:x['score'],reverse=True)
 chosen={x['id'] for x in eligible[:7] if x['score']>=35}
 for item in items:item['selected']=item['id'] in chosen
 p.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf8')
 print('Posts:',len(items),'Sélectionnés:',sum(x['selected'] for x in items))
if __name__=='__main__':main()
