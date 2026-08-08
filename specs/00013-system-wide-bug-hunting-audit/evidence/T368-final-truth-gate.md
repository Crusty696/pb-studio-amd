# T368 — Final Truth Gate

Status: CONFIRMED / RELEASE-READY
Executed: 2026-07-30

## Authoritative result

PB Studio passes every OBJ-71 End-QC gate. T340–T369 are complete,
`.completed` is current, and `.qc-passed` is authorized.

## Gate matrix

| Gate | Result | Evidence |
|---|---|---|
| T360 implementation | PASS | `T360-post-T365-revalidation.json` |
| T361 focused regression | PASS | `T363-final-focused-tests.xml`, `T363-clap-lock-regressions.xml` |
| T362 full suite/build | PASS — 1,090 passed, 11 skips; WPF 0/0 | `T363-final-full-suite.xml`, `T363-final-wpf-release.binlog` |
| T363 hardware proof | PASS — five RX 7800 XT workloads, iGPU 0% | `T363-rx7800xt-hardware-proof.md`, `T363-active-summary-20260730-105514.json` |
| T364 provider/model E2E | PASS | `T364-model-e2e.md`, `T364-failover-e2e.json` |
| T365 GUI/nullable E2E | PASS | `T365-gui-analysis-e2e.md`, `T365-nullable-runtime.json` |
| T366 H.264 full length | PASS | `T366-h264-full-length-qc.md` |
| T367 HEVC full length | PASS | `T367-hevc-full-length-qc.md` |
| Security/IRON diff review | PASS — 0 credential matches, no new forbidden runtime | current T363 diff review |

## Hardware truth

- adapter: AMD Radeon RX 7800 XT
- DirectML index: `1`
- LUID: `0x00000000_0x0001185b`
- RAFT peak: 53.483712%
- SigLIP peak: 94.288900%
- Moondream Vision peak: 87.775929%
- CLAP peak: 97.152906%
- Audio MDX peak: 96.182090%
- iGPU process load for all five PIDs: 0%

Moondream vision inference is ready. Caption generation remains explicitly
unavailable because the available decoder requires forbidden CPU-assigned
nodes. This limitation is represented by `is_ready=False` and does not weaken
or falsify the passed Moondream vision hardware workload.

## Final regression truth

The installed CLAP assets activated a previously dormant semantic path and
exposed a duplicate non-reentrant GPU-lock acquisition. The outer
`SmartDirector` lock was removed; `CLAPAnalyzer` retains per-session shared
GPU serialization. The clean final suite contains 1,090 passes, 11 justified
skips, 45 warnings and no failures.

## Reconciled truth sources

- `qc-report.md`
- `CHANGELOG.md`
- `CLAUDE.md`
- `tasks.md`
- `repair-progress.md`
- `specs/adrs/0003-runtime-hardware-and-provider-truth.md`
- Brain `10_Projects/PB_studio/INDEX.md`, `log.md`, and decision notes

T368 is PASS / CONFIRMED. `.qc-passed` may exist only while these stored
receipts and the current `.completed` marker remain valid.
