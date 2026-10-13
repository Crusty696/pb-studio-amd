"""Execute exact selected PB Studio CPU function bodies; no backend/product import."""
import ast,hashlib,json,os,sys,tempfile,types,logging,math,stat,ctypes
from pathlib import Path
from collections import Counter
os.environ['LOCALAPPDATA']=tempfile.mkdtemp(prefix='pb-t002-cpu-localappdata-')
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS']='hwaccel;none'
import cv2
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
MAN=json.loads((ROOT/'specs/00037-comfyui-control-center/reference-manifest.json').read_text(encoding='utf-8'))
SEL=json.loads((ROOT/'specs/00037-comfyui-control-center/t002-selection-2026-10-13/selected-verification.json').read_text(encoding='utf-8'))
from pb_studio.runtime_contract import ffprobe_path
probe=ffprobe_path() # canonical signed local runtime; no product app

def load_nodes(relative,names,extra):
 path=ROOT/relative;tree=ast.parse(path.read_text(encoding='utf-8'));nodes=[x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef)) and x.name in names]
 assert len(nodes)==len(names),(relative,names)
 namespace=dict(extra);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
 return namespace

# Media path policy is exact source, with only pure prerequisites injected.
policy=load_nodes('backend/media_path_policy.py',['MediaPathPolicyError','_reject_unsafe_reference','canonical_local_media_reference','canonical_local_media_file'],{'Path':Path,'os':os,'stat':stat,'ctypes':ctypes})
config=types.SimpleNamespace(ffprobe_path=probe)
audio=load_nodes('backend/routers/audio_router.py',['_probe_audio_info'],{'config':config,'Any':object})
video=load_nodes('backend/routers/video_router.py',['_get_video_info'],{'config':config,'os':os,'Any':object})

# Pin OpenCV to FFmpeg software acceleration NONE. Assert backend and accel property.
original_capture=cv2.VideoCapture
CAP_FFMPEG=cv2.CAP_FFMPEG;PROP_ACCEL=cv2.CAP_PROP_HW_ACCELERATION;ACCEL_NONE=cv2.VIDEO_ACCELERATION_NONE
class CpuCv2:
 def __getattr__(self,name):return getattr(cv2,name)
 def VideoCapture(self,path):
  cap=original_capture(str(path),CAP_FFMPEG,[PROP_ACCEL,ACCEL_NONE])
  if cap.isOpened():
   assert cap.get(cv2.CAP_PROP_BACKEND)==CAP_FFMPEG
   assert cap.get(PROP_ACCEL)==ACCEL_NONE
  return cap
cpu_cv2=CpuCv2()
frames=load_nodes('src/pb_studio/video/frame_extractor.py',['_bounded_duration','FrameGrabber'],{'Path':Path,'cv2':cpu_cv2,'Image':Image,'Optional':__import__('typing').Optional,'List':__import__('typing').List,'logger':logging.getLogger('frame_extractor')})
streamtree=ast.parse((ROOT/'src/pb_studio/audio/streaming_analyzer.py').read_text(encoding='utf-8'))
cls=next(x for x in streamtree.body if isinstance(x,ast.ClassDef) and x.name=='StreamingAudioAnalyzer')
methods=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name in ('_load_chunk','_load_chunk_soundfile')]
assert len(methods)==2
mini=ast.ClassDef(name='StreamingAudioAnalyzerCpuChunk',bases=[],keywords=[],body=[ast.parse('SR=44100').body[0],*methods],decorator_list=[])
ns={'Path':Path,'np':np};exec(compile(ast.fix_missing_locations(ast.Module(body=[mini],type_ignores=[])),str(ROOT/'src/pb_studio/audio/streaming_analyzer.py'),'exec'),ns)
chunker=ns['StreamingAudioAnalyzerCpuChunk']()

