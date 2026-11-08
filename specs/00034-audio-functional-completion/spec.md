# Spec 00034: Audio Functional Completion

## Objective

Complete productive Audio source paths before verification. Preserve accepted beat/downbeat provenance, DirectML-only ONNX inference, long-file streaming, and project-isolation contracts while repairing concrete import, analysis, stem, persistence, cancellation, and WPF defects.

## User Stories

### US1 — Reliable audio library

As a user, I need import, metadata, waveform, selection, deletion, and project refresh to represent only the active project's audio assets.

### US2 — Truthful musical analysis

As a user, I need BPM, beat/downbeat, key, energy, structure, spectral, drum-trigger, and long-mix results to carry exact availability and provenance without invented success.

### US3 — Safe staged processing

As a user, I need analysis and stem jobs to remain cancellable, project-bound, recoverable, and explicit about unavailable models or partial results.

## Functional Requirements

- FR-422: Import/list/delete current-project audio with validated canonical paths, stable identities, metadata, hashes, and duplicate handling.
- FR-423: Produce finite, duration-bounded BPM, beat/downbeat, key, energy, structure, spectral, waveform, onset, and drum-trigger data with provenance.
- FR-424: Route files over ten minutes through bounded streaming analysis and preserve complete chunk evidence across overlap/deduplication.
- FR-425: Bind background work, persistence, cache mutation, SSE publication, and WPF state to the initiating project and clip.
- FR-426: Keep stem separation truthful and recoverable while leaving the locked `separator.py` implementation unchanged.
- FR-427: Preserve valid completed results when optional capabilities fail; distinguish unavailable, partial, failed, interrupted, and completed states.
- FR-428: Catalog productive Audio functions and preserve implementation-only evidence while verification is prohibited.

## Technical Requirements

- TR-387: DirectML ONNX paths keep both required session flags and never silently fall back to CPU/CUDA/ROCm neural inference.
- TR-388: BeatNet/librosa DSP and documented Demucs PyTorch-CPU remain explicit allowed exceptions.
- TR-389: `src/pb_studio/audio/separator.py` is locked and must not be edited without explicit user authorization.
- TR-390: No tests, builds, GUI runs, audio probes, provider probes, or completion/QC markers without explicit user authorization.

## Out of Scope

- Editing the locked stem separator implementation.
- Adding dependencies, changing locked versions, or downloading models.
- Database/schema migrations or destructive media cleanup.
- Verification and release claims during the fix phase.

## Acceptance Criteria

- AC-1: Productive Audio UI/API/runtime paths are cataloged.
- AC-2: Concrete source defects across short/long analysis, persistence, jobs, and WPF state are repaired.
- AC-3: Missing/partial/non-finite musical evidence never masquerades as valid completed analysis.
- AC-4: Project transitions cannot publish stale Audio results or mutate another project.
- AC-5: Implementation evidence and Brain records identify edits and mark runtime verification unknown.
