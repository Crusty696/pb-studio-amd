# T335 — Fresh full-length H.264 AMF E2E

Status: CONFIRMED PASS

## Artifact

- Path:
  `C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\output\release_qc_longmix_h264_t335.mp4`
- Size: `3,688,013,674` bytes
- SHA-256:
  `4bf4c2c83dd6db9a047d1e1541b237cbbfe955f7303b445dfb6fe9b3d33cc366`
- Encoder: `h264_amf`, 640×360, 30 fps, 4 Mbit/s, AAC 320 kbit/s
- Frozen queue job: `0f81362b-084f-414a-bc41-d8fae85a749e`
- Finalized timeline: 4,816 contiguous entries from 0 to 6,335.027 s

## Product validation

- FFmpeg encode: exit 0, `progress=end`
- Encoded frames: 190,051
- Full video decode: PASS
- Full audio decode: PASS
- Container duration: 6,335.033333 s
- Video end PTS: 6,335.033333 s
- Audio end PTS: 6,335.040000 s
- A/V end difference: 0.006667 s
- True peak: -1.06 dBTP; zero full-scale overs
- Source end silence: 58.222062 s
- Artifact end silence: 58.215083 s
- End-silence difference: 0.006979 s
- Atomic publication: PASS

Canonical receipts:

- `evidence/T335-h264/cycle-2/completed.json`
- `output/.render_evidence/t335-h264-full-length-cycle-2/326070b1c4a7401793f29fc1d5389176/result.json`
- `output/.render_evidence/t335-h264-full-length-cycle-2/326070b1c4a7401793f29fc1d5389176/validation.json`

## Independent full-duration visual QC

- Full decode: exit 0 and `progress=end`
- Decoded frames: 190,051
- End time: 6,335.033333 s
- Segment coverage: 106/106 consecutive 60-second segments
- Minimum per-segment samples: 2
- Minimum per-segment unique hashes: 2
- 1,961.0–1,963.5 s window: 25 samples, 25 unique hashes
- 6,275.0–6,335.027 s terminal window: 60 samples, 56 unique hashes
- Full-stream black intervals: 0
- Full-stream freeze intervals: 0

Canonical receipt:
`evidence/T335-h264/full-visual-qc/qc-result.json`.

## Repair cycle

Cycle 1 failed only the end-silence comparison because the validator used
the same -60 dB threshold before and after the approved -2 dB gain. The
independent tail reproduction proved the data was preserved and the
measurement threshold was not gain-compensated. The artifact measurement
now uses -62 dB while the source remains at -60 dB. The complete cycle-1
failure and root-cause evidence remain under `evidence/T335-h264/`.
