# T367 — Fresh full-length HEVC AMF QC

Status: CONFIRMED PASS  
Executed: 2026-07-30T08:44+02:00–2026-07-30T09:07+02:00

## Artifact and frozen input

- Output:
  `C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\output\release_qc_longmix_hevc_t367.mp4`
- Size: `3,687,203,928` bytes
- SHA-256:
  `9AD896EF336B3A0DA72FC936EFA19DCADD9931423BA40D6146316B508EB913E7`
- Encoder: `hevc_amf`, 640×360, 30 fps, 4 Mbit/s, AAC 320 kbit/s
- Frozen queue job: `0f81362b-084f-414a-bc41-d8fae85a749e`
- Frozen timeline: 4,816 entries
- Finalized timeline: 4,816 contiguous entries, `0.0–6335.027 s`
- Frozen timeline SHA-256:
  `DD548D82EC6650B4EB915F2904E910EB6D16DD5F2E229CC665CE534F83C994B2`
- Finalized timeline SHA-256:
  `076E6D681D7362DB9BAB12318ADDFB0415DF26C39A5BFABD5733E2AFFFDF9A46`
- Audio SHA-256:
  `7A45A833213C4198C1C96C69D7C3890019C66E8CFC19FF151026FADBC2E0CD3`

The output path did not exist before the run. The functional HEVC AMF probe
passed. H.264 and HEVC GPU runs were sequential. Publication used a unique
staging path and occurred only after the product validator passed.

## Product validation

- Encode exit: `0`
- Machine progress: `progress=end`
- Encoded frames: `190,051`
- Render elapsed: `882.531 s`
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
`evidence/T367-hevc/full-export/completed.json`
(`2EFED7AABDBBAC67BE932163CBC0F5F7499372A8AC026A4B2A779654BBE73FA8`).

## Independent full-duration visual QC

- Full decode exit: `0`, `progress=end`
- Decoded frames: `190,051`
- End time: `6335.033333 s`
- Consecutive 60-second coverage: `106/106`
- Minimum samples / unique hashes per segment: `2 / 2`
- 1961.0–1963.5 s: `25` samples, `25` unique hashes
- 6275.0–6335.027 s: `60` samples, `54` unique hashes
- Full-stream black intervals: `0`
- Full-stream freeze intervals: `0`

Canonical receipt:
`evidence/T367-hevc/full-visual-qc/qc-result.json`
(`0B8D3DBA5FA5BAA1522E3B29533710D3CBE19851648AD48F211D5906CABF94CA`).

No T367 runner or FFmpeg process remained after validation.

CONFIRMED: fresh HEVC AMF output and every full-length product/visual
criterion pass over the complete `6335.027 s`.
