import os,re,json,hashlib,io,html,datetime,textwrap
from pathlib import Path
from urllib.parse import urlparse
import requests,feedparser
from bs4 import BeautifulSoup
from PIL import Image,ImageDraw,ImageFont,ImageOps,ImageFilter
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'docs'; ASSETS=OUT/'assets'; ASSETS.mkdir(parents=True,exist_ok=True)
RSS=os.environ.get('MF_RSS_URL','https://morning-foot.com/feed/')
MAX=int(os.environ.get('MF_MAX_ARTICLES','120'))
HEAD={'User-Agent':'MorningFootSocialStudio/1.0 (+https://morning-foot.com)'}
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'; REG='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def ft(n,bold=True): return ImageFont.truetype(FONT if bold else REG,n)
def clean(s): return re.sub(r'\s+',' ',BeautifulSoup(html.unescape(s or ''),'html.parser').get_text(' ',strip=True)).strip()
def kind(t,summary):
 s=(t+' '+summary).lower()
 if any(x in s for x in ['classement','statistique','buteur','record','chiffre','top 5','top 10']): return 'stats'
 if any(x in s for x in ['mercato','transfert','recrut','signature','prolong','départ','prêt']): return 'mercato'
 if any(x in s for x in ['victoire','défaite','match','coupe de france','ligue 1','ligue 2','derby']): return 'match'
 return 'debat'
def question(k):
 return {'stats':'QUEL CHIFFRE VOUS SURPREND LE PLUS ?', 'mercato':'BONNE OPÉRATION SELON VOUS ?', 'match':'QUEL EST VOTRE AVIS ?', 'debat':'VOUS ÊTES D’ACCORD ?'}[k]
def wrap(draw,txt,font,maxw,maxlines=4):
 words=txt.split(); lines=[]; line=''
 for w in words:
  trial=(line+' '+w).strip()
  if draw.textbbox((0,0),trial,font=font)[2]<=maxw: line=trial
  else:
   if line: lines.append(line)
   line=w
 if line: lines.append(line)
 if len(lines)>maxlines:
  lines=lines[:maxlines]; lines[-1]=lines[-1].rstrip(' .')+'…'
 return lines
def get_image(entry):
 candidates=[]
 for m in entry.get('media_content',[]): candidates.append(m.get('url',''))
 for m in entry.get('media_thumbnail',[]): candidates.append(m.get('url',''))
 for l in entry.get('links',[]):
  if (l.get('type') or '').startswith('image/'): candidates.append(l.get('href',''))
 soup=BeautifulSoup(entry.get('summary',''),'html.parser')
 for im in soup.select('img'): candidates.append(im.get('src',''))
 for url in candidates:
  if not url.startswith('https://'): continue
  try:
   r=requests.get(url,headers=HEAD,timeout=12);r.raise_for_status()
   if len(r.content)>9_000_000: continue
   im=Image.open(io.BytesIO(r.content));im.verify()
   return Image.open(io.BytesIO(r.content)).convert('RGB')
  except Exception: pass
 return None
def render(title,category,img,out):
 W,H=1080,1350; navy=(6,26,70); yellow=(255,210,0)
 canvas=Image.new('RGB',(W,H),navy);d=ImageDraw.Draw(canvas)
 if img:
  photo=ImageOps.fit(img,(W,840),method=Image.Resampling.LANCZOS,centering=(.5,.32));canvas.paste(photo,(0,0))
  gradient=Image.new('RGBA',(W,840));gd=ImageDraw.Draw(gradient)
  for y in range(840): gd.line((0,y,W,y),fill=(6,26,70,int(240*(y/840)**1.8)))
  canvas=Image.alpha_composite(canvas.convert('RGBA'),Image.new('RGBA',(W,H),(0,0,0,0)))
  canvas.alpha_composite(gradient,(0,0));canvas=canvas.convert('RGB')
 else:
  d=ImageDraw.Draw(canvas)
  for x in range(-500,1200,170): d.line((x,0,x+580,850),fill=(17,41,85),width=3)
 d=ImageDraw.Draw(canvas)
 d.rectangle((0,0,W,15),fill=yellow)
 d.rounded_rectangle((64,58,380,128),radius=12,fill=navy)
 d.text((85,73),'MORNING FOOT',font=ft(32),fill=yellow)
 d.rounded_rectangle((64,670,340,725),radius=8,fill=yellow)
 d.text((84,680),category.upper(),font=ft(26),fill=navy)
 d.rectangle((0,820,W,H),fill=navy)
 f=ft(62);lines=wrap(d,title.upper(),f,952,4)
 while len(lines)>4 and f.size>42: f=ft(f.size-3);lines=wrap(d,title.upper(),f,952,4)
 y=855
 for line in lines: d.text((64,y),line,font=f,fill='white');y+=78
 d.line((64,1190,1016,1190),fill=(58,78,118),width=3)
 d.text((64,1220),question(category),font=ft(28),fill=yellow)
 d.text((64,1305),'MORNING-FOOT.COM',font=ft(19),fill=(180,190,210))
 canvas.save(out,'PNG',optimize=True)
def main():
 r=requests.get(RSS,headers=HEAD,timeout=25);r.raise_for_status(); feed=feedparser.parse(r.content)
 if not feed.entries: raise RuntimeError('Flux RSS vide ou non lisible : '+RSS)
 oldpath=OUT/'posts.json'; old={x['id']:x for x in json.loads(oldpath.read_text(encoding='utf-8'))} if oldpath.exists() else {}
 entries=list(feed.entries)[:MAX]
 for e in entries:
  title=clean(e.get('title',''));url=e.get('link','');summary=clean(e.get('summary',''))[:600]
  if not title or not url: continue
  uid=hashlib.sha256(url.encode()).hexdigest()[:16]
  if uid in old: continue
  k=kind(title,summary);p=ASSETS/f'{uid}.png'
  render(title,k,get_image(e),p)
  desc=(summary[:180].rsplit(' ',1)[0]+'…') if len(summary)>180 else summary
  caption=f'{title}\n\n{desc}\n\n💬 {question(k).capitalize()}\n\n📰 Retrouvez notre analyse sur Morning-Foot.com (lien en bio).'
  old[uid]={'id':uid,'title':title,'url':url,'category':k,'caption':caption,'image':f'assets/{uid}.png','published':e.get('published',''),'status':'brouillon'}
 posts=list(old.values());posts.sort(key=lambda x:x.get('published',''),reverse=True)
 oldpath.write_text(json.dumps(posts[:MAX],ensure_ascii=False,indent=2),encoding='utf-8')
 print(f'{len(posts[:MAX])} brouillons, {len(entries)} entrées RSS')
if __name__=='__main__':main()
