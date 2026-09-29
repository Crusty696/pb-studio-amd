# T003 Real Long-Mix Streaming Probe — 2026-09-29

## Scope

Read-only, in-memory execution of the production `StreamingAudioAnalyzer` followed by the production `StructureAnalyzer.analyze_streaming_energy` on an existing local 67.6-minute album continuous mix. No backend, project catalog, SQLite, Brain DB, or media file was written. The probe called the same streaming-feature-to-structure combination used by `backend/routers/audio_router.py`; it did not execute the full ASGI/WPF/project-persistence workflow.

## Input identity

- Path: `F:\neue Psy-Trance, Progressive nur Beatport musik\Vertical_Mode_-_Madness_Express_(Album)_(Continuous_Mix)_138__(Psy-Trance)_A_Minor_17_17.mp3`
- Size: 162,383,922 bytes
- SHA-256: `0544E5C6ECD9A140C58F36E60AA36D8BA455368F89E5FDC4BCD7AC22B59F5103`
- FFprobe container duration: 4,053.760 s. Analyzer-decoded duration: 4,053.708820861678 s (difference 0.05118 s; MP3/container duration semantics differ slightly).

## Observed result

- Completed in 125.681 s; progress callback reached 100%.
- Streaming used 162 windows; 6,742 beats; 87,236 energy samples.
- Feature coverage: 1.0 / 4,053.708820861678 s; 4,215 timestamps paired with 4,215 12-bin chroma rows.
- `stage_errors` was empty.
- Structure analyzer returned 97 segments. Receipt's first segment: 0–56.087 s, label `section`, energy+chroma evidence, coverage 1.0, source role `original_mix`. Last segment ended exactly at decoded duration (4,053.709 s), labeled `outro`, with the same reported evidence/coverage/source role.
- Reported mix BPM was 109.9568. The filename's 138 value is not treated as ground truth for a continuous mix.

## Acceptance boundary

This is current real-media proof of streaming decode, feature alignment/coverage, error reporting, and connection into structure detection. It is **not** proof that 97 boundaries are musically correct, nor that a named song/section or key is correct. The official [HOMmega continuous-mix listing](https://soundcloud.com/hommega-official/vertical-mode-madness-express-continuous-mix) names the constituent tracks/order but provides no boundary timestamps; album track durations alone cannot identify overlap points. T003/#34 remains partial pending independently timecoded or human-reviewed reference labels.

## Local source-track fingerprint exploration (same day)

Read-only, in-memory coarse chroma matching was run against eight local candidate source tracks and the continuous mix. Several excerpts returned multiple high-scoring locations, while some excerpts matched unrelated repeated/harmonic sections; two expected album tracks were unavailable as the exact album versions (only remix files existed locally). This method therefore did **not** establish unique source-to-mix alignment or transition times and is rejected as acceptance ground truth. No media or project data was changed. Human/timecoded labels are still required for musical accuracy acceptance.

## Independent reference-material inventory

A separate read-only specialist inventory of `F:\neue techno sammlung nur beatport musik` found 1,042 audio files (560 AIFF, 461 MP3, 21 WAV) and no CUE/M3U/text/JSON/CSV/LRC/XML/log/SRT/VTT sidecars in that directory. `ffprobe` on two tracks found artist/title/track/BPM/key metadata but no beat, downbeat, section, or transition timecodes. Scope is limited to that directory and the examined files; it does not prove no labels exist elsewhere. This corroborates that technical feature coverage currently has no independent musical ground truth in the inspected collections.
