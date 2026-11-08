"""Validate final source/test evidence and protected files, without PB imports."""
import ast
import hashlib
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

files = [
    "src/pb_studio/ai/siglip_wrapper.py", "src/pb_studio/embedding_identity.py",
    "src/pb_studio/video/video_embedder.py", "src/pb_studio/ai/video_specialist.py",
    "src/pb_studio/data/vector_store.py", "src/pb_studio/pacing/clip_selector.py",
    "backend/app_state.py", "backend/routers/video_router.py", "backend/routers/pacing_router.py",
    "scripts/backfill_brain_embedding_cache.py", "docs/examples/siglip_video_example.py",
    "Tests/test_t055_siglip_preprocessing.py", "Tests/test_t056_embedding_identity.py",
    "Tests/test_clip_selector_semantic_fallback.py", "Tests/test_lmstudio_vision_wrapper.py",
]
for name in files:
    ast.parse((ROOT / name).read_text(encoding="utf-8-sig"), filename=name)
results = {}
for name, expected in [("pytest-caption-final.txt", 108), ("pytest-identity-final.txt", 78)]:
    log = (OUT / name).read_text(encoding="utf-8-sig")
    matches = re.findall(r"(\d+) passed", log)
    assert matches and int(matches[-1]) == expected and not re.search(r"\d+ failed", log), name
    results[name] = expected
media = json.loads((OUT / "siglip-results.json").read_text())
protected = {name: sha(Path(name)) if Path(name).is_file() else None for name in media["after"]}
assert protected == media["after"], "Protected state changed after media probe; inspect before claiming protection"
result = {
    "test_groups": results,
    "distinct_passed": sum(results.values()),
    "syntax_valid_files": files,
    "source_sha256": {name: sha(ROOT / name) for name in files},
    "protected_unchanged_after_cpu_tests": True,
    "protected_sha256": protected,
    "full_suite_or_gui_acceptance": False,
}
(OUT / "final-validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k not in ("protected_sha256", "source_sha256", "syntax_valid_files")}, indent=2))
