"""Deterministic 240px Ball design previews; sample data, not firmware captures."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import json
OUT=Path(__file__).resolve().parent
BG='#090f11'; PANEL='#191d29'; BLUE='#00b4ff'; WHITE='#f4f5fa'; MUTED='#a6b1c4'
FONT=Path('C:/Windows/Fonts')
def font(size,bold=False): return ImageFont.truetype(str(FONT/('segoeuib.ttf' if bold else 'segoeui.ttf')),size)
checks=[]
def page():
 im=Image.new('RGB',(240,240),'#000000'); d=ImageDraw.Draw(im)
 d.ellipse((1,1,238,238),fill=BG,outline='#34404b')
 return im,d
def text(d,s,x,y,size,color=WHITE,align='center',bold=False):
 f=font(size,bold); b=d.textbbox((0,0),s,font=f); w=b[2]-b[0];h=b[3]-b[1]
 left=x-w/2 if align=='center' else x-w if align=='right' else x
 top=y
 # Validate all four text-rectangle corners against a 115px safe circle.
 for px in (left,left+w):
  for py in (top,top+h):
   assert (px-120)**2+(py-120)**2 <= 115**2, (s,px,py)
 checks.append({'text':s,'bounds':[left,top,left+w,top+h]})
 d.text((left-b[0],top-b[1]),s,font=f,fill=color)
def base(d):
 text(d,'CodexMeter',120,20,15,BLUE)
 d.ellipse((176,24,181,29),fill='#56cba0')
def dots(d,n):
 for i in range(3):
  x=106+i*14;d.ellipse((x-2,220,x+2,224),fill=BLUE if i==n else '#435062')
im,d=page();base(d)
text(d,'Weekly remaining',120,45,14,MUTED)
text(d,'69%',120,66,49,bold=True)
text(d,'Reset 3d 4h',120,125,16)
d.line((43,153,197,153),fill='#354050')
for x,label,value,color in [(65,'Running','2',BLUE),(120,'Waiting','1','#ffd44c'),(175,'Done','5','#4edb8d')]:
 text(d,value,x,164,25,color,bold=True);text(d,label,x,189,12,MUTED)
dots(d,0);im.save(OUT/'01-quota-tasks.png')
for n,title,values,costs in [(1,'Today',['1.2M','8.4M','400K','10M'],['$2.40','$0.84','$4.00','$7.24']), (2,'7 days',['8.4M','58.8M','2.8M','70M'],['$16.80','$5.88','$28.00','$50.68'])]:
 im,d=page();base(d);text(d,title,120,43,22,bold=True)
 text(d,'Tokens',143,73,12,MUTED,align='right');text(d,'USD',211,73,12,MUTED,align='right')
 for i,(label,value,cost) in enumerate(zip(['Input (new)','Cached','Output','Total'],values,costs)):
  y=96+i*25
  if i==3:d.line((29,163,211,163),fill='#354050')
  text(d,label,28,y,12 if i<3 else 14,MUTED if i<3 else WHITE,align='left',bold=i==3)
  text(d,value,145,y,14,align='right',bold=i==3)
  text(d,cost,212,y,14,align='right',bold=i==3)
 text(d,'API cost estimate',120,201,12,MUTED)
 dots(d,n);im.save(OUT/('02-today.png' if n==1 else '03-seven-days.png'))
(OUT/'bounds-check.json').write_text(json.dumps({'size':[240,240],'safe_radius':115,'text_rectangles_checked':len(checks)},indent=2))
print('Rendered three 240x240 images;',len(checks),'text rectangles inside safe circle.')