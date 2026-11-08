from pathlib import Path
import subprocess,json,hashlib,concurrent.futures,time
OUT=Path(__file__).parent
PROBE=Path('tools/ffmpeg/bin/ffprobe.exe').resolve()
roots={'video':Path(r'E:\03_Video_&_Medien\Eigene_Videos\Video\Clips'),'audio':Path(r'E:\02_Musik_&_Audio\Audio_Clips\Psy-Set')}
def inspect(item):
 role,root,p=item;s=p.stat();h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 cmd=[str(PROBE),'-v','error','-show_format','-show_streams','-of','json',str(p)]
 try:
  r=subprocess.run(cmd,capture_output=True,timeout=30);probe=json.loads(r.stdout) if r.returncode==0 else None;err=r.stderr.decode('utf-8','replace')
 except Exception as e:probe=None;err=type(e).__name__
 after=p.stat()
 return {'role':role,'path':str(p),'relative_path':str(p.relative_to(root)),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'sha256':h.hexdigest(),'stat_unchanged':(s.st_size,s.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'probe':probe,'error':err}
items=[(role,root,p) for role,root in roots.items() for p in sorted(root.rglob('*')) if p.is_file() and p.suffix.lower() in ('.mp4','.wav','.mp3','.m4a')]
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for row in pool.map(inspect,items):
  results.append(row)
  if len(results)%50==0: print('inspected',len(results),flush=True)
(OUT/'inventory.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
groups={}
for row in results:groups.setdefault(row['sha256'],[]).append(row['relative_path'])
print(json.dumps({'count':len(results),'bytes':sum(r['bytes'] for r in results),'probe_errors':sum(r['probe'] is None for r in results),'stat_changes':sum(not r['stat_unchanged'] for r in results),'duplicate_groups':[v for v in groups.values() if len(v)>1]},ensure_ascii=False),flush=True)
