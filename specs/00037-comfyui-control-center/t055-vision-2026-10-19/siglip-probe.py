"""Bounded real-reference caption probe; product config and source media read-only."""
import os, sys, json, time, hashlib, subprocess, traceback, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = ROOT/'scratch'/('t055-siglip-'+time.strftime('%Y%m%d-%H%M%S'))
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

import numpy as np
from PIL import Image
import io, asyncio
result={'scope':'SigLIP DirectML native25/50/75percent frames of six clips, two calls each; legacy/correct center comparison; no persistence or semantic label proof','before':snapshot(),'runs':[]}
wrapper=None
try:
    from pb_studio.core.system_monitor import SystemMonitor
    from pb_studio.core.vram_budget_manager import get_vram_manager
    monitor=SystemMonitor();stats=monitor.get_stats(force_refresh=True);result['preflight']=stats
    assert stats['monitoring_status']=='ready' and stats['gpu_load']<20
    result['lmstudio_models']=get('http://127.0.0.1:1234/api/v0/models')
    assert all(m['state']=='not-loaded' for m in result['lmstudio_models']['data'])
    get_vram_manager(monitor=monitor)
    from pb_studio.ai.siglip_wrapper import SigLIPWrapper
    from backend.dependencies import with_gpu_task
    wrapper=SigLIPWrapper(models_dir=str(ROOT/'models'),lazy_load=True)
    exact={r['source_id']:r for r in json.loads((OUT.parent/'t002-reference-preparation-2026-10-13/reference-frames.json').read_text(encoding='utf-8-sig'))}
    result['asset_sha256']=digest(ROOT/'models/siglip_vision.onnx')
    result['wrapper_sha256']=digest(ROOT/'src/pb_studio/ai/siglip_wrapper.py')
    for r in reviews:
        sid=r['source_id'];assert digest(Path(sources[sid]['absolute_path']))==r['source_sha256']
        mid=exact[sid]['frame_index_zero_based'];embs=[]
        for idx in [round(mid/2),mid,round(mid*1.5)]:
            raw=subprocess.run([str(ROOT/'tools/ffmpeg/bin/ffmpeg.exe'),'-v','error','-nostdin','-hwaccel','none','-threads','1','-i',sources[sid]['absolute_path'],'-vf',f'select=eq(n\,{idx})','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],capture_output=True,check=True,timeout=90).stdout
            im=Image.open(io.BytesIO(raw)).convert('RGB');vectors=[];times=[]
            for rep in range(2):
                started=time.perf_counter()
                emb=asyncio.run(with_gpu_task(wrapper.encode_image,im,model_id='siglip_vision',manage_vram=False,timeout_seconds=120))
                times.append(time.perf_counter()-started)
                assert emb is not None and emb.shape==(1152,) and np.isfinite(emb).all()
                assert abs(float(np.linalg.norm(emb))-1)<1e-5
                vectors.append(emb)
            row={'source_id':sid,'frame_index':idx,'size':im.size,'native_rgb_sha256':hashlib.sha256(np.asarray(im).tobytes()).hexdigest(),'seconds':times,'provider':wrapper.active_provider,'shape':list(vectors[0].shape),'norm':float(np.linalg.norm(vectors[0])),'repeat_max_abs':float(np.max(np.abs(vectors[0]-vectors[1]))),'repeat_cosine':float(vectors[0]@vectors[1]),'vector_sha256':[hashlib.sha256(e.tobytes()).hexdigest() for e in vectors]}
            if idx==mid:
                arr=np.asarray(im.resize((384,384),Image.Resampling.BICUBIC),dtype=np.float32)/255
                legacy=(arr-np.array([.48145466,.4578275,.40821073],np.float32))/np.array([.26862954,.26130258,.27577711],np.float32)
                tensor=np.transpose(legacy,(2,0,1))[None]
                from pb_studio.core.gpu_lock import gpu_inference_lock
                with gpu_inference_lock:
                    old=wrapper.vision_session.run(None,{wrapper.vision_session.get_inputs()[0].name:tensor})[0].squeeze()
                if old.ndim==2:old=old.mean(axis=0)
                old=old/(np.linalg.norm(old)+1e-8)
                row['legacy_corrected_cosine']=float(old@vectors[0])
                row['legacy_corrected_max_abs']=float(np.max(np.abs(old-vectors[0])))
            result['runs'].append(row);embs.append(vectors[0]);print(json.dumps(row),flush=True)
            (OUT/'siglip-results.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
        mean=np.mean(embs,axis=0);mean=mean/np.linalg.norm(mean)
        result.setdefault('clip_aggregates',{})[sid]={'shape':list(mean.shape),'norm':float(np.linalg.norm(mean)),'sha256':hashlib.sha256(mean.tobytes()).hexdigest()}
    sess=wrapper.vision_session;opts=sess.get_session_options()
    result['session']={'providers':sess.get_providers(),'mem_pattern':opts.enable_mem_pattern,'cpu_mem_arena':opts.enable_cpu_mem_arena,'text_encoder_available':wrapper.has_text_encoder}
    assert wrapper.active_provider=='DmlExecutionProvider' and not opts.enable_mem_pattern and not opts.enable_cpu_mem_arena
except Exception:
    result['error']=traceback.format_exc();print(result['error'],flush=True)
finally:
    if wrapper is not None:
        wrapper.unload();result['unloaded']=wrapper.vision_session is None and wrapper.text_session is None and not wrapper.is_ready
    result['after']=snapshot();result['protected_unchanged']=result['before']==result['after']
    (OUT/'siglip-results.json').write_text(json.dumps(result,indent=2,default=str),encoding='utf-8')
if result.get('error') or not result['protected_unchanged']:sys.exit(1)
