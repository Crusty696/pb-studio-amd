# Freigegebener Reparaturplan: PB Studio Release-Video

## Freigabestatus

- Freigegeben durch Nutzer am 2026-07-29.
- Ausführung noch nicht gestartet.
- Fortsetzung des SDD-Workspaces `00013-system-wide-bug-hunting-audit`.
- Neue Tasks: T305–T339.
- Consulting-Team-Verdikt: **GO mit Modifikationen**.
- Plan-Confidence: MEDIUM.
- Zeit-Confidence vor T310: LOW.
- Realistische Dauer: 27–58 Stunden beziehungsweise 4–8 Arbeitstage.
- Jeder outputrelevante End-QC-Fehler kann 3–8 Stunden Zusatzaufwand verursachen.

## Verbindliche Grundregeln

1. `caveman` und `pb-master` sind bei jedem Task und jedem Subagenten aktiv.
2. Keine Implementierung aufgrund einer Vermutung.
3. Sachverhalte werden als `CONFIRMED`, `OPEN`, `DECIDED` oder `BLOCKED` geführt.
4. Funktions-, Regression-, Hardware-, GUI- und E2E-Tests beginnen erst in der zusammenhängenden End-QC-Phase ab T332.
5. Vorher erlaubt sind Root-Cause-Diagnostik, vollständiges Lesen und Gegenprüfen, Syntax-/XML-Prüfung, Truncation-Schutz sowie statische Vertrags- und Referenzprüfung.
6. Root-Cause-Diagnose vor der Implementierung ist zwingend. Sie ist kein Regressionstest, sondern Voraussetzung für einen belegten Fix.
7. Shared Files, öffentliche DTOs, `backend/app_state.py`, `backend/main.py` und Model Registry werden sequenziell bearbeitet.
8. Keine neue Dependency und keine Lockfile-Änderung ohne erneute Freigabe.
9. Kein Force-Push und kein automatisches Rebase bei Remote-Divergenz.
10. Bestehende fremde Änderungen im Brain-Vault werden nicht angefasst.
11. `.completed` und `.qc-passed` dürfen nur nach ihren echten SDD-Gates existieren.
12. Erfolg darf nur mit gespeichertem Nachweis gemeldet werden.

## Fortschrittsanzeige

Nach Ausführungsstart werden zwei Statusquellen gepflegt:

1. `tasks.md` ist die verbindliche Abschlussquelle. Nur `- [ ]` → `- [X]`.
2. `repair-progress.md` zeigt live:

| Task | Status | ETA | Ist-Zeit | Owner | Evidenz | Commit |
|---|---|---:|---:|---|---|---|
| T305 | `PENDING` | 0,5–1 h | – | Parent | – | – |

Erlaubte Statuswerte:

- `PENDING`
- `IN_PROGRESS`
- `BLOCKED`
- `PASS`
- `FAIL`

Ein Task wird erst `[X]`, wenn ein konkreter Evidenzpfad eingetragen ist. Bei jedem Start, Abschluss oder Blocker folgt ein sichtbares Update. Bei Langläufern erfolgt spätestens alle 30 Minuten ein Fortschrittsbericht.

## Basis-Skills

`B` bedeutet für jede Taskzeile verbindlich:

- `caveman`
- `pb-master`

## Phase 1 – Wahrheit und Governance

| Status | Task | Ergebnis | ETA / Confidence | Skills, Tools und Plugins |
|---|---|---|---|---|
| [ ] | **T305 – Evidence und Status invalidieren** | Video, Reports, Logs und Git-Zustand hashen; falsche Release-Marker entfernen; `qc-report.md` auf `FAILED/REOPENED` setzen. | 0,5–1 h / HIGH | `B`, `consulting-team`; PowerShell, `git`, `ffprobe`, `Get-FileHash`; kein Plugin |
| [ ] | **T306 – SDD und Fortschrittsledger** | Bestehende 60 Findings und neue Videoerkenntnisse deduplizieren; Requirements ergänzen; Tasks T305–T339 und `repair-progress.md` anlegen. | 1–2 h / HIGH | `B`, `consulting-team`; `rg`, Git-Diff; kein Plugin |
| [ ] | **T307 – Decision Register und Architekturprüfung** | Entscheidungen D01–D08 festhalten; Auswirkungen, Reversibilität und Abbruchkriterien dokumentieren. | 1–2 h / MEDIUM | `B`, `engineering:architecture`, `codex-security:threat-model`; Security-Plugin |
| [ ] | **T308 – Produktionsidentischer Reproducer** | Exaktes 4.816-Einträge-Manifest mit unverändertem produktiven Filter-/Encode-/Mux-Graph ausführen; vollständiges FFmpeg-Log erhalten. | 1–3 h / LOW | `B`, `rendering-expertise`; FFmpeg, ffprobe, PowerShell; kein Plugin |
| [ ] | **T309 – Stage-Isolation und Prefix-Bisektion** | Fehler nacheinander in Demux/Decode, Filter, AMF-Encoding oder Muxing lokalisieren; Bisektion nur mit nachweislich identischer Fehlersignatur. | 2–6 h / LOW | `B`, `rendering-expertise`, `gpu-expertise`; FFmpeg-Debug, Manifest-Tools; kein Plugin |
| [ ] | **T310 – Unabhängiges Design-Gate** | Root Cause durch zweiten Prüfer falsifizieren lassen; Fixdesign, Seiteneffekte und neue ETA einfrieren. Ohne belegte Ursache `BLOCKED`. | 0,5–1,5 h / MEDIUM | `B`, `consulting-team`, `caveman-review`; paralleler Read-only-Agent; kein Plugin |

