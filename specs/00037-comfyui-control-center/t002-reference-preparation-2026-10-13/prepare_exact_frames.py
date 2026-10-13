from pathlib import Path
import json,subprocess,hashlib
from PIL import Image,ImageDraw
OUT=Path(__file__).parent;ROOT=OUT.parent;FF=str(Path('tools/ffmpeg/bin/ffmpeg.exe').resolve())
m=json.loads((ROOT/'reference-manifest.json').read_text(encoding='utf-8'));frames=[];sheet=Image.new('RGB',(960,660),'#222222');draw=ImageDraw.Draw(sheet)
for i,s in enumerate(x for x in m['sources'] if x['source_id'].startswith('V')):
 st=next(x for x in s['streams'] if x['codec_type']=='video');num,den=map(int,st['r_frame_rate'].split('/'));fps=num/den;n=360 if s['source_id']=='V02' else 150
 cmd=[FF,'-nostdin','-v','error','-hwaccel','none','-threads','1','-i',s['absolute_path'],'-map','0:v:0','-vf',f'select=eq(n\,{n}),scale=480:270','-frames:v','1','-threads','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
 r=subprocess.run(cmd,capture_output=True,timeout=60);assert r.returncode==0 and len(r.stdout)==480*270*3
 im=Image.frombytes('RGB',(480,270),r.stdout);path=OUT/(s['source_id']+'-reference.png');im.save(path)
 # contact sheet resized only for review; individual source-bound frame retained
 im=im.resize((320,180));x=(i%3)*320;y=(i//3)*330;sheet.paste(im,(x,y));draw.text((x,y+185),f'{s["source_id"]} frame {n}, {n/fps:.3f}s',fill='white')
 frames.append({'source_id':s['source_id'],'source_sha256':s['sha256'],'video_stream_index':st['index'],'frame_index_zero_based':n,'source_time_seconds':n/fps,'time_basis':'observed regular PTS in selected-verification; zero-based frame index / rational frame rate','frame_image':str(path.relative_to(ROOT)),'frame_image_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rgb_sha256':hashlib.sha256(r.stdout).hexdigest(),'extraction_command':cmd})
sheet.save(OUT/'reference-sheet.jpg');(OUT/'reference-frames.json').write_text(json.dumps(frames,ensure_ascii=False,indent=2),encoding='utf-8');print('6 exact frame references extracted on CPU')
