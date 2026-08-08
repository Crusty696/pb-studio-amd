# T321 – Canonical Feature Adapter

Status: CONFIRMED

## Root cause

- RAFT `avg_motion` values from the persisted project analysis reach `129.26`; the Brain bridge previously consumed them as if they were already in `[0,1]`.
- Pace defaulted to synthetic `0.5`, segment type did not reach the deep selector hook, and `brain_min_confidence` filtered the calculated ranking score instead of analysis confidence.
- `clip_selector.py` and `post_processor.py` maintained separate feature mappings, so their units and fallbacks diverged.

## Contract

- `CanonicalFeatureAdapter` is the only constructor of `CandidateFeatures`.
- Motion is normalized against the selected video pool's positive p95; motion curves use the identical scale.
- Pace uses explicit normalized analysis data or normalized real motion, never a fixed semantic default.
- Mood tags and segment aliases are canonicalized; segment type is resolved from persisted structure/subtrack segments.
- Feature confidence comes from explicit analysis confidence/status or `is_analyzed`; unavailable data remains `0.0`.
- `brain_min_confidence` filters feature availability confidence. The calculated Brain score remains ranking evidence and is not relabelled as confidence.
- Both the deep selector and post-processor persist normalized motion, feature confidence, provenance, and segment type.

## Data-flow evidence

1. `pacing_router.py` forwards persisted video analysis status/confidence into clip data.
2. `PacingService._configure_brain_selector` builds one adapter from the cached audio analysis and selected video pool.
3. `ClipSelector._select_via_brain` and `annotate_cuts_with_brain` call the same adapter.
4. `BrainReranker` filters on `CandidateFeatures.confidence`; `BrainScorer` returns the features used for the selected result.
5. Timeline metadata retains `feature_confidence`, `feature_provenance`, `segment_type`, bridge values, and the independent final score.

## Static verification

- Python syntax: PASS for all eight changed Brain/Pacing/router files.
- Reference scan: exactly one production `CandidateFeatures(` construction remains, in `feature_adapter.py`.
- Stale mapping scan: no `_video_pace_score`, `_feature_at_time`, or score-as-confidence threshold remains.
- `git diff --check`: PASS (line-ending notices only).
- Functional/regression tests: intentionally not run before T332.