## Phase 2 – Render und Export

| Status | Task | Ergebnis | ETA / Confidence | Skills, Tools und Plugins |
|---|---|---|---|---|
| [ ] | **T311 – Deterministischen EOF-Fehler beheben** | Ausschließlich die in T308–T310 bestätigte Ursache beheben. | 2–6 h / LOW | `B`, `rendering-expertise`, `gpu-expertise`; `rg`, statische Python-Prüfung; kein Plugin |
| [ ] | **T312 – Fail-closed Artefaktvalidator** | Erfolg verlangt vollständigen Decode, erwartete End-PTS, Frame-/Audiovollständigkeit und gültige Streams – nicht nur eine nichtleere Datei. | 1–3 h / MEDIUM | `B`, `rendering-expertise`, `video-expertise`; ffprobe-Schema; kein Plugin |
| [ ] | **T313 – Temp-, Resume- und Prozessisolation** | Eindeutige Jobdateien, atomarer Austausch, sichere Wiederaufnahme und kein Cross-Job-Überschreiben. | 2–4 h / MEDIUM | `B`, `rendering-expertise`, `projekt-expertise`; statischer Pfadscan; kein Plugin |
| [ ] | **T314 – Maschinenlesbarer Renderfortschritt** | `-progress`/`progress=end`, Logs, Exitcode, End-PTS und Failure-Fingerprint dauerhaft erfassen. | 1–2 h / HIGH | `B`, `rendering-expertise`, `terminal-expertise`; FFmpeg-Progress; kein Plugin |
| [ ] | **T315 – Export-Audiovertrag** | AAC-Overs verhindern, Ziel `≤ -1,0 dBTP`; 58,2 Sekunden quellseitige Endstille unverändert erhalten. Filterverfahren erst nach Messbeleg festlegen. | 1–3 h / MEDIUM | `B`, `audio-expertise`, `rendering-expertise`; FFmpeg-Audioanalyse; kein Plugin |

## Phase 3 – Audio und Pacing

| Status | Task | Ergebnis | ETA / Confidence | Skills, Tools und Plugins |
|---|---|---|---|---|
| [ ] | **T316 – Chunk-/Beat-Evidenz** | Ergebnisse und Fehler aller 254 Long-Mix-Chunks dauerhaft speichern; Teilfehler dürfen nicht als Erfolg erscheinen. | 1–3 h / MEDIUM | `B`, `audio-expertise`; SQLite-Inspektion, statischer Contract-Scan; kein Plugin |
| [ ] | **T317 – Downbeat-Provenance** | Echte Downbeats von synthetischen Annahmen trennen; keine pauschale „jeder vierte Beat“-Behauptung. | 1–3 h / MEDIUM | `B`, `audio-expertise`, `pacing-expertise`; Analyseartefakte; kein Plugin |
| [ ] | **T318 – Timeline-Grenzen normalisieren** | Startgrenze bei `0` und Ende bei Sollzeit; die bestätigte Startlücke von 1,927 Sekunden verschwindet. | 0,5–1,5 h / HIGH | `B`, `pacing-expertise`; Timeline-/Cutlist-Inspektion; kein Plugin |
| [ ] | **T319 – Snap-Provenance aktualisieren** | Nach Endpoint-Snapping werden Typ, Herkunft und Qualitätsaussage neu berechnet; keine veralteten Downbeat-Typen. | 0,5–2 h / MEDIUM | `B`, `pacing-expertise`; statischer Datenflussscan; kein Plugin |
| [ ] | **T320 – Adaptive Diversity** | Blacklist-/Wiederholungslogik berücksichtigt verfügbare Clipanzahl; keine 80-Prozent-Blacklist bei nur sechs Clips. | 1–3 h / MEDIUM | `B`, `pacing-expertise`; Cutlist-Metriken; kein Plugin |

