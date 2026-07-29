# Third-Party Licenses — PB Studio Brain Module

## ML-Modelle

### CLAP (laion/larger_clap_music) — **CC-BY-4.0**

Audio-Embedding-Modell für DJ-Mix-Charakterisierung.

> **Attribution Required.** Modell zitieren in App-Credits / About-Dialog:
>
> "Audio-Embedding by **LAION CLAP** (`laion/larger_clap_music`),
> licensed under CC-BY-4.0 — https://creativecommons.org/licenses/by/4.0/"

Source: <https://huggingface.co/laion/larger_clap_music>

### SigLIP SO400M (google/siglip-so400m-patch14-384) — **Apache 2.0**

Video-Vision-Tower für Scene-Embeddings.

Apache 2.0 ist permissiv; keine Attribution-Pflicht in der App-UI nötig.
Volltext: <http://www.apache.org/licenses/LICENSE-2.0>

## Python-Bibliotheken

| Komponente            | Lizenz       |
|-----------------------|--------------|
| torch                 | BSD-3-Clause |
| onnxruntime-directml  | MIT          |
| transformers          | Apache 2.0   |
| librosa               | ISC          |
| scipy                 | BSD-3-Clause |
| numpy                 | BSD-3-Clause |
| sqlite-vec            | MIT          |
| sqlite3 (CPython)     | Public Domain (SQLite source) |
| opencv-python         | Apache 2.0   |
| Pillow                | HPND (PIL-style permissive) |
| soundfile             | BSD-3-Clause |

## Externe Tools

- FFmpeg / ffprobe — LGPL/GPL (dynamisch verlinkt)
- UVR-MDX-NET-Inst_HQ_3.onnx — MIT

## App-Credits (Mindestumfang)

```
PB Studio nutzt unter anderem:
  • LAION CLAP (laion/larger_clap_music) — CC-BY-4.0
  • SigLIP SO400M (google/siglip-so400m-patch14-384) — Apache 2.0
  • FFmpeg — LGPL
  • UVR-MDX-NET — MIT

Alle Lizenztexte siehe LICENSES.md im Repository.
```
