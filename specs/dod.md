# PB Studio Deployment-, Betriebs- und Releasevertrag

## Status

Dieser Vertrag definiert die Mindestbedingungen für eine Releasefreigabe.
Der laufende Reparaturplan
[`00013-system-wide-bug-hunting-audit`](00013-system-wide-bug-hunting-audit/tasks.md)
ist erst freigegeben, wenn seine Implementierung vollständig ist, sämtliche
QC-Gates echte PASS-Belege besitzen und `.qc-passed` für genau denselben
Quellstand erzeugt wurde. Frühere Builds, Testzahlen oder Hardwaremessungen
reichen nicht als Freigabe des aktuellen Worktrees.

## Autoritative Quellen

- Architektur und Cross-Stack-Regeln:
  [`.agents/skills/pb-master/SKILL.md`](../.agents/skills/pb-master/SKILL.md)
- DirectML-Modellherkunft und Transformationen:
  [`config/directml-model-assets.json`](../config/directml-model-assets.json)
- Release-Archiv, Datei- und Lizenzhashes:
  [`config/directml-asset-bundle.json`](../config/directml-asset-bundle.json)
- FFmpeg-Runtime:
  [`config/ffmpeg-runtime.json`](../config/ffmpeg-runtime.json)
- Aktuelle Umsetzung und QC:
  [`specs/00013-system-wide-bug-hunting-audit/tasks.md`](00013-system-wide-bug-hunting-audit/tasks.md)

## Setup

1. Windows 10/11, Python 3.11.x und .NET SDK bereitstellen.
2. [`setup.bat`](../setup.bat) oder
   [`setup_pb_studio.ps1`](../setup_pb_studio.ps1) ausführen.
3. Das freigegebene DirectML-Archiv muss Dateiname, Größe und SHA-256 aus
   `config/directml-asset-bundle.json` erfüllen. Die Installation erfolgt
   fail-closed über
   [`scripts/provision_directml_assets.ps1`](../scripts/provision_directml_assets.ps1).
4. Die App über [`start.bat`](../start.bat) starten. Keine Einzelpakete,
   beliebigen ONNX-Dateien oder ungebundenen FFmpeg-Binaries ergänzen.

## Verbindliche Runtime

- Python 3.11.x, NumPy 1.26.4 und `PYTHONPATH=src`.
- Neuronale ONNX-Inferenz ausschließlich mit `DmlExecutionProvider`.
- Jede DirectML-Session setzt `enable_mem_pattern=False` und
  `enable_cpu_mem_arena=False`; kein CPU-, CUDA- oder ROCm-Fallback.
- Rendering ausschließlich über freigegebene AMF-Encoder.
- Fehlende oder hashfalsche Assets ergeben einen expliziten Fehler oder
  `unavailable`, niemals stillen Ersatz.

## Modell- und Lizenzherkunft

| Asset | Gepinnte Quelle | Lizenzkette |
|---|---|---|
| RAFT Small | `pytorch/vision@61943691d3390bd3148a7003b4a501f0e2b7ac6e` | BSD-3-Clause |
| SigLIP SO400M | `google/siglip-so400m-patch14-384@9fdffc58afc957d1a03a25b10dba0329ab15c2a3` | Apache-2.0 |
| CLAP Audio/Text | `ConceptualMachines/magda-sample-tagger@f24970352f239768aaad48cc8734fb298441a763` | BSD-3-Clause AND Apache-2.0 |
| CLAP Processor | `laion/clap-htsat-unfused@8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a` | Apache-2.0 |
| Moondream Vision | `Heliosoph/moondream2-onnx@e48d8acc253b09d8f201206aa126388742298452` | Apache-2.0 |

Die vollständigen Source-, Target- und Lizenzdatei-Hashes stehen in den beiden
Manifesten. Abweichende historische Modell- oder Lizenzangaben erteilen keine
Freigabe.

## Release-Gates

- Alle Implementierungsaufgaben des aktiven Reparaturplans sind abgeschlossen.
- `.completed` bindet Aufgaben, Belege und Quellstand.
- Fault-Injection, komplette Python-Tests, native C#-Tests und WPF-Release-Build
  sind PASS.
- Externer sauberer Windows-Checkout stellt Abhängigkeiten wieder her,
  generiert den Client und validiert Assets ohne lokalen Cachevorteil.
- Alle 14 Views, Fehlerzustände, Auflösungen, DPI, Tastatur, Fokus, UIA und
  High Contrast sind belegt.
- Aktiver Projektwechsel A→B erzeugt keine projektfremden Schreibvorgänge.
- RX 7800 XT, exakter Adapter/LUID, DirectML-Flags, Modellassets und AMF sind
  auf einer frischen Installation belegt.
- Render-Deduplizierung, Retry, Neustart und Inhaltsidentität sind PASS.
- Secrets, SCA, SBOM, Lock-/Artefakthashes und Release-Commit stimmen überein.
- `.qc-passed` bindet alle QC-Belege an denselben Quellstand.
- PR, Pflichtprüfungen und geschützter Remote-Release-SHA sind verifiziert.

## Build, Prüfung und Veröffentlichung

- Tests: [`test.bat`](../test.bat)
- Release-Smoke: [`verify_release_smoke.ps1`](../verify_release_smoke.ps1)
- Publish: [`publish.ps1`](../publish.ps1)
- Hardware-QC:
  [`docs/HARDWARE_VERIFY_GUIDE.md`](../docs/HARDWARE_VERIFY_GUIDE.md)

Kein einzelner Befehl erteilt allein die Freigabe. Entscheidend sind alle
Release-Gates und ihre Belege für denselben Commit.