T316–T320 bilden einen Vertrags-Freeze. Brain-Arbeit, die diese Felder konsumiert, startet erst danach.

## Phase 4 – Brain

| Status | Task | Ergebnis | ETA / Confidence | Skills, Tools und Plugins |
|---|---|---|---|---|
| [ ] | **T321 – Kanonischer Feature-Adapter** | Motion, Pace, Mood, Segmenttyp und Confidence werden aus echten Daten in normalisierten Einheiten bereitgestellt. | 2–4 h / MEDIUM | `B`, `brain-expertise`, `video-expertise`, `pacing-expertise`; Schema-/Datenflussscan; kein Plugin |
| [ ] | **T322 – Semantic Availability** | Fehlende Embeddings werden sichtbar als unavailable/partial gemeldet; keine hardcodierte Ähnlichkeit `0.5`. | 2–5 h / MEDIUM | `B`, `brain-expertise`, `model-registry-expertise`, `gpu-expertise`; SQLite/FAISS-Inspektion; kein Plugin |
| [ ] | **T323 – Kontextbezogene Credit Assignment** | Feedback aktualisiert nur relevante Achsen und Kontexte; kein identisches 6/4-Update für alle 102 Zeilen. | 2–5 h / LOW | `B`, `brain-expertise`; Architekturreview, Formelinventar; kein Plugin |
| [ ] | **T324 – Gewichte sicher behandeln** | Backup+Hash, Migration auf Kopie, Replayprüfung und Restore-Probe. Kein pauschales Löschen oder Reset. | 2–5 h / LOW | `B`, `brain-expertise`, `projekt-expertise`; SQLite-Backup/Restore; kein Plugin |

## Phase 5 – Runtime, Skripte und Verträge

| Status | Task | Ergebnis | ETA / Confidence | Skills, Tools und Plugins |
|---|---|---|---|---|
| [ ] | **T325 – FFmpeg-Version entscheiden** | 8.0.1 gegen verifiziertes 6.x-AMF-Bundle vergleichen; Projektregel 6.x nur mit Quelle, Hash, Funktionsbeleg und Rollback umsetzen. | 1–3 h / MEDIUM | `B`, `rendering-expertise`, `config-expertise`; FFmpeg-Version/Encoder-Probe; kein Plugin |
| [ ] | **T326 – Alle Start-/Setup-Skripte synchronisieren** | Setup, Start, Test, Release-QC, Konfiguration und Settings zeigen auf dieselbe geprüfte Runtime und dieselben Argumente. | 2–4 h / MEDIUM | `B`, `config-expertise`; PowerShell-Parser, `rg`; kein Plugin |
| [ ] | **T327 – Öffentliche Verträge und UI-Status** | DTOs, OpenAPI, C#-Modelle und sichtbare Fehlerzustände entsprechen den neuen Render-/Audio-/Brain-Verträgen. | 1–3 h / MEDIUM | `B`, `config-expertise`, `wpf-visual-blind-spot`; OpenAPI-/C#-Referenzscan; kein Plugin |
| [ ] | **T328 – Tests implementieren, noch nicht ausführen** | Regression-, Fault-, Security- und Full-Length-Testfälle schreiben; Ausführung bleibt bis End-QC gesperrt. | 3–6 h / MEDIUM | `B`, `auto-qa-loop`, `run-tests`, `codex-security:validation`; pytest/Testprojekte; Security-Plugin |
| [ ] | **T329 – Cross-Zone Code- und Security-Review** | Unabhängiger Read-only-Review aller Diffs; Findings müssen vor Implementierungsfreeze geschlossen werden. | 1–3 h / MEDIUM | `B`, `consulting-team`, `caveman-review`, `engineering:code-review`, `codex-security:security-diff-scan`; Security-Plugin |
| [ ] | **T330 – Referenz- und Vollständigkeitsscan** | Alle Skripte, DTOs, Dokumente, ADRs, Beispiele und Konfigurationen auf veraltete Parameter und Behauptungen prüfen. | 1–2 h / HIGH | `B`, `config-expertise`, `engineering:documentation`; `rg`, Diff-Inventar; kein Plugin |
| [ ] | **T331 – Implementierungsmarker** | Nur wenn alle Fix-Tasks `[X]` sind und T329 keine offenen High/Critical Findings enthält: `.completed` erstellen. | 0,25–0,5 h / HIGH | `B`, `caveman-commit`; Git/SDD-Prüfung; kein Plugin |

