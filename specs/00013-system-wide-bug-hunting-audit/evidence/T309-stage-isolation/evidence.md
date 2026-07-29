# T309 — Stage-Isolation und Prefix-Bisektion

Status: `CONFIRMED`

## Stage matrix

| Stage | AMF | MP4 mux | Result | Conclusion |
|---|---|---|---|---|
| Frozen production graph | yes | yes | 58,863 video frames; 1,962.10 s; exit 0 | failure reproduced |
| Concat demux, stream copy to null | no | no | 701,461 packets through 6,338.71 s; exit 0 | demux does not terminate at 1,962 s |
| Native decode, no `concatdec_select`, null output | no | no | 701,461 frames; exit 0 | decoder consumes the complete packet stream |
| Native decode plus production `concatdec_select,setpts=N/FR/TB`, null output | no | no | 58,863 frames; 1,962.10 s; exit 0 | identical loss exists before AMF and MP4 mux |

AMF encoding and MP4 muxing are independently excluded as the origin of the
deterministic video EOF.

## Prefix result

The full filter-to-null run reproduced the exact 58,863-frame signature before
prefix isolation started.

- Prefix 1: 35 selected frames.
- Prefix 2: still 35 frames; the second segment contributes zero frames.
- Prefixes 3–6: still 35 frames.
- Prefix 20: 390 frames versus 985 frame-addressable target frames.
- Therefore the first failing prefix is two entries; no repeated or unbounded
  bisect loop was used.

## Concrete root cause

The six production normalization files are not frame-addressable:

- four 8 s files contain one keyframe, at 0 s;
- two 10 s files contain two keyframes, at 0 s and 8 s.

The 4,816-entry concat manifest uses random `inpoint`/`outpoint` ranges. FFmpeg
must seek each range back to the preceding keyframe, so the demux/decode path
emits 701,461 frames instead of approximately 190,000 target frames and logs
continuous DTS regressions. Under these repeated single-GOP seeks,
`concatdec_select` drops or overlaps most target ranges without returning an
error. The output then contains only 58,863 frames, while the independent audio
input continues to `-t 6335.027`; FFmpeg exits successfully.

This contract mismatch originates between:

- `_transcode_clip()`, which normalizes resolution/FPS/codec but provides no
  keyframe-addressability contract; and
- `_generate_concat_file()` / `_build_render_cmd()`, which assume that random
  in/out ranges remain frame-addressable through concat demuxing and
  `concatdec_select`.

## Independent diagnostic counterexample

The same six source clips were normalized outside the product output with the
same AMD AMF scale/FPS/codec settings plus diagnostic `-g 1`.

- Each 8 s diagnostic clip has 240 keyframes.
- Each 10 s diagnostic clip has 300 keyframes.
- Prefix 20 then produces exactly 985 frames instead of 390.
- The full 4,816-entry diagnostic manifest produces 189,948 frames and reaches
  6,331.60 s instead of 58,863 frames / 1,962.10 s.

This falsifies AMF throughput, MP4 mux duration and an early demux EOF as root
causes. It confirms missing segment-level frame addressability as the concrete
cause. GOP=1 is evidence, not yet the frozen fix design.

## Evidence

External directory:
`C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\diagnostics\T309-stage-isolation`

| Artifact | SHA-256 |
|---|---|
| `demux-copy-null.stderr.log` | `57eb3a1e3cef640937444e54842e39e3889597369b3b410e93dec5e994d0132a` |
| `filter-null.stderr.log` | `5d27bbe40cc882b611eaffc2cdabd4f4580ed7c723e9df3ee9c7f748bae6a727` |
| `decode-no-select.stderr.log` | `4da62d6de781bed4bd6f3fc640a90ec436edaca24466943c1c397863d2987df7` |
| `gop1-full-filter-null.stderr.log` | `4a3cba8900ddf9cb0e190b7a4ddad5d0d67f70944b586c442d0865a86c5184ce` |
| `prefix-20-filter-null.stderr.log` | `b64dfb34f052c09d706e36765b6937634305a281fd91cdf9b679f1b31d53947b` |
| `prefix-20-gop1-filter-null.stderr.log` | `f94d43ac65457b4fb58edd25f0b33a80c223dfbd4f70d52a2cd0a6de76cbe5c8` |

Fix design, frame-count closure, side effects and ETA remain `OPEN` for the
independent T310 gate.
