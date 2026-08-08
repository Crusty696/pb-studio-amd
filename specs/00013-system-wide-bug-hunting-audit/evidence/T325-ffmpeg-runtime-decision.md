# T325 – FFmpeg Runtime Decision

Status: DECIDED
Decision: D05

## Active runtime

- Resolution: `config.json` → `./tools/ffmpeg/bin/ffmpeg.exe`; PATH resolves
  to the same file; `PBSTUDIO_FFMPEG_PATH` is unset.
- Version: `8.0.1-essentials_build-www.gyan.dev`
- Build includes `--enable-amf`.
- Registered encoders: `h264_amf`, `hevc_amf`, `av1_amf`.
- `ffmpeg.exe` SHA-256:
  `5AF82A0D4FE2B9EAE211B967332EA97EDFC51C6B328CA35B827E73EAC560DC0D`
- `ffprobe.exe` SHA-256:
  `192A1D6899059765AC8C39764FC3148D4E6049955956DC2029F81F4BD6A8972D`
- Existing historical hardware proof belongs to this active runtime and does
  not prove the 6.x candidate.

## Pinned 6.x candidate

- Version: `6.1.1-essentials_build-www.gyan.dev`
- Release: `https://github.com/GyanD/codexffmpeg/releases/tag/6.1.1`
- Upstream FFmpeg commit: `e38092ef93`
- Asset:
  `https://github.com/GyanD/codexffmpeg/releases/download/6.1.1/ffmpeg-6.1.1-essentials_build.zip`
- GitHub API asset size: `87,520,045` bytes; downloaded size matches.
- Asset SHA-256:
  `742E32FC9F92681F9F254B925E1B613FDD8074BA40749D4879AEFDB009B94CC5`
- Candidate `ffmpeg.exe` SHA-256:
  `04E1307997530F9CF2FE35CBA2CA7E8875CA91DA02F89D6C7243DF819C94AD00`
- Candidate `ffprobe.exe` SHA-256:
  `3A7E2DC003DC2CD1472827E4C7C4F056AE1AE0AE7C5BBC580C99B49827351BA4`
- Static capability: `--enable-amf` and all three required AMF encoders are registered.
- Staged path:
  `C:\Users\david\AppData\Local\Temp\PBStudio-FFmpeg-6.1.1-T325`

## Decision

- `6.1.1` is the pinned candidate for the project-required FFmpeg 6.x line.
- It is not activated before T332 because encoder registration is not a
  hardware-functional proof and functional/hardware tests are prohibited earlier.
- T326 synchronizes every consumer to the stable project runtime path
  `tools\ffmpeg\bin`; no consumer may select a separate binary.
- At T332, run the candidate H.264/HEVC AMF functional probes. Only on PASS:
  back up the active 8.0.1 bundle, atomically publish 6.1.1 at the stable path,
  update the runtime manifest, and rerun all T332 static/targeted gates.
- On either probe failure, retain 8.0.1, record the condition as BLOCKED against
  the 6.x activation gate, and restore/verify the pre-switch hashes.

## Comparison

| Property | Active 8.0.1 | Candidate 6.1.1 |
|---|---|---|
| Source | Gyan essentials | Gyan tagged release |
| AMF compiled | CONFIRMED | CONFIRMED |
| H.264/HEVC/AV1 listed | CONFIRMED | CONFIRMED |
| Local hardware proof | historical/current | OPEN until T332 |
| Full-length release proof | FAILED reference | OPEN T335/T336 |
| Rollback identity | hashes above | activation is conditional |

No active runtime file, config, dependency, or lockfile was changed in T325.