## Phase 6 – Gebündeltes End-QC

| Status | Task | Ergebnis | ETA / Confidence | Skills, Tools und Plugins |
|---|---|---|---|---|
| [ ] | **T332 – Statisch und gezielte Regressionen** | Compile-Sweep, XAML, Iron Rules, Contracts und alle neuen gezielten Tests. | 1–3 h / MEDIUM | `B`, `auto-qa-loop`, `run-tests`, `health-check`; Python 3.11, pytest, dotnet; Security-Plugin |
| [ ] | **T333 – Full Suite und Release-Build** | Komplette `Tests/`-Suite, Skip-Audit, Coverage und WPF-Release-Build. | 1–4 h / MEDIUM | `B`, `run-tests`, `health-check`; pytest, coverage, dotnet; kein Plugin |
| [ ] | **T334 – Security, Daten und Fault Injection** | Tampering, Diskfehler, Abbruch, Restore, Migration, SQLite/FAISS-Integrität und atomare Veröffentlichung. | 2–5 h / MEDIUM | `B`, `codex-security:validation`, `projekt-expertise`, `brain-expertise`; Security-Plugin |
| [ ] | **T335 – Vollständiger H.264-E2E** | Frischer 6.335,027-s-Lauf; vollständiger Decode, Frame-/Audiozählung, End-PTS, Drift, True Peak und visuelle Vollzeitanalyse. | 3–7 h / LOW | `B`, `run-pb-studio`, `video-expertise`, `audio-expertise`, `rendering-expertise`; FFmpeg/ffprobe, Videoanalyse; kein Plugin |
| [ ] | **T336 – HEVC, Resume, Cancel und AV1** | Vollständiger HEVC-Lauf; Restart/Resume/Cancel; bestehendes Ziel bleibt erhalten; AV1 meldet vor Start `unavailable`. | 3–8 h / LOW | `B`, `rendering-expertise`, `gpu-expertise`, `auto-qa-loop`; FFmpeg/AMF, Prozessmonitor; kein Plugin |
| [ ] | **T337 – GUI und Modelle** | Release-Binary, alle zwölf Bereiche, Models-Tab, Projektwechsel während Jobs, sichtbare Partial-/Failure-Zustände. | 1–4 h / MEDIUM | `B`, `wpf-gui-verification`, `wpf-visual-blind-spot`, `model-registry-expertise`; Windows UI Automation/Computer Use; kein Plugin |

## Phase 7 – Wahrheit, Dokumentation und Veröffentlichung

| Status | Task | Ergebnis | ETA / Confidence | Skills, Tools und Plugins |
|---|---|---|---|---|
| [ ] | **T338 – Finaler Wahrheitsabgleich** | `qc-report.md`, Requirement-Matrix, CHANGELOG, ADRs, Scripts, CLAUDE/Projektstatus und Brain-Log aktualisieren. Nur 100 Prozent PASS erzeugt `.qc-passed`. | 1–3 h / HIGH | `B`, `consulting-team`, `engineering:documentation`; Diff-/Evidenzscan; kein Plugin |
| [ ] | **T339 – Commits und Push** | Zonenweise Commits, Secret-Scan, `fetch`, Origin-Diff, Fast-forward-Nachweis, PB-Push, pfadbegrenzter Brain-Push und Remote-SHA-Verifikation. Kein Force-Push. | 1–3 h / MEDIUM | `B`, `caveman-commit`, `codex-security:validation`; Git CLI; Security-Plugin |

## Messbare Video-PASS-Kriterien

Ein Video gilt nur als vollständig, wenn sämtliche Punkte erfüllt sind:

