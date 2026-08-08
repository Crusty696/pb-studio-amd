# T329 Cross-Zone Code- und Security-Review

Status: CONFIRMED
Zeitfenster: 2026-07-29T07:17:20+02:00 bis 2026-07-29T08:25:00+02:00
Ausführung: Read-only Review plus fundbezogene Reparaturen; keine Tests oder Builds

## Autoritativer Security-Scan

- Scan-ID: `57aef94d-d22d-46ca-8739-31d148f8dd1e`
- Modus: Standard / Review changes
- Snapshot: `codex-security-snapshot/v1:sha256:ef27d07b7086461a39f4513a7fd4f5cd5b6068418eba349a6838f2cd483cc7d1`
- Coverage: `1160/1160`
- Findings: `12` (`5 medium`, `7 low`)
- Finalisierung: CONFIRMED, 2026-07-29T05:40:15.309714Z
- Scan-Pfad: `C:\Users\david\AppData\Local\Temp\codex-security-scans-cIER71\Pb_studio_AMD_version\b76937ddf341fb395f81e6936612329eca85c601_20260729T051720Z_et8ekqc9`

| Artefakt | SHA-256 |
|---|---|
| `report.md` | `d3f7370d633934bd4e59d02bfb5f9b5c0aac165646950549328f986a86721780` |
| `scan-manifest.json` | `4e1e29746bac0f69f1c8146afbf16da498385de4de47361d429c35e3b4005748` |
| `coverage.json` | `b700f5f32faaa10a4fabc2cbac0f9b5e1e78fd29310b7ef9465bdb2a76021585` |
| `findings.json` | `8e20829953eeecc52c1cd3323b57178746d5d2095e4dd12502f16219d103ad5e` |

## Findings und Reparaturbezug

| Gruppe | Scan-Findings | Status | Reparaturvertrag |
|---|---:|---|---|
| Script-/Installer-Injection und ungesicherte Downloads | 1–6 | CONFIRMED | Feste `-File`-Wrapper, keine variablen `-Command`-Interpolationen, nur verifizierte winget-/Runtime-Manifestpfade |
| Persistierte Render-/Preview-Medienpfade | 7–8 | CONFIRMED | Lokale Pfadpolicy, Projektkatalog-Bindung über `clip_id`, projektgebundener Queue-Resume |
| Learning-Session-Medienpfad | 9 | CONFIRMED | Timeline-/Katalogpfad statt Dateinamen-Heuristik; WPF-LocalMediaPathPolicy vor `MediaElement` |
| Design-System Traversal | 10–11 | CONFIRMED | Label-Validierung und Root-Containment in `design_system.py` und `search.py` |
| Unauthentifizierter Brain-Reset | 12 | CONFIRMED | Prozesslokale Owner-Capability, owner-gebundene Einmaltokens, Capability auch für `/shutdown` |

## Unabhängige Review-Funde

- CONFIRMED: Render-Resume validiert vor Projekt-Restore jetzt gegen einen separat aus Projekt-ID und registrierter Projektwurzel geladenen Medienkatalog.
- CONFIRMED: Audio-/Video-Import, DB-Restore und Stem-Pacing prüfen Remote-, Device-, ADS-, Reparse- und Fremdroot-Pfade vor Dateisystem-/FFmpeg-Sinks.
- CONFIRMED: Owner-Capability wird in Backend und WPF aus der vererbten Umgebung entfernt; Ollama, LM Studio und spätere Child-Prozesse erhalten sie nicht.
- CONFIRMED: LHM lädt ausschließlich ein extern freigegebenes, vollständig manifest- und hashgebundenes Assembly-Bundle als Exact Bytes.
- CONFIRMED: Terminale Render-Failure-, Cancel- und Finalization-Timeout-Pfade persistieren und propagieren Result-/Validation-Evidence in Task- und SSE-Verträge.
- CONFIRMED: Zwei unabhängige Abschlussreviews melden `0` verbleibende OPEN/BLOCKED In-Scope-Funde.

## Statische Verifikation

| Gate | Ergebnis |
|---|---|
| Python 3.11 `compileall` für `backend`, `src`, `Tests`, Design-Scripts | CONFIRMED PASS |
| PowerShell-Parser für alle geänderten `.ps1` | CONFIRMED PASS (`7`) |
| C# Truncation-/Brace-Schutz für alle geänderten `.cs` | CONFIRMED PASS (`14`) |
| `git diff --check` über den vollständigen Working-Tree-Diff | CONFIRMED PASS |
| Verbotene Setup-Muster (`torch-directml`, CLAP/SigLIP-PyTorch-Precache, variable Download-Fallbacks) | CONFIRMED abwesend |
| Funktionale/Regression-/Hardware-/GUI-/E2E-Tests | DECIDED auf T332 verschoben |

## Restrisiko und Gate

- DECIDED: Same-user-Dateisystemmutation zwischen Pfadprüfung und Media-Sink ist im dokumentierten Single-User-Desktop-Threat-Model keine zusätzliche Privileggrenze.
- DECIDED: Hardware-Monitoring bleibt ohne extern freigegebenes LHM-Manifest und beide SHA-256-Werte deaktiviert.
- OPEN: Dynamische Wirksamkeit der neuen Verträge wird erstmals in T332 geprüft.
