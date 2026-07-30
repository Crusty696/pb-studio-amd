# T368 — Final Truth Gate

Status: CONFIRMED documentation / BLOCKED release  
Executed: 2026-07-30T09:13+02:00

## Authoritative result

PB Studio is **not release-ready**. T340–T362 and T364–T367 are confirmed;
T363 / TR-344 remains blocked. `.completed` exists after the fresh post-fix
T360 validation. `.qc-passed` is absent and must not be created.

## Gate matrix

| Gate | Result | Evidence |
|---|---|---|
| T360 implementation | PASS | `T360-post-T365-revalidation.json` |
| T361 targeted regression | PASS — 85 passed, 3 skips | `T361-targeted-regressions.xml` |
| T362 full suite/build | PASS — 1,086 passed, 12 skips; WPF 0/0 | `T362-full-suite.xml`, `T362-wpf-release.binlog` |
| T363 hardware proof | BLOCKED | `T363-rx7800xt-hardware-proof.md` |
| T364 provider/model E2E | PASS | `T364-model-e2e.md`, `T364-failover-e2e.json` |
| T365 GUI/nullable E2E | PASS | `T365-gui-analysis-e2e.md`, `T365-nullable-runtime.json` |
| T366 H.264 full length | PASS | `T366-h264-full-length-qc.md` |
| T367 HEVC full length | PASS | `T367-hevc-full-length-qc.md` |

## Blocking evidence

- Audio MDX: active RX 7800 XT DirectML load PASS.
- RAFT and SigLIP: current ONNX exports contain nodes that require the default
  CPU provider; strict `session.disable_cpu_ep_fallback=1` correctly rejects
  both sessions.
- Moondream and CLAP: required approved DirectML ONNX assets are absent.
- No compatible local alternatives were found. CPU/PyTorch, CUDA, ROCm,
  `torch-directml`, dependency changes and contract relaxation were not used.

Completion requires DirectML-only-compatible RAFT and SigLIP exports for the
pinned runtime plus approved, hashed Moondream and CLAP ONNX assets, or an
explicitly approved dependency/model-asset scope change.

## Reconciled truth sources

- `qc-report.md`
- `CHANGELOG.md`
- `CLAUDE.md`
- `tasks.md`
- `repair-progress.md`
- `specs/adrs/0003-runtime-hardware-and-provider-truth.md`
- Brain `10_Projects/PB_studio/INDEX.md`, `log.md`, and decision notes

T368 is complete because every truth source and marker now reflects the
blocked gate. This does not convert T363 to PASS and does not authorize
`.qc-passed`.
