from pathlib import Path
import json,subprocess,concurrent.futures,io,hashlib
from PIL import Image,ImageDraw,ImageStat
OUT=Path(__file__).parent;FF=str(Path('tools/ffmpeg/bin/ffmpeg.exe').resolve())
rows=[r for r in json.loads((OUT/'inventory.json').read_text(encoding='utf-8')) if r['role']=='video' and r['probe']]
def frame(row):
 d=float(row['probe']['format'].get('duration',0));t=max(0,d/2)
 cmd=[FF,'-nostdin','-v','error','-hwaccel','none','-threads','1','-ss',str(t),'-i',row['path'],'-map','0:v:0','-frames:v','1','-vf','scale=160:90','-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1']
 try:
  p=subprocess.run(cmd,capture_output=True,timeout=20)
  if p.returncode or len(p.stdout)!=160*90*3:return {'path':row['path'],'error':p.stderr.decode('utf-8','replace')[:500]},None
  im=Image.frombytes('RGB',(160,90),p.stdout);gray=im.convert('L');a=list(gray.resize((9,8)).getdata());bits=[a[y*9+x]>a[y*9+x+1] for y in range(8) for x in range(8)];h=sum(int(b)<<i for i,b in enumerate(bits));stat=ImageStat.Stat(gray)
  return {'path':row['path'],'sample_second':t,'dhash':f'{h:016x}','sample_pixel_sha256':hashlib.sha256(p.stdout).hexdigest(),'mean_luma_sample':stat.mean[0],'luma_std_sample':stat.stddev[0]},im
 except Exception as e:return {'path':row['path'],'error':type(e).__name__},None
results=[];images=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for i,(r,im) in enumerate(pool.map(frame,rows)):
  r['inventory_index']=i;results.append(r);images.append(im)
  if (i+1)%100==0:print('sampled',i+1,flush=True)
(OUT/'video-samples.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
# Overview is inspection evidence, not generated media; original files untouched.
for batch in range((len(rows)+79)//80):
 ids=list(range(batch*80,min((batch+1)*80,len(rows))));sheet=Image.new('RGB',(1000, len(range(0,len(ids),5))*115),'#222222');draw=ImageDraw.Draw(sheet)
 for k,i in enumerate(ids):
  x=(k%5)*200;y=(k//5)*115
  if images[i]:sheet.paste(images[i],(x,y))
  draw.text((x,y+91),str(i)+' '+Path(rows[i]['path']).name[:24],fill='white')
 sheet.save(OUT/f'overview-{batch}.jpg')
print('Done sample frames',len(results),flush=True)
