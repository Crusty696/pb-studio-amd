# T308 — Produktionsidentischer Reproducer

Status: `CONFIRMED`

## Frozen inputs

- Queue job: `0f81362b-084f-414a-bc41-d8fae85a749e`
- Persisted settings JSON: 7,982,230 bytes; SHA-256 `cbe3da460b924dd16868939030327f804e7439633e09fdb4cc45b96248e9772f`
- Timeline snapshot: 4,816 entries; canonical SHA-256 `dd548d82ec6650b4eb915f2904e910eb6d16dd5f2e229cc665ce534f83c994b2`
- Generated concat manifest: 765,744 bytes; SHA-256 `0d5115a198718e12b1c19a5536cb3c9309bcdccc96caab79e7193ab1049ee3a3`
- Audio: 6,335.027 s; SHA-256 `7a45a833213c4198c1c96c69d7c3890019c66e8cfc19ff151026fadbcce2c0d3`
- Normalized input clips: the six archived production files, individually hashed in `started.json`

## Production graph

The reproducer called the current production methods
`RenderService._generate_concat_file()` and `RenderService._build_render_cmd()`.
The filter, encoder and mux arguments were unchanged:

`-f concat -safe 0 -segment_time_metadata 1 -map 0:v -map 1:a -vf select=concatdec_select,setpts=N/FR/TB -c:v h264_amf -rc cbr -quality balanced -b:v 4M -c:a aac -b:a 320k -movflags +faststart -stats_period 0.5 -t 6335.027`

Only the output path was redirected to the isolated diagnostics directory. The
reference output was not opened for writing.

## Long-run monitoring

| Check | PID | Running | Log bytes | Output bytes | out_time | Result |
|---|---:|---|---:|---:|---|---|
| 02:26:44 | 2428 | yes | 54,601 | 74,711,088 | 00:02:07.73 | growing |
| 02:29:17 | 2428 | yes | 334,537 | 493,879,344 | 00:14:08.26 | growing |
| 02:31:11 | 2428 | yes | 544,487 | 805,044,272 | 00:23:01.06 | growing |
| 02:33:28 | 2428 | yes | 766,695 | 1,161,035,824 | 00:39:55.02 | audio continued; video frame count frozen |
| 02:36:42 | 2428 | no | 804,151 | 1,332,887,476 | completed | exit 0 |

No stall occurred.

## Reproduced failure signature

- FFmpeg exit code: `0`
- Elapsed: 594.266 s
- Output size: 1,332,887,476 bytes
- Output SHA-256: `efed6650ed5db3bb507e58f48986d2003d389500cc503b88c1c6eea7e4f45050`
- Reference SHA-256: `efed6650ed5db3bb507e58f48986d2003d389500cc503b88c1c6eea7e4f45050`
- Result: byte-identical reproduction
- Video froze at 58,862 progress frames and approximately 1,962.06 s while
  the audio/mux clock continued to 6,335.027 s.
- The complete FFmpeg stderr log is preserved externally at
  `C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\diagnostics\T308-production-reproducer\ffmpeg.stderr.log`
  with SHA-256 `635d3aba19dcbc3e035163c7ab61d05cefcaaf6e194e89a1398e909bf419b368`.
- `started.json`, `completed.json`, `concat_list.txt`, PID and exit-code files
  are preserved in the same directory.

The failure is deterministic under the frozen production graph. Its stage and
cause remain `OPEN` for T309.
