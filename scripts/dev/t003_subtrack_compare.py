"""Run a SubtrackDetector module (current or old via file path) on a mix; print boundaries + F1."""
import importlib.util
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_subtrack_detection import _load_gt, evaluate_boundaries  # noqa: E402

mod_path, audio, gt_path = sys.argv[1], sys.argv[2], sys.argv[3]
spec = importlib.util.spec_from_file_location("sd_under_test", mod_path)
mod = importlib.util.module_from_spec(spec)
sys.modules["sd_under_test"] = mod
spec.loader.exec_module(mod)
t0 = time.time()
res = mod.SubtrackDetector().detect(audio)
b = [x.time for x in res.boundaries]
gt = _load_gt(Path(gt_path))
m = evaluate_boundaries(b, gt, 15.0)
print(json.dumps({"module": Path(mod_path).name, "audio": Path(audio).name, "seconds": round(time.time() - t0, 1),
                  "n": len(b), **{k: round(v, 3) if isinstance(v, float) else v for k, v in m.items()},
                  "detected": [round(x) for x in b], "gt": [round(x) for x in gt],
                  "components": [{k: round(v, 2) for k, v in x.components.items()} for x in res.boundaries]}))
