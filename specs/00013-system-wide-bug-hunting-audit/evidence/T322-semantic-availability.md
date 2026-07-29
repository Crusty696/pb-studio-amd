# T322 – Semantic Availability

Status: CONFIRMED

## Root cause

- Missing, empty, dimension-mismatched, zero-norm, or non-finite embeddings were converted to the numeric similarity `0.5`.
- That value was indistinguishable from a valid neutral cosine result and was included in the Brain score denominator.
- The active video pipeline writes 1152-D SigLIP vectors to `video_index.faiss`; the legacy global Brain cache identity still names a 768-D SigLIP2 model and the active pipeline does not populate that cache.

## Persisted-data inspection

- `data/video_index.faiss`: dimension `1152`, `ntotal=904`.
- Metadata entries: `904`; tombstones: `113`; `vector_map`: `791` live rows.
- Release-QC project 34: six video rows, each `has_embedding=true`, `embedding_dim=1152`, and one FAISS link.
- Release-QC audio row: no audio embedding and no vector link.
- `%APPDATA%\PB_Studio\brain\embedding_cache.db`: `PRAGMA quick_check=ok`, zero indexed embeddings and zero files.
- Result for the current reference project: Brain cross-modal similarity is genuinely `partial/unavailable`, not `0.5`.

## Repair contract

- `CandidateFeatures` carries `semantic_status` and `semantic_reason`.
- Status is `available` only for finite, non-zero, equal-dimensional projected vectors; one missing/invalid side is `partial`, both missing is `unavailable`.
- `BridgeDimensions.compute_all` omits `semantic_match_weight` when semantic data is not available.
- `BrainScorer` and the post-processor average only available axes.
- Timeline/deep-hook metadata exposes `semantic_status`, `semantic_reason`, and `brain_axis_status`.
- Invalid projected cosine input returns `None`; no synthetic similarity is generated.
- Model Registry was inspected but not modified: LM Studio selection does not supply these ONNX/FAISS embeddings.

## Static verification

- Python syntax: PASS for all changed Brain/Pacing files.
- Static scan: no missing-semantic or invalid-cosine path returns `0.5`.
- SQLite/FAISS inspection was read-only.
- `git diff --check`: PASS (line-ending notices only).
- Functional/regression tests: intentionally not run before T332.
