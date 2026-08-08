# T363 — RX 7800 XT Hardware Proof

Status: CONFIRMED
Date: 2026-07-30
Scope: TR-344, SC-073

## Result

All five required workloads executed with strict DirectML on the AMD Radeon
RX 7800 XT:

| Workload | PID | Iterations | RX engine peak | iGPU peak | Dedicated VRAM peak |
|---|---:|---:|---:|---:|---:|
| RAFT | 43760 | 909 | 53.483712% | 0% | 295,043,072 B |
| SigLIP Vision | 11852 | 212 | 94.288900% | 0% | 2,987,941,888 B |
| Moondream Vision | 25268 | 352 | 87.775929% | 0% | 1,045,348,352 B |
| CLAP Audio/Text | 19472 | 3,416 | 97.152906% | 0% | 1,048,829,952 B |
| Audio MDX | 24352 | 428 | 96.182090% | 0% | 1,875,615,744 B |

Every workload reported adapter LUID `0x00000000_0x0001185b`. The iGPU LUID
`0x00000000_0x0000ffbc` showed no process DirectML load.

Canonical measurement receipt:
`evidence/T363-active-summary-20260730-105514.json`.

## Runtime contract

- Python 3.11.9
- NumPy 1.26.4
- ONNX Runtime DirectML 1.19.2
- DirectML device index `1`
- `session.disable_cpu_ep_fallback=1`
- `enable_mem_pattern=False`
- `enable_cpu_mem_arena=False`
- runtime fallback disabled for every session
- LibreHardwareMonitor state `ready`

Physical identity receipt: `evidence/T363-hardware-identity.xml`.

## Real project inputs

The newest existing project was used:
`C:\Users\david\Documents\PBStudio\New_test_juli`, database project ID `35`,
with 1 audio file and 571 video files.

- RAFT, SigLIP and Moondream used
  `C:\Users\david\Videos\video\1 (1).mp4`.
- CLAP used
  `C:\Users\david\Music\audio\psy-set\Progressive Psy Summer Dream Mix  by Crusty FREE DOWNLOAD.wav`.
- Audio MDX used a deterministic tensor with the exact model input contract
  `[1, 4, 3072, 256]`; this gate measures model/session hardware ownership,
  while the earlier audio probe separately proved the same path.

## Model assets

`config/directml-model-assets.json` records pinned repositories, revisions,
source hashes, installed hashes and transformations.

- RAFT and SigLIP were converted from the already present dynamic graphs to
  fixed supported input shapes. Strict session creation and active inference
  pass without CPU fallback.
- CLAP audio/text assets came from the pinned
  `ConceptualMachines/magda-sample-tagger` revision. The source audio graph's
  deterministic input BatchNorm and unsupported cubic Resize were externalized
  as CPU preprocessing; all neural inference remains strict DirectML.
  Source/derived embedding parity has cosine similarity `1.0000001`.
- The CLAP processor came from pinned `laion/clap-htsat-unfused` assets.
  Real audio and text embeddings are functional; live classification returned
  ordered non-neutral scores.
- Moondream's pinned vision encoder is strict-DirectML compatible and passed
  active inference. The available text decoder requires CPU-assigned nodes and
  remains intentionally absent. `is_vision_ready=True` and
  `is_ready=False`, so vision readiness never falsely claims caption readiness.

T363 requires active Moondream load, which the vision encoder satisfies.
Moondream caption generation remains explicitly unavailable and is not hidden
by this hardware result.

## Regression and build receipts

- model integration: `T363-model-integration-tests.xml`
- focused model contracts: `T363-final-focused-tests.xml`
- CLAP lock regression: `T363-clap-lock-regressions.xml`
- SDD marker gate: `T363-marker-gate.xml`
- final full suite: `T363-final-full-suite.xml`
  (`1090 passed, 11 skipped, 0 failed`)
- WPF Release: `T363-final-wpf-release.binlog`
  (`0 warnings, 0 errors`)

The full suite exposed a previously dormant self-deadlock: `SmartDirector`
held the shared non-reentrant GPU lock while `CLAPAnalyzer` attempted to
acquire it again. The redundant outer lock was removed; CLAP retains
per-session serialization and all relevant regressions pass.

## Verdict

TR-344 and SC-073 are PASS / CONFIRMED. RX 7800 XT activity, exact LUID,
process engine load and VRAM are stored for every required workload; the iGPU
was inactive for those PIDs.
