# Implementation Evidence — Spec 00034 AUDIO

## Scope

- Productive Audio import/list/delete/waveform/analysis/stem/WPF paths inspected.
- `src/pb_studio/audio/separator.py` remained untouched and locked.
- No test, build, GUI run, audio probe, provider probe, backend start, or QC marker was executed.

## Implemented

- Audio list, single delete, batch delete, beat/onset/structure/spectral reads, and waveform extraction are bound to a project operation; mutations use the project commit gate.
- Beat/onset/structure/spectral endpoints now require their actual stage to be `completed`; absent, partial, failed, or interrupted stages no longer return fabricated successful empty payloads.
- Waveform validates source existence/non-empty extraction and returns the clip's real sample rate instead of a hard-coded value.
- ffprobe metadata rejects non-finite/negative duration and invalid stream dimensions.
- BeatNet failure/empty-output fallback preserves an explicitly requested duration bound.
- Audio schema collections use isolated `default_factory` values.
- Audio Library and Media Import normalize/deduplicate paths, continue after individual import errors, suppress stale project results, clear transitional selection/state, and prevent duplicate import/stem commands.
- Existing short/long DSP, chunk evidence/resume, overlap floor/dedup, stage checkpoint merge, DirectML Beat This gate, and stem marker/resume callers were retained after source inspection.

## Deferred Verification

- T008 automated tests/builds.
- T009 live API/GUI/audio/DirectML verification.
- T010 completion/QC markers.

Runtime state: **unknown until explicit user authorization**.
