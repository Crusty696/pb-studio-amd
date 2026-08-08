# T332 Static and Targeted Regressions

Status: CONFIRMED
Ausgeführt: 2026-07-29T10:19:00+02:00–2026-07-29T10:35:00+02:00
Owner: Parent + read-only static/security reviewer

## Environment

| Vertrag | Ergebnis |
|---|---|
| Python | CONFIRMED 3.11.9 |
| NumPy | CONFIRMED 1.26.4 |
| ONNX Runtime | CONFIRMED 1.19.2 |
| DirectML | CONFIRMED `DmlExecutionProvider` verfügbar |
| FAISS | CONFIRMED 1.7.4 |
| FFmpeg runtime contract | CONFIRMED PASS |
| AMF registration | CONFIRMED `h264_amf`, `hevc_amf`, `av1_amf` |

## Root cause and corrections

Der erste gezielte Lauf ergab 61 PASS und vier Testfehler. Vor Änderungen
wurden Datenfluss, Caller und Produktverträge unabhängig geprüft:

- Der Render-Test importierte den öffentlichen `APIRouter` statt des
  `backend.routers.render_router`-Moduls. Der Paketexport blieb unverändert;
  nur der Test importiert das Modul jetzt explizit.
- Das Pacing-Testdouble ließ den vertraglich vorhandenen `clip_selector` eines
  echten `AdvancedPacingEngine` aus. Nur beide Testdoubles wurden ergänzt.
- Die LHM-Assertion verglich eine textuelle `Assembly.Load`-Position innerhalb
  einer erst später aufrufbaren Resolver-Funktion. Sie prüft jetzt die erste
  Load-Stelle nach der registrierten Resolver-Grenze.
- Der statische Vertragscheck fand, dass Backend/OpenAPI
  `has_audio_embedding` liefern, während der C#-DTO das Feld verwarf.
  `AudioClipInfo` enthält jetzt das optionale, rückwärtskompatible
  `HasAudioEmbedding = false`; direkte Konstruktor-Caller existieren nicht.

Ein fokussierter Retest wurde einmal durch einen falschen PowerShell-
Zeilenfortsetzer auf den Pfad `\` fehlgeleitet. Nach PID-/Commandline-Prüfung
wurde ausschließlich der eigene pytest-Prozess beendet. Der korrigierte
Argumentlisten-Aufruf bestand 4/4; es gab keine blinde Wiederholung.

## Ergebnisse

| Gate | Ergebnis |
|---|---|
| Gezielte neue Regressionen | CONFIRMED PASS, 65/65 |
| WPF Release-Build | CONFIRMED PASS, 0 Warnungen, 0 Fehler |
| Python Compile-Sweep | CONFIRMED PASS, 346/346 statisch; 324/324 Parent-Nachlauf |
| PowerShell-Parser | CONFIRMED PASS, 28/28 |
| JSON | CONFIRMED PASS, 22/22 Reviewer; 60/60 Parent-Nachlauf |
| XAML/XML | CONFIRMED PASS, 19/19 |
| Truncation | CONFIRMED PASS, 154/154 |
| IRON R1–R5, R7–R8 | CONFIRMED PASS |
| `AudioClipInfo` C#/OpenAPI | CONFIRMED PASS, 17/17 |
| `git diff --check` | CONFIRMED PASS |

## Security point validation

- Owner-Capability schützt `/shutdown` und `/brain/reset`.
- Medienpfade werden vor Render-Sinks kataloggebunden validiert.
- Design-System-Projekt- und Seitenpfade werden auf erlaubte Labels und
  direkte Kindpfade begrenzt.
- OpenAPI enthält Owner-Header sowie 403/503-Verträge.
- Kein neuer Security-Scan wurde gestartet.

## Gespeicherte Testbelege

| Datei | SHA-256 |
|---|---|
| `T332-targeted-pytest-rerun.log` | `8E4313702F299CA04EE0B0167A4B1455C8104CE296727C5887C252199BF1B02D` |
| `T332-wpf-release-build.log` | `80D98D06D4609D0CE1E63E0EDC866D948C6CCFEF76EEB0B1F64A0256B1F4569C` |

OPEN: Full Suite, Coverage und Skip-Audit beginnen in T333.
BLOCKED: none.
