from pathlib import Path
import subprocess,json,hashlib,numpy as np
from PIL import Image,ImageDraw
OUT=Path(__file__).parent;FF=str(Path('tools/ffmpeg/bin/ffmpeg.exe').resolve());FP=str(Path('tools/ffmpeg/bin/ffprobe.exe').resolve())
allrows=json.loads((OUT/'inventory.json').read_text(encoding='utf-8'));videos=[r for r in allrows if r['role']=='video'];ids=[0,191,85,101,135,143];reports=[]
for num,i in enumerate(ids):
 r=videos[i];path=r['path'];duration=float(r['probe']['format']['duration'])
 cmd=[FF,'-nostdin','-v','error','-xerror','-hwaccel','none','-threads','1','-i',path,'-map','0:v:0','-map','0:a?','-f','null','-']
 p=subprocess.run(cmd,capture_output=True,timeout=120)
 q=subprocess.run([FP,'-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',path],capture_output=True,timeout=60)
 frames=json.loads(q.stdout)['frames'];pts=[float(f['best_effort_timestamp_time']) for f in frames if 'best_effort_timestamp_time' in f];delta=np.diff(pts)
 sheet=Image.new('RGB',(5*256,170),'#222222');draw=ImageDraw.Draw(sheet)
 for k,frac in enumerate((.05,.25,.5,.75,.95)):
  t=duration*frac
  z=subprocess.run([FF,'-nostdin','-v','error','-hwaccel','none','-threads','1','-ss',str(t),'-i',path,'-map','0:v:0','-frames:v','1','-vf','scale=256:144','-threads','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],capture_output=True,timeout=25)
  assert z.returncode==0 and len(z.stdout)==256*144*3
  sheet.paste(Image.frombytes('RGB',(256,144),z.stdout),(k*256,0));draw.text((k*256,146),f'{t:.3f}s',fill='white')
 sheet.save(OUT/f'V{num+1:02d}-frames.jpg')
 reports.append({'id':f'V{num+1:02d}','inventory_index':i,'path':path,'sha256':r['sha256'],'decode_exit':p.returncode,'decode_stderr':p.stderr.decode('utf-8','replace'),'video_frame_count':len(frames),'pts_count':len(pts),'pts_monotonic':bool(np.all(delta>0)),'pts_delta_min_s':float(delta.min()),'pts_delta_max_s':float(delta.max()),'pts_first_s':pts[0],'pts_last_s':pts[-1],'sample_sheet':f'V{num+1:02d}-frames.jpg'})
 print('verified',num+1,flush=True)
for n,name in enumerate(('Progressive Psy Summer Dream mix  by Crusty Free download.wav','Crusty -Klangkraft-21nai2022.wav','Podcast-04.m4a')):
 r=next(r for r in allrows if Path(r['path']).name==name)
 p=subprocess.run([FF,'-nostdin','-v','error','-xerror','-threads','1','-ss','60','-i',r['path'],'-map','0:a:0','-t','120','-ac','1','-ar','8000','-f','f32le','pipe:1'],capture_output=True,timeout=90)
 x=np.frombuffer(p.stdout,dtype='<f4')
 reports.append({'id':f'A{n+1:02d}','path':r['path'],'sha256':r['sha256'],'range_seconds':[60,180],'decode_exit':p.returncode,'decode_stderr':p.stderr.decode('utf-8','replace'),'decoded_probe_sample_rate':8000,'decoded_probe_channels':1,'decoded_probe_samples':len(x),'finite_samples':bool(np.isfinite(x).all()),'probe_peak':float(np.max(np.abs(x))) if len(x) else None,'note':'CPU downsampled bounded decode into RAM only; not native loudness/truepeak/beat/quality measurement; no audio derivative saved'})
(OUT/'selected-verification.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');print('selected complete',flush=True)
