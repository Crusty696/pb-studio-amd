# T016 Export-Artifact and Log Review — 2026-09-29

## Scope and source

Read-only review of the completed T016 export and its run-scoped evidence. Artifact: `%TEMP%\pb_studio_true_peak_fix_20260929_live\PBStudio_true_peak_verified.mp4`. Run ID: `9d29b8850fbf4a0abcea95ea2092d2f2`. The run-scoped FFmpeg progress/stderr, `result.json`, and `validation.json` were read. The repository's newest application/E2E logs are from 2026-09-28; they do not contain the 2026-09-29 render run. No project, source, output, or app state was changed.

- Artifact SHA-256: `E95C7EBC7AF925689C566B30CCC8D341AB9C1EC38F339AC1E2F662FF86B2729F`.
- Existing QA timeline SHA-256: `9E9F1679ABEA72062056A324BE57A2FFFE2AC54A394F75C5BBF3141FAB64C967`; audio master SHA-256: `E794B72DAD7ADB4106469D6704E473736142C320B019E7307BB45C49278DD501`.
- The timeline and render evidence agree on audio path, total duration, and frame count. However, the run receipt does not carry a project ID or timeline hash; this is a strong cross-check, not a cryptographic binding of this artifact to that exact saved timeline snapshot.

## Verified artifact facts

- FFprobe: HEVC Main, 1920x1080, 30/1 fps, yuv420p, BT.709; AAC-LC, 48 kHz, stereo. Video stream duration 337.166667 s; audio stream duration 337.137 s; container duration 337.166667 s.
- Run receipt: FFmpeg exit 0, `progress=end`, 10,115/10,115 frames, `dup_frames=0`, `drop_frames=0`; expected duration 337.176 s. Independent complete FFmpeg decode exited 0.
- Run validator passed; true peak -1.58 dBTP; final container packet scan found zero non-monotonic PTS or DTS in either stream. AAC first packet PTS is -21.333 ms while stream start is zero; no cause is inferred from this observation.
- Full-video read-only FFmpeg scan at `freezedetect=n=-60dB:d=2` and `blackdetect=d=0.5:pix_th=0.10` completed all 10,115 frames with no detected freeze ≥2 s or black interval ≥0.5 s. This does not rule out shorter freezes, flashes, or semantic defects.
- The run's FFmpeg stderr contains 29 `concat` input `DTS ... out of order` warnings. The output MP4's packet scan is monotonic and decode passed, so this is an upstream concat warning—not proof of a corrupt final artifact. Preserve as a follow-up: attribute warnings to source segments and check A/V cut-boundary alignment before suppressing or changing timestamp handling.

### Timestamp-diagnostic follow-up

The FFmpeg diagnostics skill completed read-only diagnosis against the final MP4 and this exact run's stderr. It reported 29 `PTS_DTS_ERROR` findings from the *input concat log*, but the final-artifact decode exited 0 with no decode stderr and the diagnostic report had no final-media warnings. Input concat video time base is `1/15360`. Exploratory comparison of each warning's larger/prior DTS converted by that time base against the saved timeline's 161 cut starts found all 29 nearest boundaries within 4.47–24.82 ms (median 11.15 ms). This supports boundary-localized input timestamp overlap; it does not establish a specific source clip or root cause because the render receipt is not cryptographically bound to this timeline and the exact run's `concat_list.txt` is absent. The run temp directory was removed; current `_cleanup_temp()` deletes `concat_list.txt` and normalized clips. Do not suppress or alter DTS handling from this correlation alone. The final artifact remains fully decodable with monotonic output packet PTS/DTS and all 161 decoded cut transitions within ±1 frame in the existing cross-check.

### Timestamp-warning semantics recheck — 2026-09-29

- Re-read the surviving run-scoped `ffmpeg.stderr.log` (29 warnings) and verified the current saved project timeline SHA-256 is still `9e9f1679abea72062056a324be57a2fffe2ac54a394f75c5bbf3141fab64c967`, matching the timeline hash recorded above. All 29 prior-DTS values map to the next saved cut boundary within 4.47–24.82 ms before the cut; 24 distinct following source paths are implicated. This is correlation, not a cryptographic linkage to the old render run.
- Read-only ffprobe of those 24 original source files reports H.264 High, 30/1 fps, time base 1/90000, and 2 B-frames. Current normalization code targets HEVC for a HEVC render and requests GOP size 1 (`render_service.py` `_normalize_clips`, `_encoder_args`); however, that old run's normalized temporary files and exact `concat_list.txt` no longer exist, so the exact packet that triggered each warning cannot be attributed to a persisted intermediate.
- FFmpeg's official concat demuxer documentation states that seeking to an `inpoint` can include packets before the requested point and that timestamps may consequently overlap between concatenated files: [FFmpeg Formats — concat demuxer](https://ffmpeg.org/ffmpeg-formats.html#concat). The measured warnings' proximity to cut boundaries is consistent with this documented demuxer behavior. It does not prove that every warning is benign or identify the exact normalized-stream cause.
- No product timestamp change is justified by this evidence alone. The final MP4 independently passed full decode and had monotonic output packet PTS/DTS; all 161 visible boundaries remained within ±1 frame. Record as an observed input-concat boundary warning with no demonstrated final-artifact defect; retain as a diagnostic check for the next T017-instrumented render.

