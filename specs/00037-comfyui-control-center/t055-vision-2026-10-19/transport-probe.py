"""Bounded real-reference caption probe; product config and source media read-only."""
import os, sys, json, time, hashlib, subprocess, traceback, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = ROOT/'scratch'/('t055-vision-'+time.strftime('%Y%m%d-%H%M%S'))
RUN.mkdir()
real_app = Path(os.environ['APPDATA']); real_local = Path(os.environ['LOCALAPPDATA'])
for name in ('APPDATA','LOCALAPPDATA','TEMP','TMP'):
    p=RUN/name; p.mkdir(); os.environ[name]=str(p)
os.environ['PBSTUDIO_PROJECT_DIR']=str(RUN/'projects')
os.environ['HF_HUB_OFFLINE']='1'; os.environ['TRANSFORMERS_OFFLINE']='1'
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT))
lhm=json.loads((ROOT/'config/lhm-runtime.json').read_text())['active']
os.environ['PBSTUDIO_LHM_MANIFEST_SHA256']=lhm['manifest_sha256']
os.environ['PBSTUDIO_LHM_SHA256']=lhm['library_sha256']
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
sources={s['source_id']:s for s in json.loads((OUT.parent/'reference-manifest.json').read_text(encoding='utf-8-sig'))['sources']}
reviews=json.loads((OUT.parent/'t002-human-review-2026-10-19/bildbewertungen.json').read_text(encoding='utf-8-sig'))['records']
protected=[Path(sources[r['source_id']]['absolute_path']) for r in reviews]
protected += [ROOT/'config.json',real_local/'PB_Studio/recovery-control/v1/RUNTIME_DIRTY']
protected += list((ROOT/'data').glob('*.db*'))+list((real_app/'PB_Studio/brain').glob('*.db*'))
def snapshot(): return {str(p):digest(p) if p.is_file() else None for p in protected}
def get(url):
    with urllib.request.urlopen(url,timeout=8) as r:return json.load(r)
result={'scope':'Same exact source frame V02/V03; preview/native and JPEG/PNG transport matrix; unchanged prompt and native wrapper/client; two calls each', 'before':snapshot(),'runs':[]}
cli=str(Path.home()/'.lmstudio/bin/lms.exe')
owned=False
try:
    from pb_studio.core.system_monitor import SystemMonitor
    monitor=SystemMonitor(); stats=monitor.get_stats(force_refresh=True)
    result['preflight']=stats
    print('PREFLIGHT '+json.dumps(stats,default=str),flush=True)
    assert stats['monitoring_status']=='ready'
    assert stats.get('gpu_load',100)<20, 'GPU is busy or load unavailable'
    result['models_before']=get('http://127.0.0.1:1234/api/v0/models')
    assert not any(m['state']=='loaded' for m in result['models_before']['data']), 'Existing model ownership; stop'
    for r in reviews:
        assert digest(Path(sources[r['source_id']]['absolute_path']))==r['source_sha256']
        frame=OUT.parent/'t002-reference-preparation-2026-10-13'/f"{r['source_id']}-reference.png"
        assert digest(frame)==r['frame_image_sha256']
    load=subprocess.run([cli,'load','google/gemma-4-e4b','--context-length','4096','--gpu','max','--ttl','600','--yes'],capture_output=True,text=True,timeout=180)
    result['load']={'returncode':load.returncode,'stdout':load.stdout,'stderr':load.stderr}
    assert load.returncode==0, result['load']
    owned=True
    import cv2
    from pb_studio.video import lmstudio_vision_wrapper as wrapper
    from pb_studio.ai.lmstudio_client import LMStudioClient
    original_chat=LMStudioClient.chat
    calls=[]
    async def observed(self,*args,**kwargs):
        assert self.base_url=='http://127.0.0.1:1234/v1', 'Prevent unapproved provider inference'
        assert kwargs.get('model')=='google/gemma-4-e4b', 'Prevent loading another model'
        pixels=kwargs['images'][0]
        if active_arm.endswith('_png'):
            buf=io.BytesIO();Image.fromarray(pixels).save(buf,format='PNG');kwargs['images']=[buf.getvalue()]
        from pb_studio.ai.lmstudio_client import _encode_image_data_uri
        uri=_encode_image_data_uri(kwargs['images'][0]);wire=base64.b64decode(uri.split(',',1)[1]);im=Image.open(io.BytesIO(wire))
        wire_meta={'width':im.width,'height':im.height,'format':im.format,'bytes':len(wire),'sha256':hashlib.sha256(wire).hexdigest()}
        response=await original_chat(self,*args,**kwargs)
        calls.append({'provider':self.provider,'endpoint':self.base_url,'model':kwargs['model'],'wire_image':wire_meta,'response':response})
        return response
    LMStudioClient.chat=observed
    import io, base64
    from PIL import Image
    active_arm='preview_jpeg'
    result['wrapper_sha256']=digest(Path(wrapper.__file__))
    result['prompt']=wrapper.DEFAULT_PROMPT
    exact={r['source_id']:r for r in json.loads((OUT.parent/'t002-reference-preparation-2026-10-13/reference-frames.json').read_text(encoding='utf-8-sig'))}
    for r in [x for x in reviews if x['source_id'] in ('V02','V03')]:
        sid=r['source_id']; frame=OUT.parent/'t002-reference-preparation-2026-10-13'/f'{sid}-reference.png'
        rgb=cv2.cvtColor(cv2.imread(str(frame)),cv2.COLOR_BGR2RGB)
        native_bytes=subprocess.run([str(ROOT/'tools/ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-hwaccel','none','-threads','1','-i',sources[sid]['absolute_path'],'-vf',f"select=eq(n\\,{exact[sid]['frame_index_zero_based']})",'-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],capture_output=True,check=True,timeout=90).stdout
        native=cv2.cvtColor(cv2.imdecode(__import__('numpy').frombuffer(native_bytes,dtype='uint8'),cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
        preview=rgb
        arms=['preview_jpeg','native_jpeg','preview_png','native_png']
        for repeat,active_arm in enumerate(arms+list(reversed(arms))):
            rgb=native if active_arm.startswith('native') else preview
            wrapper.clear_tag_cache()
            n=len(calls); start=time.perf_counter()
            tags,model=wrapper.extract_tags_and_model_via_lmstudio(rgb)
            row={'source_id':sid,'arm':active_arm,'input_shape':list(rgb.shape),'repeat':repeat+1,'frame_sha256':digest(frame),'source_time_seconds':r['source_time_seconds'],'seconds':time.perf_counter()-start,'tags':tags,'model':model,'calls':calls[n:]}
            result['runs'].append(row)
            (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k!='calls'},ensure_ascii=False),flush=True)
            assert tags and len(calls)>n, 'No actual usable inference'
except Exception:
    result['error']=traceback.format_exc();print(result['error'],flush=True)
finally:
    if owned:
        unload=subprocess.run([cli,'unload','google/gemma-4-e4b'],capture_output=True,text=True,timeout=60)
        result['unload']={'returncode':unload.returncode,'stdout':unload.stdout,'stderr':unload.stderr}
    result['after']=snapshot();result['protected_unchanged']=result['before']==result['after']
    try: result['models_after']=get('http://127.0.0.1:1234/api/v0/models')
    except Exception as exc: result['models_after_error']=str(exc)
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
if result.get('error') or not result['protected_unchanged']:sys.exit(1)