- FFmpeg/Decoder beendet sich mit Exitcode 0 und ohne Decodefehler.
- Container-, Video- und Audioendzeit entsprechen der Soll-Timeline.
- Letzte Video-PTS liegt höchstens ein Ausgabeframe von der Sollzeit entfernt.
- A/V-Enddifferenz liegt innerhalb eines Video- plus eines Audiopaketintervalls.
- Erwartete und decodierte Framezahl stimmen innerhalb der begründeten Rundungstoleranz überein.
- Kein unerwarteter schwarzer oder eingefrorener terminaler Abschnitt.
- Fenster vor, bei und nach 1.962,1 Sekunden enthalten valide neue Frames.
- Gesamte Timeline wird segmentweise geprüft, nicht nur am Anfang.
- AAC True Peak `≤ -1,0 dBTP`, null Overs.
- Quellseitige 58,2-Sekunden-Endstille bleibt erhalten.
- H.264 und HEVC bestehen diese Kriterien jeweils vollständig.

## Anti-Loop-Sicherung

1. Derselbe unveränderte Befehl darf höchstens zweimal wiederholt werden.
2. Maximal drei Implementierungs-/Prüfzyklen pro eindeutiger Failure-Signatur.
3. Maximal drei gleichzeitig aktive Hypothesen.
4. Jede Hypothese benötigt vorher ein falsifizierbares Prüfkriterium.
5. 45 Minuten ohne neue Evidenz oder mehr als `2 × ETA-Obergrenze` führen zu `BLOCKED`.
6. Bei `BLOCKED`:
   1. Status, Log, Diff und Failure-Fingerprint sichern.
   2. Unabhängigen Spezialisten hinzuziehen.
   3. Genau einen begründeten Alternativweg versuchen.
   4. Bei erneut identischem Stillstand nicht weiterlaufen, sondern offen eskalieren.
7. Ein Langlauf mit wachsendem FFmpeg-`out_time`, Log oder Output gilt nicht als Stall.
8. Langläufer werden mindestens alle 15 Minuten maschinell kontrolliert.
9. Ein outputrelevanter Fix nach T335/T336 erzwingt einen erneuten vollständigen Lauf.

## Freigegebene Entscheidungen

| Entscheidung | Freigegebener Standard |
|---|---|
| **D01 – Diagnose vor Implementierung** | Ja, zwingend. Ohne Reproducer wäre der Renderfix eine Annahme. |
| **D02 – 58,2-s-Endstille** | Nicht entfernen. Quellinhalt bleibt erhalten. |
| **D03 – Audioziel** | `≤ -1,0 dBTP` und null Overs. Filterkette erst nach Messprobe. |
| **D04 – Alte Brain-Gewichte** | Kein pauschaler Reset. Replay nur bei vollständigem Eventlog; sonst versioniertes Archiv und neutraler Neustart der neuen Version. |
| **D05 – FFmpeg 8.0.1** | Bedingter Wechsel auf 6.x nach Vergleichsprobe, geprüftem AMF-Bundle, Hash und Rollback. |
| **D06 – Codec-QC** | Vollständiger H.264- und vollständiger HEVC-Lauf. |
| **D07 – Remote-Divergenz** | Kein automatisches Rebase. `BLOCKED`, Diff vorlegen, neue Freigabe. |
| **D08 – Brain-Repo** | Nur PB-Studio-Pfade committen; fremder Dirty Tree bleibt erhalten. |

Neue gegenteilige Evidenz öffnet die jeweilige Entscheidung erneut.

## Consulting-Team-Review

### Critical

- Bisheriger Release-Status ist sachlich falsch und muss als erster Ausführungsschritt invalidiert werden.
- Decode-only-Probe ist nicht ausreichend repräsentativ. Deshalb gilt Produktionsreproduktion plus stufenweise Isolation.

### High

- Tests ausschließlich am Ende erhöhen Batch-Risiko. Risikobegrenzung: kleine Commits, statische Write-Gates, Vertrags-Freeze und gestufte End-QC-Phase.
- Erfolgskriterien müssen messbar sein. Datei vorhanden oder korrekte Containerdauer reichen nicht.
- Push ist wegen 46 lokalen Commits und fremd verschmutztem Brain-Repository eigenes Release-Gate.

### Steel-Man-Alternative

Schnellere Alternative wäre, nur Rendervalidator, EOF-Ursache und AAC-Pegel zu reparieren und Brain/Pacing zu vertagen. Diese Alternative lässt bestätigte Wiederholungs-, Downbeat-, Startlücken- und Brain-Probleme bestehen und ist deshalb nicht freigegeben.

## Git- und Markerwarnung für Ausführungsstart

T305 entfernt die ungültigen Dateien `.completed` und `.qc-passed` und setzt den bisherigen QC-Status auf `FAILED/REOPENED`. Die Dateien bleiben über Git wiederherstellbar. T339 pusht nur nach Secret-, Remote-Diff- und Fast-forward-Prüfung.
