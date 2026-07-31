# Third-Party Licenses — PB Studio Brain Module

## ML-Modelle

### CLAP (derived DirectML ONNX) — **BSD-3-Clause AND Apache-2.0**

Audio-Embedding-Modell für DJ-Mix-Charakterisierung.

Audio-/Text-ONNX:
`ConceptualMachines/magda-sample-tagger@f24970352f239768aaad48cc8734fb298441a763`.

Processor:
`laion/clap-htsat-unfused@8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a`.

Die exakten Source-/Target-Hashes und der gebündelte Lizenztext
`licenses/CLAP-license-chain.txt` sind in
`config/directml-asset-bundle.json` gebunden.

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

- FFmpeg / ffprobe `8.0.1-essentials_build-www.gyan.dev` —
  **GPL-3.0-or-later**, statischer Windows-Build. Das gegen
  `config/ffmpeg-runtime.json` hashverifizierte Binary meldet
  `--enable-gpl --enable-version3 --enable-static`; das mitgelieferte
  `README.txt` nennt GPL v3 und den FFmpeg-Quellstand `894da5ca7d`.
- UVR-MDX-NET-Inst_HQ_3.onnx — MIT

## App-Credits (Mindestumfang)

```
PB Studio nutzt unter anderem:
  • CLAP DirectML ONNX — BSD-3-Clause AND Apache-2.0
  • SigLIP SO400M (google/siglip-so400m-patch14-384) — Apache 2.0
  • FFmpeg 8.0.1 essentials (statischer Gyan.dev-Build) — GPL-3.0-or-later
  • UVR-MDX-NET — MIT

Lizenzdetails siehe LICENSES.md. Der FFmpeg-GPL-Volltext liegt im
installierten FFmpeg-Bundle als LICENSE bei.
```