## Sampled visual review

A temporary 17-frame contact sheet sampled the artifact at 20-second intervals (0–320 s). The sampled frames share a dark teal/purple woodland/fantasy visual palette and recurring figure/locations, which gives broad visual cohesion. The sample also shows repeated-looking portal, dancer, and close-up compositions. This is a screening observation only: it does not identify exact repeated source clips, prove a narrative arc, judge the entire 337-s video, or verify that individual cuts follow musical accents. The contact sheet is `%TEMP%\pb_studio_true_peak_fix_20260929_live\contact_sheet_20s.png` and is not a durable repo artifact.

## Saved timeline and music-cut correlation

The existing QA project's read-only `timeline.json` matches the rendered master path and exact `337.176 s` timeline end. It contains 162 timeline entries, 55 unique source paths, and 161 non-initial cut starts. Every entry records `selection_path=semantic_fallback_motion` and `fallback_reason=semantic_query_embedding_unavailable`; all 162 therefore lack semantic query matching. One source is used seven times; the final two entries use the same source consecutively with source in-points 5.968 s and 0 s, the latter lasting 0.611 s. Timeline trigger metadata: 149 kick, 6 snare, 4 subtrack, 1 bass, 1 hi-hat, 1 source-repeat.

A fresh in-memory run of the production `StreamingAudioAnalyzer` on that master completed in 12.78 s (14 windows): 337.137 s decoded duration, 132.512 BPM estimate, 643 beats, 1,237 kicks, 1,474 snares, 1,395 hi-hat triggers, 100% feature coverage, no stage errors. Comparing each saved cut start to the nearest detected event: among 148 kick-triggered cut starts, median offset is 12.7 ms; 104/148 are within 60 ms and 140/148 within 120 ms; eight exceed 120 ms (maximum 746.8 ms). All six snare-triggered starts are within 120 ms of detected snare events; the sole hi-hat start is 19.5 ms from a detected hi-hat. These are same-pipeline correlation checks, not independent beat/downbeat ground truth. They provide strong evidence that this saved timeline is music-triggered, but **do not** show that the selected shots carry a semantic/narrative thread. The median cut duration is 1.869 s (range 0.611–4.783 s; 28.6 boundaries/min); whether that pace is desirable needs human review.

The rendered MP4 was then decoded once more to 64x36 grayscale frames and each of the 161 saved non-initial cut times compared to the largest frame-to-frame luminance change within ±2 frames (30 fps). All 161 had a strong local change (median delta 45.4/255 and median 17.27× local-motion baseline); 107/161 peaked at the predicted frame and the other 54/161 peaked one frame either side. Thus the actual decoded picture transitions match the persisted timeline within one output frame (33.3 ms) in this check. This supports no user-visible multi-frame cut drift despite the concat-input DTS warnings; it is not a full visual continuity or audio-content judgment.

## Application-log review and remaining quality issues

- `logs/e2e_20260928_051437.log` has 54,282 lines and ends 2026-09-28 11:03:26. It contains two distinct failed renders rejected at +1.47 dBTP; T016's 2026-09-29 render now passed at -1.58 dBTP, so those failures are historical and the corrected artifact is evidence of recovery.
- The same E2E log has four distinct provider-generation timeouts on 2026-09-28 (three Ollama calls across two model IDs, one LM Studio VLM call). These are concrete prior failures; the 2026-09-29 read-only inventory shows a caption model is available but not loaded, and does not establish inference or AMD-backend compliance. T014 remains open.
- 6,320 repeated `audio_key ... unavailable (kein Fehler)` notices correspond to clip analyses where the video has no analyzable audio track. These are stage-specific informational outcomes, not 6,320 application errors; improve aggregation/UI messaging to avoid noisy logs if they obscure real failures.
- No contemporaneous full backend/WPF user-action log for the 2026-09-29 render is present in `logs/`. Run-scoped FFmpeg evidence verifies encoding and artifact validation only; it is not a complete application-session audit trail.

## Actionable follow-ups

1. T017 now preserves a run-scoped, privacy-minimized segment manifest and binds its hashes into future `result.json` receipts. The Sep 29 artifact predates this change, so its 29 boundary-localized DTS warnings remain unattributed. A controlled future rerun can correlate warning times to exact segment order/source hashes; keep final validation unchanged and do not suppress warnings without source-level evidence.
2. For actual narrative-quality acceptance, use the authorized existing project and a reviewer-defined rubric to inspect the complete export, with timestamps and judgments for continuity, repetition, and visible defects. Sparse sampling is insufficient; persisted provenance already shows semantic query embeddings unavailable for every clip selection.
3. Capture correlated app-level render/job logs for the next approved live GUI run; keep run ID, project ID, artifact hash, and validator receipt in one evidence record.
4. T014 still needs a loaded, policy-compliant caption provider and independently human-reviewed labels. Historical provider timeouts should be diagnosed, not treated as current runtime state.
