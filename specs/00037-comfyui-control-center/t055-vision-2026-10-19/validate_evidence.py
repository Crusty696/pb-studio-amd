"""Read-only cross-check of bounded T055 media evidence; no product imports."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

caption_files = ["transport-results.json", "reasoning-results.json", "native-multipoint-results.json"]
captions = [read(name) for name in caption_files]
siglip = read("siglip-results.json")
for result in [*captions, siglip]:
    assert not result.get("error"), result.get("error")
    assert result["protected_unchanged"] and result["before"] == result["after"]
assert [len(result["runs"]) for result in captions] == [16, 8, 18]
assert sum(len(row["calls"]) for result in captions for row in result["runs"]) == 42
assert all(result["unload"]["returncode"] == 0 for result in captions)
assert all(m["state"] == "not-loaded" for result in captions for m in result["models_after"]["data"])
native = {(r["source_id"], r["frame_index"]): r for r in captions[-1]["runs"]}
assert len(siglip["runs"]) == 18 and siglip["unloaded"]
for row in siglip["runs"]:
    assert native[row["source_id"], row["frame_index"]]["native_rgb_sha256"] == row["native_rgb_sha256"]
    assert row["repeat_max_abs"] == 0 and len(set(row["vector_sha256"])) == 1
    assert row["shape"] == [1152] and abs(row["norm"] - 1) < 1e-5
assert "DmlExecutionProvider" in siglip["session"]["providers"]
assert not siglip["session"]["mem_pattern"] and not siglip["session"]["cpu_mem_arena"]
assert siglip["wrapper_sha256"] == sha(ROOT / "src/pb_studio/ai/siglip_wrapper.py")
summary = {
    "caption_calls": 42,
    "directml_calls": 42,
    "native_frames": 18,
    "identical_frame_hashes_caption_and_siglip": True,
    "identical_siglip_repeats": 18,
    "four_series_protected_unchanged": True,
    "owned_models_unloaded": True,
    "siglip_executed_code_matches": True,
    "legacy_corrected_cosine": {r["source_id"]: r["legacy_corrected_cosine"] for r in siglip["runs"] if "legacy_corrected_cosine" in r},
    "semantic_acceptance": False,
    "full_native_api_gui_acceptance": False,
}
(OUT / "media-validation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
