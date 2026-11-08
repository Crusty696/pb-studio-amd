"""CPU-only full-clip SceneDetector probe, isolated from application state."""
import os
import sys
import json
import time
import hashlib
import subprocess
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
REAL_APPDATA = Path(os.environ['APPDATA'])
REAL_LOCAL = Path(os.environ['LOCALAPPDATA'])
RUN = ROOT / 'scratch' / ('t002-scenes-' + time.strftime('%Y%m%d-%H%M%S'))
RUN.mkdir(exist_ok=False)
for key in ('APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP'):
    path = RUN / key
    path.mkdir()
    os.environ[key] = str(path)
os.environ['PYTHONPATH'] = str(ROOT / 'src')
sys.path.insert(0, str(ROOT / 'src'))

import cv2
import numpy as np
from scenedetect import open_video
cv2.setNumThreads(2)
cv2.ocl.setUseOpenCL(False)

def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

sources = [s for s in json.loads((OUT.parent/'reference-manifest.json').read_text(encoding='utf-8'))['sources']
           if s['source_id'].startswith('V')]
protected = [Path(s['absolute_path']) for s in sources]
protected += [ROOT/'config.json', ROOT/'data/pb_studio.db', ROOT/'data/pb_studio.db-wal',
              ROOT/'data/pb_studio.db-shm', REAL_LOCAL/'PB_Studio/recovery-control/v1/RUNTIME_DIRTY']
protected += list((REAL_APPDATA/'PB_Studio/brain').glob('*.db*'))
def snapshot():
    return {str(p): digest(p) if p.is_file() else None for p in protected}

before = snapshot()
for source in sources:
    assert before[source['absolute_path']] == source['sha256']
code = ROOT/'src/pb_studio/video/scene_detect.py'
spec = importlib.util.spec_from_file_location('scene_probe_module', code)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = {'scope': 'Full clips; SceneDetector body with observed software OpenCV decoder; no router or GUI',
          'code_sha256': digest(code), 'sources': [], 'protection_before': before}
try:
    for source in sources:
        metadata = json.loads(subprocess.run([str(ROOT/'tools/ffmpeg/bin/ffprobe.exe'), '-v','error',
            '-select_streams','v:0','-count_frames','-show_entries',
            'stream=duration,nb_read_frames,avg_frame_rate:format=duration','-of','json',source['absolute_path']],
            capture_output=True, check=True, timeout=120).stdout)
        stream = metadata['streams'][0]
        duration = float(stream.get('duration') or metadata['format']['duration'])
        expected_frames = int(stream['nb_read_frames'])
        runs = []
        for repetition in range(2):
            receipt = {'decoded_frames': 0}
            handles = []
            def observed_open(path):
                video = open_video(path, backend='opencv')
                handles.append(video)
                receipt['hardware_acceleration'] = video.capture.get(cv2.CAP_PROP_HW_ACCELERATION)
                assert receipt['hardware_acceleration'] == cv2.VIDEO_ACCELERATION_NONE
                read = video.read
                def count_read(*args, **kwargs):
                    frame = read(*args, **kwargs)
                    if isinstance(frame, np.ndarray):
                        receipt['decoded_frames'] += 1
                    return frame
                video.read = count_read
                return video
            module.open_video = observed_open
            started = time.perf_counter()
            try:
                scenes = module.SceneDetector().detect_scenes(source['absolute_path'], duration_seconds=duration)
                receipt['decode_failures'] = sum(v._decode_failures for v in handles)
            finally:
                for video in handles:
                    video.capture.release()
            receipt.update(seconds=time.perf_counter()-started, scenes=scenes)
            assert receipt['decoded_frames'] == expected_frames
            assert receipt['decode_failures'] == 0
            assert scenes and abs(scenes[0][0]) < 1e-6
            for i, (start, end) in enumerate(scenes):
                assert 0 <= start < end <= duration + 1e-6
                if i:
                    assert abs(start-scenes[i-1][1]) < 1e-6
            # Container duration and frame-time duration may differ by one frame.
            numerator, denominator = map(int, stream['avg_frame_rate'].split('/'))
            assert abs(scenes[-1][1]-duration) <= denominator/numerator + 0.001
            runs.append(receipt)
        assert runs[0]['scenes'] == runs[1]['scenes']
        result['sources'].append({'id': source['source_id'], 'source_sha256':source['sha256'],
            'ffprobe_duration_seconds':duration, 'ffprobe_decoded_frames':expected_frames, 'runs':runs})
        print(source['source_id'], expected_frames, 'frames', len(scenes), 'scene(s), identical repeats', flush=True)
    result['technical_status'] = 'PASS'
except Exception as exc:
    result['technical_status'] = 'FAIL'
    result['error'] = repr(exc)
    raise
finally:
    result['protection_after'] = snapshot()
    result['protected_files_unchanged'] = result['protection_after'] == before
    (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert result['protected_files_unchanged']
