# T336 — HEVC, restart/resume/cancel, existing target, AV1

Status: CONFIRMED PASS

## Full-length HEVC artifact

- Path:
  `C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\output\release_qc_longmix_hevc_t336.mp4`
- Size: `3,687,203,928` bytes
- SHA-256:
  `9ad896ef336b3a0da72fc936efa19dcadd9931423ba40d6146316b508eb913e7`
- Encoder: `hevc_amf`, 640×360, 30 fps, 4 Mbit/s, AAC 320 kbit/s
- Frozen/finalized timeline: 4,816 contiguous entries, 0–6,335.027 s
- Encode: exit 0, `progress=end`, 190,051 frames
- Full HEVC video decode: PASS
- Full AAC audio decode: PASS
- Container/video end: 6,335.033333 s
- Audio end: 6,335.040000 s
- A/V end difference: 0.006667 s
- True peak: -1.06 dBTP; zero full-scale overs
- Source/artifact end silence: 58.222062 / 58.215083 s
- Atomic publication: PASS

Canonical product receipt:
`evidence/T336-hevc/full-export/completed.json`.

## Independent full-duration visual QC

- Full decode: exit 0 and `progress=end`
- Decoded frames: 190,051
- End time: 6,335.033333 s
- Segment coverage: 106/106 consecutive 60-second segments
- Minimum per-segment samples / unique hashes: 2 / 2
- 1,961.0–1,963.5 s: 25 samples, 25 unique hashes
- 6,275.0–6,335.027 s: 60 samples, 54 unique hashes
- Full-stream black intervals: 0
- Full-stream freeze intervals: 0

Canonical receipt:
`evidence/T336-hevc/full-visual-qc/qc-result.json`.

## Restart, resume and cancel

Executed through the real queue/router path against a byte-identical local
database copy:

- persisted `running` job restored as `interrupted`;
- startup resume reconstructed one runtime task;
- public cancel path returned `cancelled=true`;
- runtime terminal status: `cancelled`;
- queue terminal status: `failed`, error `cancelled`;
- `progress_end=false`, validation status `cancelled`;
- no resume output was published;
- live database SHA-256 stayed
  `719f552f3806f1d6e57d0eef7046071f0406cbf7bcb8839712601223302ab4f7`.

## Existing target and AV1

- Existing H.264 target SHA before/after a real cooperative cancel:
  `4bf4c2c83dd6db9a047d1e1541b237cbbfe955f7303b445dfb6fe9b3d33cc366`.
- Remaining staging files: 0.
- Real `av1_amf` functional probe: false.
- Router preflight: HTTP 503,
  `AV1 AMF ist auf dieser AMD-GPU/FFmpeg-Konfiguration nicht verfügbar`.
- No AV1 task/output was created.

Canonical receipt:
`evidence/T336-hevc/control-gates-cycle-2/control-gates.json`.

Control-gate cycle 1 stopped before GPU/output work because the package
export was imported instead of the router module. The preserved attempt
is under `evidence/T336-hevc/control-gates/`; cycle 2 used the corrected
module import and passed.

## Regression

Focused render/queue/atomic/preflight suite: 44/44 PASS in 13.84 s.
