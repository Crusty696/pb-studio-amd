# T315 — Export audio contract

Status: CONFIRMED

## Root cause and data flow

- Source WAV, full 6,335.027 s: `input_tp=-0.12 dBTP`.
- Existing AAC reference, full 6,335.027 s: `input_tp=+0.52 dBTP`.
- The AAC encode therefore introduced a measured `+0.64 dB` peak increase and
  produced overs.
- Source audio flows through FFmpeg input 1, the final audio filter, native AAC
  encoding, staging validation, and only then atomic publication.

## Decision and implementation

- Apply a fixed `-2.0 dB` gain before AAC. This leaves `0.48 dB` margin beyond
  the measured codec increase and does not alter duration or silence.
- Before publication, decode the complete audio stream, perform a full-duration
  EBU R128 true-peak measurement, and reject results above `-1.0 dBTP`.
- Measure trailing silence at `-60 dB`, `d=1 s` on source and staging artifact;
  reject a difference above `0.05 s`.
- Persist true peak and both silence durations in `validation.json`.

## End-silence evidence

- Source: start `6276.804938`, end `6335.027`, duration `58.222062 s`.
- Existing AAC: start `6276.824917`, end `6335.04`, duration `58.215083 s`.
- Difference: `0.006979 s`, within one AAC frame and the `0.05 s` contract.

## Evidence hashes

- Source loudnorm: `5EFEFB43CD098357A74075E0BBE6A7B4B5D9D37DFCA318BF9A8A61DAC829149D`
- Reference loudnorm: `587D4B92042837ED79726A5CC76656F5F1CBFF90F941C69ADF0A036A0C97EF52`
- Source silence: `3E6891FEA96921DABAC50FB20CC9D4F769FCC14D2A3F6235AA0A7405EA7EEA19`
- Reference silence: `A1AB1EBC5D0B45044EDBA02950344826729DAA37A2DBB98F50DDF8C5BAC23312`

Artifacts:
`C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\diagnostics\T315-audio-contract`

## Static verification

- `python -m py_compile src/pb_studio/rendering/render_service.py` — PASS
- `git diff --check -- src/pb_studio/rendering/render_service.py` — PASS
- Fresh encoded-output validation is deferred to T335/T336 as required by the
  T332 test gate.
