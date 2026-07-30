# T366 — Fresh full-length H.264 AMF QC

Status: CONFIRMED PASS  
Executed: 2026-07-30T08:30+02:00–2026-07-30T08:43+02:00

## Artifact and frozen input

- Output:
  `C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\output\release_qc_longmix_h264_t366.mp4`
- Size: `3,688,013,674` bytes
- SHA-256:
  `4BF4C2C83DD6DB9A047D1E1541B237CBBFE955F7303B445DFB6FE9B3D33CC366`
- Encoder: `h264_amf`, 640×360, 30 fps, 4 Mbit/s, AAC 320 kbit/s
- Frozen queue job: `0f81362b-084f-414a-bc41-d8fae85a749e`
- Frozen timeline: 4,816 entries
- Finalized timeline: 4,816 contiguous entries, `0.0–6335.027 s`
- Frozen timeline SHA-256:
  `DD548D82EC6650B4EB915F2904E910EB6D16DD5F2E229CC665CE534F83C994B2`
- Finalized timeline SHA-256:
  `076E6D681D7362DB9BAB12318ADDFB0415DF26C39A5BFABD5733E2AFFFDF9A46`
- Audio SHA-256:
  `7A45A833213C4198C1C96C69D7C3890019C66E8CFC19FF151026FADBC2E0CD3`

The output path did not exist before the run. The functional AMF probe passed.
Publication used a unique staging path and occurred only after the product
validator passed.

## Product validation

- Encode exit: `0`
- Machine progress: `progress=end`
- Encoded frames: `190,051`
- Render elapsed: `588.109 s`
- Full video decode: PASS
- Full audio decode: PASS
- Container duration: `6335.033333 s`
- Video end PTS: `6335.033333 s`
- Audio end PTS: `6335.040000 s`
- A/V end difference: `0.006667 s`
- True peak: `-1.06 dBTP`
- Source/artifact end silence: `58.222062 / 58.215083 s`
- End-silence difference: `0.006979 s`
- Atomic publication: PASS

Canonical receipt:
`evidence/T366-h264/full-export-cycle-2/completed.json`
(`046FE8998260C7251BC7A1E4846AD98FA35975DA3C05344A3A9298267A7F6EF4`).

## Independent full-duration visual QC

- Full decode exit: `0`, `progress=end`
- Decoded frames: `190,051`
- End time: `6335.033333 s`
- Consecutive 60-second coverage: `106/106`
- Minimum samples / unique hashes per segment: `2 / 2`
- 1961.0–1963.5 s: `25` samples, `25` unique hashes
- 6275.0–6335.027 s: `60` samples, `56` unique hashes
- Full-stream black intervals: `0`
- Full-stream freeze intervals: `0`

Canonical receipt:
`evidence/T366-h264/full-visual-qc/qc-result.json`
(`2027F5E9A62427BB8A977BD620C362F12E54DC10DC257BAE4A65921DAEC56D00`).

## Preserved preflight attempt

Cycle 1 stopped before AMF, FFmpeg, or output creation because the reused
runner's optional router-finalizer import required repository root in the
child `PYTHONPATH`. Its stderr and PID receipt remain under
`evidence/T366-h264/full-export/`. Cycle 2 added repository root plus `src`,
used the real router finalizer, and passed.

CONFIRMED: fresh H.264 AMF output and every full-length product/visual
criterion pass over the complete `6335.027 s`.
