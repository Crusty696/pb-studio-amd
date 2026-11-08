"""Bounded CPU-only module probe; no backend, model load, DB write or generation."""
import os
import sys
import json
import hashlib
import importlib.util
import logging
import subprocess
import time
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = ROOT / 'scratch' / ('t002-spectral-' + time.strftime('%Y%m%d-%H%M%S'))
RUN.mkdir(exist_ok=False)
REAL_APPDATA = Path(os.environ['APPDATA'])
REAL_LOCAL = Path(os.environ['LOCALAPPDATA'])
for key in ('APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'NUMBA_CACHE_DIR'):
    directory = RUN / key
    directory.mkdir()
    os.environ[key] = str(directory)
os.environ['PYTHONPATH'] = str(ROOT / 'src')
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
os.environ['MKL_NUM_THREADS'] = '2'
sys.path.insert(0, str(ROOT / 'src'))

import numpy as np
import librosa
import psutil

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

manifest = json.loads((OUT.parent / 'reference-manifest.json').read_text(encoding='utf-8'))
sources = [s for s in manifest['sources'] if s['source_id'].startswith('A')]
protected = [ROOT / 'config.json', ROOT / 'data' / 'pb_studio.db',
             ROOT / 'data' / 'pb_studio.db-wal', ROOT / 'data' / 'pb_studio.db-shm',
             REAL_LOCAL / 'PB_Studio/recovery-control/v1/RUNTIME_DIRTY']
protected += list((REAL_APPDATA / 'PB_Studio/brain').glob('*.db*'))
protected += [Path(s['absolute_path']) for s in sources]

def snapshot():
    return {str(p): digest(p) if p.is_file() else None for p in protected}

before = snapshot()
for source in sources:
    assert before[source['absolute_path']] == source['sha256'], source['source_id']

def module(name):
    path = ROOT / 'src/pb_studio/audio' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

spectral_mod = module('spectral_analyzer')
structure_mod = module('structure_analyzer')
messages = []
class Capture(logging.Handler):
    def emit(self, record):
        messages.append({'level': record.levelname, 'message': record.getMessage()})
handler = Capture()
for mod in (spectral_mod, structure_mod):
    mod.logger.addHandler(handler)

result = {'scope': 'CPU module bodies, not router/GUI; source seconds 60-90',
          'run_directory': str(RUN), 'sources': [], 'protection_before': before,
          'code_sha256': {name: digest(ROOT / 'src/pb_studio/audio' / (name + '.py'))
                          for name in ('spectral_analyzer', 'structure_analyzer')},
          'versions': {'python': sys.version, 'numpy': np.__version__, 'librosa': librosa.__version__},
          'sampler_scope': '100ms process RSS samples during analysis only; not exact peak or GPU measurement'}
try:
    for source in sources:
        sid = source['source_id']
        decoded = subprocess.run([str(ROOT / 'tools/ffmpeg/bin/ffmpeg.exe'), '-v', 'error',
            '-nostdin', '-threads', '2', '-ss', '60', '-i', source['absolute_path'],
            '-t', '30', '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '44100',
            '-f', 'f32le', 'pipe:1'], check=True, capture_output=True, timeout=90)
        y = np.frombuffer(decoded.stdout, dtype='<f4').copy()
        assert len(y) == 30 * 44100 and np.isfinite(y).all()
        low = librosa.resample(y, orig_sr=44100, target_sr=22050)
        repeats = []
        for repetition in range(2):
            rss = []
            stop = threading.Event()
            def sample():
                process = psutil.Process()
                while not stop.is_set():
                    rss.append(process.memory_info().rss)
                    stop.wait(0.1)
            thread = threading.Thread(target=sample, daemon=True)
            thread.start()
            started = time.perf_counter()
            try:
                spectral = spectral_mod.SpectralAnalyzer().analyze_from_array(y, 44100)
                structure = structure_mod.StructureAnalyzer().analyze_song_structure(low, 22050)
            finally:
                stop.set()
                thread.join()
            elapsed = time.perf_counter() - started
            times = np.asarray(spectral['times'])
            assert len(times) > 1 and np.all(np.diff(times) > 0)
            assert spectral['duration'] == 30 and len(spectral['band_energies']) == 8
            for values in spectral['band_energies'].values():
                assert len(values) == len(times) and np.isfinite(values).all()
            segments = structure['segments']
            assert segments and abs(segments[0]['start_time']) < 1e-6
            assert abs(segments[-1]['end_time'] - 30) < 1e-6
            for i, seg in enumerate(segments):
                assert 0 <= seg['start_time'] < seg['end_time'] <= 30.001
                if i:
                    assert abs(seg['start_time'] - segments[i-1]['end_time']) < 1e-6
            raw = {'spectral': spectral, 'structure': structure}
            encoded = json.dumps(raw, sort_keys=True, allow_nan=False).encode()
            artifact = RUN / f'{sid}-repeat-{repetition+1}.json'
            artifact.write_bytes(encoded)
            repeats.append({'seconds': elapsed, 'result_sha256': digest(artifact),
                            'sampled_rss_max_bytes': max(rss), 'rss_samples': len(rss)})
        assert repeats[0]['result_sha256'] == repeats[1]['result_sha256']
        windows = []
        for offset in (0, 10, 20):
            mask = (times >= offset) & (times < offset + 10)
            windows.append({'source_seconds': [60+offset, 70+offset],
                'rms': float(np.sqrt(np.mean(y[offset*44100:(offset+10)*44100] ** 2))),
                'band_mean_magnitude': {k: float(np.mean(np.asarray(v)[mask]))
                                        for k,v in spectral['band_energies'].items()}})
        result['sources'].append({'id': sid, 'source_sha256': source['sha256'],
            'source_window': [60,90], 'samples': len(y), 'repeats': repeats,
            'structure_relative_to_excerpt': structure, 'events_relative_to_excerpt': spectral['events'],
            'ten_second_descriptive_windows': windows, 'technical_checks': 'PASS'})
        print(sid, 'two repeats identical', round(repeats[0]['seconds'], 3), flush=True)
    assert not messages, messages
    result['technical_status'] = 'PASS'
except Exception as error:
    result['technical_status'] = 'FAIL'
    result['error'] = repr(error)
    raise
finally:
    result['logs_warning_or_above'] = messages
    result['protection_after'] = snapshot()
    result['protected_files_unchanged'] = result['protection_before'] == result['protection_after']
    (OUT / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
assert result['protected_files_unchanged']
