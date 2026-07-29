# T335 H.264 cycle 1 root cause

Status: CONFIRMED

## Failure

- Run ID: `b495be69e38f4a5ca06c8104e6edf09f`
- Encoder completed at 190,051 frames and 6,335.027 seconds.
- Full video and audio decode completed.
- Artifact validation then failed:
  `expected=58.222062s, actual=58.334958s`.
- Persisted failure fingerprint:
  `8bfb16f17303dca0d16e5b4e760b28ba646452763d735ddd096db27617b5d962`.

## Independent reproduction

The final 135.027 seconds of the 48 kHz source were measured before and
after the production `volume=-2.0dB,aac@320k` chain.

| Stream / threshold | Silence start | Silence end | Duration |
|---|---:|---:|---:|
| Source at -60 dB | 76.804937 | 135.027 | 58.222062 s |
| AAC at -60 dB | 76.712479 | 135.040 | 58.327521 s |
| AAC at -62 dB | 76.824917 | 135.040 | 58.215083 s |

The fixed -60 dB comparison did not compensate the approved -2 dB
pre-encode gain. It therefore classified approximately 92 ms of the
unchanged fade as additional silence. AAC packetization accounts for the
remaining approximately 13 ms and remains within the 0.05-second contract.

## Repair

Source silence remains measured at -60 dB. Artifact silence is measured at
the gain-compensated threshold of -62 dB. Encoding, source content,
true-peak limit, and the 0.05-second preservation tolerance are unchanged.

Verification before cycle 2:

- Python syntax/truncation checks: PASS.
- Render/audio contract tests: 35/35 PASS.
