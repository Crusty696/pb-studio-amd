# Clarifications: PB Studio Full Audit Remediation

## Resolved Scope and Decisions

- One new master workspace `00035-full-audit-remediation`; existing Specs 00029–00034 remain historical and unchanged.
- All 54 numbered findings are traced. Duplicate evidence points share a fix/test; conditional risks need positive and negative-path proof. Finding 54 is withdrawn and gets no product change.
- User authorized implementing the complete plan, regression/full-suite tests, builds, and API/live checks. Controlled WPF GUI operation waits until user hands over PB Studio.
- Reuse one existing QA project and approved media. Do not create repeated QA projects or delete user media/projects/old test artifacts.
- Keep existing dirty files; no commit, push, merge, install, dependency/version change, or schema/FAISS migration.
- Maintain DirectML/AMF, Python/NumPy, Windows path, and `Tests/` constraints; `separator.py` remains locked.
- Music timing/relevance is primary; narrative theme continuity is bounded and secondary; diversity breaks ties.
- The Brain `INDEX.md` and `_wiki/decisions` paths specified by AGENTS.md were absent at inspection. Existing repository ADRs 0001–0004 are the available architecture decision source.
- Live acceptance follow-up: keep the existing post-AAC `-1.00 dBTP` fail-closed gate. A real export measured `+1.47 dBTP`; remediation must make the encoded artifact pass rather than bypassing or loosening validation.
- T016 concat timestamp follow-up: retain a privacy-minimized, run-scoped ordered segment manifest before final FFmpeg encoding. Store no raw path/basename or media bytes; record a SHA-256 of the normalized source path, exact source in/out points, cumulative timeline start/end and order. Hash the canonical ordered records and exact manifest, then add both hashes to `result.json`. Use atomic exclusive creation; never overwrite an existing run's evidence. This supports forensic correlation but does not presume the concat DTS warnings are a final-artifact defect.
- 2026-09-30 user decision (T014): caption/LLM inference through LM Studio with the Vulkan llama.cpp runtime on the RX 7800 XT is permitted (`qwen3.5-9b`, Apache-2.0). This is the only exception to DirectML-only; ROCm stays forbidden (including Ollama-ROCm) and all ONNX paths stay DirectML. The human caption-accuracy rating remains required for T014.
- 2026-09-30 user handover: T013 GUI operation may proceed on the existing `t013_psy_20260930` project; the 5-clip test folder import was added there after a full backup.
- T017 precision follow-up: source in/out boundaries are serialized to six decimal places (FFmpeg concat's microsecond time base); the manifest stores those exact effective bounds. Cumulative timeline endpoints and duration use integer microseconds, avoiding binary-float drift and matching the concat input.
