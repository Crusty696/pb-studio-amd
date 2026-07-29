# T305 Evidence Freeze — 2026-07-29

## Status

- Task: T305
- Result: CONFIRMED
- Captured: 2026-07-29T02:12:55+02:00
- Release state: FAILED / REOPENED / NOT RELEASE-READY
- Tests executed: none

## Git state

- Branch: `00013-system-wide-bug-hunting-audit`
- HEAD: `b76937ddf341fb395f81e6936612329eca85c601`
- Upstream: `origin/00013-system-wide-bug-hunting-audit`
- Upstream HEAD: `a4b227d2f291f65c46109810fc9a3faf1bd956b8`
- Ahead/behind: `+46/-0`
- Pre-change dirty state: one untracked file, `approved-repair-plan-2026-07-29.md`
- Canonical Git-state SHA-256: `02f53fbd9d82f841c491bf5138d7d0bdf0883022cae56e6f6fc1e943e1a0ec42`

## Reference-video finding

- File: `C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\output\release_qc_longmix_h264.mp4`
- Size: 1,332,887,476 bytes
- SHA-256: `efed6650ed5db3bb507e58f48986d2003d389500cc503b88c1c6eea7e4f45050`
- Container duration: 6,335.027 s
- Audio duration: 6,335.027 s
- Video duration: 1,962.100 s
- Declared video frames: 58,863 at 30 fps
- Existing full-frame scan: 58,848 decoded frames; decoded duration 1,961.600 s
- Existing scan warning: OpenCV/FFmpeg packet-read maximum attempts exceeded.
- Release criterion: FAIL. Video stream ends 4,372.927 s before expected timeline end.

The recovery partial and published output are byte-identical:

- Partial SHA-256: `efed6650ed5db3bb507e58f48986d2003d389500cc503b88c1c6eea7e4f45050`
- Published SHA-256: `efed6650ed5db3bb507e58f48986d2003d389500cc503b88c1c6eea7e4f45050`

## Frozen release inputs

| File | Bytes | SHA-256 |
|---|---:|---|
| `ReleaseQC_20260728_1245/project.json` | 292 | `7ebc33767cff16841a19cfe2e5f69f2d255746a9b22cf02081eff532067892b0` |
| `ReleaseQC_20260728_1245/timeline.json` | 11,401,124 | `365780b025239009f5a6d6f5e6ee15256a38528369da013f72fdd132f5826d97` |
| `ReleaseQC_20260728_1245/state.db` | 19,791,872 | `fcdc7bd66d30e4b1138dfc831673ee84c82ef5c75e7be92de1a43ffb5d89c7f4` |

## Frozen reports and logs

| File | Bytes | SHA-256 |
|---|---:|---|
| `FULLSTACK_STATUS_AUDIT_PB_STUDIO_2026-07-28.md` | 21,460 | `79615d2df8faa237f4976407d38876a8c6fda496259c0e4f6eeb2a792372c0ca` |
| `qc-report.md` before T305 | 16,033 | `3849aa258afefcdab5f757fabb9ab2078e87225a021f886cdeaa169b1c3600c4` |
| `logs/backend.log` | 404,204 | `eeef002f598b5b3dc44b8f700ce997b6acc4b11e20db1d8200014d663e43217e` |
| `logs/driver_backend.err.log` | 202 | `dca8eeef922b9de646ee6e58b4ad624a9912f773bcae87d6cbf7a118baf3aee7` |
| `logs/driver_backend.out.log` | 8,867 | `e048c240ca0d8a1b16e6257673fe82a1602600d4ef5583ff2a08c68f6f130826` |
| `logs/full_video_frame_scan.err.log` | 260 | `3bc9cee4d53772449f896d2ac4bcdbcbc9deb3133fc29b33a1aaefb227b28319` |
| `logs/full_video_frame_scan.out.log` | 5,879 | `199e81de08bff52024ccd941e6fbe447371ee1b03e7fdbaaa4a98068e5fc58ee` |

## Invalidated markers

| Marker | Pre-delete SHA-256 | Pre-delete content |
|---|---|---|
| `.completed` | `e1b8ecffacf5b14c702bd81283455865a7f0a27be60c3874487923f96b1fae17` | `Implementation complete: 60/60 release-readiness findings closed.` |
| `.qc-passed` | `d64aa767defd520cda0473093d5bbb4d9a7854f96d464e1541d7238de5460f2a` | `QC passed 2026-07-28: 60/60 findings PASS; 966 tests passed, 11 justified skips, 0 failures.` |

## Toolchain observation

- Active ffprobe: `tools\ffmpeg\bin\ffprobe.exe`
- Version: `8.0.1-essentials_build-www.gyan.dev`
- FFmpeg 6.x decision remains OPEN until T325.