records=[]
for source in MAN['sources']:
 name=source['source_id'];path=policy['canonical_local_media_file'](source['absolute_path'])
 assert path==Path(source['absolute_path']).resolve()
 old=path.stat();rec={'source_id':name,'path':str(path),'source_sha256':source['sha256'],'status':'UNKNOWN','pb_path_accepted':True}
 if name.startswith('V'):
  info=video['_get_video_info'](str(path));expected=next(x for x in SEL if x['id']==name)
  raw_stream=next(s for s in source['streams'] if s['codec_type']=='video')
  raw_fps=float(raw_stream['r_frame_rate'].split('/')[0])/float(raw_stream['r_frame_rate'].split('/')[1])
  assert (info['width'],info['height'],info['codec'])==(raw_stream['width'],raw_stream['height'],raw_stream['codec_name'])
  assert abs(info['fps']-round(raw_fps,2))<.01
  assert abs(info['duration']-float(raw_stream['duration']))<.05
  assert info['width']>0 and info['height']>0 and info['fps']>0 and info['duration']>0
  assert abs(info['duration']-source['range_end'])<.05,(name,info,source['range_end'])
  grabber=frames['FrameGrabber'](default_count=3)
  end=min(info['duration']-.25,source['range_end']-.25)
  extracted=grabber.extract_batch(str(path),.25,end,count=3,duration_seconds=source['range_end'])
  assert len(extracted)==3
  assert all(im.width>0 and im.height>0 for im in extracted)
  strip=grabber.extract_thumbnail_strip(str(path),n=4,duration_seconds=source['range_end'])
  assert len(strip)==4
  rec.update({'pb_metadata':info,'pb_random_frames':len(extracted),'pb_frame_sizes':[list(im.size) for im in extracted],'pb_thumbnail_strip_frames':len(strip),'status':'PASS_CPU_FUNCTIONS'})
 else:
  info=audio['_probe_audio_info'](str(path))
  raw_stream=next(s for s in source['streams'] if s['codec_type']=='audio')
  assert (info['sample_rate'],info['channels'])==(int(raw_stream['sample_rate']),int(raw_stream['channels']))
  assert abs(info['duration']-float(raw_stream['duration']))<.10
  assert info['duration']>180 and info['sample_rate']>0 and info['channels']>0
  y=chunker._load_chunk(Path(path),60.0,30.0)
  assert isinstance(y,np.ndarray) and np.isfinite(y).all() and len(y)>0
  # Native chunker resamples to 44100 mono; verify 30 s at target SR within decoder tolerances.
  assert abs(len(y)-30*44100)<=2048,(name,len(y))
  rec.update({'pb_metadata':info,'pb_chunk_offset_seconds':60,'pb_chunk_duration_seconds':30,'pb_chunk_samples':len(y),'pb_chunk_finite':True,'pb_chunk_mean_abs':float(np.mean(np.abs(y))),'status':'PASS_CPU_FUNCTIONS'})
 now=path.stat();assert (old.st_size,old.st_mtime_ns)==(now.st_size,now.st_mtime_ns)
 records.append(rec);print(name,rec['status'],flush=True)

# Hash selected9 after; quality comparison would need independent labels and separate authorized runs.
for rec in records:
 h=hashlib.sha256()
 with Path(rec['path']).open('rb') as f:
  for data in iter(lambda:f.read(4*1024*1024),b''):h.update(data)
 rec['source_sha256_after']=h.hexdigest();assert rec['source_sha256_after']==rec['source_sha256']

report={'status':'CPU_FUNCTION_SCOPE_ONLY','source_modules':['backend/media_path_policy.py','backend/routers/audio_router.py','backend/routers/video_router.py','src/pb_studio/video/frame_extractor.py','src/pb_studio/audio/streaming_analyzer.py','src/pb_studio/runtime_contract.py'],'extraction':'AST exact named pure function/class bodies; no router/package import except runtime_contract','gpu_backend':'OpenCV CAP_FFMPEG with VIDEO_ACCELERATION_NONE asserted for all frame opens; audio soundfile/librosa CPU','not_performed':['backend app start','API import or catalog write','full beat/caption/motion/embedding inference','GPU run','generation','quality scoring'],'records':records,'source_hashes_identical_after':True}
(OUT/'cpu-function-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Complete',len(records))
