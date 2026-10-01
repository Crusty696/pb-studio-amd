# PB Studio — Vollständiger Entwicklungs- und App-Audit

**Datum:** 2026-07-31  
**Projekt:** PB Studio AMD Edition  
**Branch / HEAD:** `00013-system-wide-bug-hunting-audit` / `044fa13c70f8880d0c64d78d24667b49ea8f3eb4`  
**Audit-Typ:** Read-only Produkt-, Architektur-, Entwicklungsprozess- und Laufzeitprüfung  
**Codeänderungen:** keine  
**Gesamturteil:** **Lokal funktionsfähig, aber nicht belastbar release-ready**

## 1. Executive Summary

PB Studio besitzt einen realen, technisch starken Funktionssockel: Die aktuelle
Testsuite besteht mit **1.090 passed / 11 skipped / 0 failed**, der WPF
Release-Build endet mit **0 Warnungen / 0 Fehlern**, das Backend antwortet live,
und alle **14/14 WPF-Tabs** starten und rendern. DirectML, AMF, die
Modell-Endpunkte und die dokumentierten Full-Length-H.264-/HEVC-Evidenzen sind
substanziell.

Die aktuelle Release-Freigabe ist trotzdem nicht belastbar. Drei Befunde sind
kritisch:

1. Laufende Analyse-, Pacing- und Timeline-Operationen sind nicht durchgängig
   an das Projekt gebunden und können nach einem Projektwechsel in den neuen
   Singleton-State beziehungsweise dessen Datenbank schreiben.
2. Der WPF-Build ist aus einem sauberen Checkout nicht reproduzierbar, weil der
   ignorierte NSwag-Client bei der Projektevaluierung bereits vorhanden sein
   muss. Der letzte Main-CI-Lauf scheiterte genau daran.
3. Die aktive `spec.md` verletzt mit 47.807 Bytes das verbindliche
   10-KB-SDD-Limit.

Zusätzlich melden mehrere Persistenz-, Analyse- und Settings-Pfade Erfolg,
obwohl der dauerhafte Schreibvorgang fehlgeschlagen sein kann. Die lokale
Qualität ist damit deutlich höher als die Release-/Installationsreife.

## 2. Umfang und Methode

Geprüft wurden:

- Projektregeln, Brain-Entscheidungen, SDD-Artefakte, QC-Evidenz und Git-Historie
- Python/FastAPI/Core: Audio, Video, Brain, Pacing, Render, Daten, GPU/VRAM
- C# WPF: Views, ViewModels, Services, REST/SSE- und DTO-Verkabelung
- Tests, Build, CI, Setup, Publish, Dependencies und Security-Hygiene
- lokale Laufzeit: Backend, OpenAPI, Modell-Endpunkte und Release-GUI

Repository-Inventar:

| Kennzahl | Wert |
|---|---:|
| Getrackte Dateien | 1.419 |
| Python-Dateien | 423 / 95.323 Zeilen |
| C#-Dateien | 85 / 14.535 Zeilen |
| XAML-Dateien | 19 / 5.517 Zeilen |
| Python-Testdateien | 163 |
| Testfunktionen | 1.048 |
| FastAPI-Operationen | 63 |
| WPF Views / ViewModels | 16 / 16 |
| TODO/FIXME/HACK im Produkt-/Testcode | 0 |

Nicht jede historische Datei unter `archive/`, jede Binärdatei oder jede
gespeicherte Evidence wurde semantisch Zeile für Zeile neu auditiert. Alle
aktiven Produktzonen, UI-Flächen und Entwicklungs-Gates wurden abgedeckt.

## 3. Frische Verifikation

| Prüfung | Ergebnis | Bewertung |
|---|---|---|
| Python | 3.11.9 | PASS |
| NumPy | 1.26.4 | PASS |
| ONNX Runtime | 1.19.2; DML verfügbar | PASS |
| Kernimporte | 11/11 | PASS |
| `pip check` | keine gebrochenen Requirements | PASS |
| Pytest | 1.090 passed, 11 skipped, 45 warnings | PASS |
| WPF Release-Build | 0 Warnungen, 0 Fehler | PASS |
| Backend `/health` | HTTP 200, `status=ok`, GPU verfügbar | PASS |
| OpenAPI | 59 Pfade, 63 Operationen | PASS |
| `/models/list` | 0,02 s | PASS |
| `/models/available` | 0,03 s | PASS |
| `/models/recommendations` | 0,02 s | PASS |
| FFmpeg | 8.0.1; H.264/HEVC/AV1-AMF registriert | PASS, Encoder-Präsenz |
| WPF GUI | 14/14 Tabs, Rendering-Varianz PASS | PASS |
| App-/Backend-Shutdown | Prozesse sauber beendet | PASS |
| Gespeicherte Coverage | 57,8 % | STALE SNAPSHOT, nicht aktueller Lauf |
| Formaler Security-Scan | Plugin-Runtime fehlt | BLOCKED |

Der frische GUI-Lauf erfolgte bei 2576×1408. Alle Tabs waren auswählbar,
nicht leer und UIA-sichtbar. Der Backend-Status wechselte während des Starts
erwartungsgemäß von Offline zu Online; ab EXPORT war er online. Die App endete
mit Exitcode 0, Port 8765 war danach geschlossen.

GUI-Evidenz:

- `gui_screenshots/full_audit_20260731_000904/report.json`
- `gui_screenshots/full_audit_20260731_000904/`

Gespeicherte, nicht neu gerenderte End-QC-Evidenz vom 2026-07-30:

- H.264 und HEVC jeweils 190.051 Frames
- 6.335,027 Sekunden vollständiger Video-/Audio-Decode
- 106/106 visuelle Segmente
- keine Schwarz- oder Freezeintervalle
- RAFT, SigLIP, Moondream Vision, CLAP und Audio MDX auf RX 7800 XT

## 4. Findings nach Schweregrad

### KRITISCH

#### C-01 — Projektübergreifende State-/Datenbank-Korruption

Laufende Audio-, Video- und Pacing-Jobs erfassen zwar Eingaben, besitzen aber
keinen unveränderlichen Projektkontext beziehungsweise `project_epoch`. Nach
einem Projektwechsel schreiben ihre Fortsetzungen in den inzwischen neuen
Singleton-State und lösen die Projekt-ID erst beim Commit aus dem aktuellen
Projekt auf.

Zusätzlich kann der verzögerte Timeline-Autosave nach einem Projektwechsel
leere oder alte Entries an das neue Projekt senden. Video-/Media-Ingest-
Operationen sind ebenfalls nicht vollständig projektgebunden oder abbrechbar.

**Auswirkung:** Ergebnisse, Timeline oder Analysezustände aus Projekt A können
Projekt B überschreiben oder dort persistiert werden.

**Evidenz:**

- `backend/routers/audio_router.py:501-597`
- `backend/routers/video_router.py:443-604`
- `backend/routers/pacing_router.py:67-184`
- `backend/routers/project_router.py:299-308`
- `backend/app_state.py:354-378,591-594,780-783`
- `PBStudio.UI/Views/TimelineView.xaml.cs:114-118,470-473,552-561,707-716`
- `PBStudio.UI/ViewModels/TimelineViewModel.cs:140-146,542-563`

#### C-02 — Clean-Checkout-WPF-Build nicht reproduzierbar

`PBStudio.UI/Generated/*.g.cs` ist ignoriert. Der NSwag-Target erzeugt
`ApiTypes.g.cs` erst `BeforeBuild`, die Compile-Aufnahme wird aber bereits bei
der Projektevaluierung nur dann aktiviert, wenn die Datei schon existiert.
Lokale Builds funktionieren, weil die Datei im Arbeitsverzeichnis vorhanden
ist. Ein sauberer Checkout besitzt sie nicht.

Der letzte Main-CI-Lauf
([GitHub Actions 28985500555](https://github.com/Crusty696/pb-studio-amd/actions/runs/28985500555))
endete deshalb mit 14 `CS0234`-Fehlern.

**Evidenz:**

- `.gitignore:317`
- `PBStudio.UI/PBStudio.UI.csproj:39-49`
- `PBStudio.UI/Models/VramTelemetry.cs:9-19`
- lokale `PBStudio.UI/Generated/ApiTypes.g.cs` ist nicht getrackt

#### C-03 — Verbindliches SDD-Spec-Limit verletzt

`specs/00013-system-wide-bug-hunting-audit/spec.md` hat 47.807 Bytes und liegt
damit fast beim Fünffachen des verbindlichen 10-KB-Limits. Nach den
Projektregeln ist eine Instruktionsverletzung CRITICAL.

### HOCH

#### H-01 — HTTP-Erfolg trotz fehlgeschlagener Persistenz

Audio-/Video-Clip- und Analyse-Persistenz fängt Exceptions ab und propagiert
keinen Fehler. Import-, Analyse- und Stem-Endpunkte melden danach Erfolg.

**Auswirkung:** Daten sind in RAM sichtbar, können aber nach Neustart fehlen.

**Evidenz:** `backend/app_state.py:491-547,728-735,902-995`,
`audio_router.py:324-385,573-623,763-812`,
`video_router.py:140-178,585-638`.

#### H-02 — Partielle Videoanalyse als vollständig markiert

Ein Stagefehler erzeugt `analysis_status="partial"`, wird aber mit
`is_analyzed=True` und DB-Status `analyzed` gespeichert. Die Clip-Liste
interpretiert bereits irgendeinen Analyse-Cache-Eintrag als vollständige
Analyse.

**Evidenz:** `video_router.py:195-205,520-604`,
`app_state.py:807-842`, `video_schemas.py:12-40`.

#### H-03 — Videoanalyse-Ergebnis kann auf falschen Clip angewendet werden

`AnalyzeSelectedAsync` liest `SelectedClip` vor und nach dem Await erneut.
Wählt der Nutzer während der Analyse Clip B, kann das Ergebnis von Clip A auf
B angewendet werden. Mehrere Analysebefehle bleiben parallel aktiv und teilen
Progress-/Statusfelder.

**Evidenz:** `VideoLibraryViewModel.cs:647-783`,
`VideoLibraryView.xaml:68-95,175-185`.

#### H-04 — Persistente Löschaktionen ohne Bestätigung

„Markierte löschen“ und „Alle löschen“ entfernen Audio-/Videodaten aus
Projekt-DB, Analysezustand und bei Video aus dem Vektorindex, ohne
Bestätigungsdialog. Die UI bezeichnet die Aktion selbst als unwiderruflich.

**Evidenz:** `AudioLibraryViewModel.cs:98-139`,
`VideoLibraryViewModel.cs:243-287`,
`AudioLibraryView.xaml:107-123`, `VideoLibraryView.xaml:128-145`.

#### H-05 — DirectML-Release nicht frisch installierbar

Die für den Hardwarebeweis verwendeten ONNX-Dateien sind lokal vorhanden,
ignoriert und nicht Bestandteil von Setup oder Paket. Das Manifest enthält
Quellen und Hashes, provisioniert die Assets aber nicht.

**Auswirkung:** T363 beweist die aktuelle Workstation, nicht die
Reproduzierbarkeit einer Neuinstallation.

**Evidenz:** `.gitignore:63`, `setup_pb_studio.ps1:771-777`,
`README.md:136,142-146`, `config/directml-model-assets.json`.

#### H-06 — Kein durchgesetzter CI-/Releasepfad

Der Feature-Branch ist **71 Commits vor `main`**, Remote-HEAD und lokaler HEAD
sind identisch, aber es gibt keinen PR und keinen CI-Lauf für den Branch.
CI läuft nur für `main`/`develop`; die letzten Main-Läufe sind fehlgeschlagen.
`main` besitzt keinen Branchschutz und kein Ruleset.

#### H-07 — SDD-Gate-Test beweist Markerwahrheit nicht

`Tests/test_audit_sdd_gate.py` prüft weder offene Tasks zuverlässig noch die
Reihenfolge von `.completed` und `.qc-passed`; eine Assertion testet zweimal
dieselbe Markerexistenz. Der aktuelle Stand ist real 369/369 geschlossen, die
Automatisierung würde jedoch falsche Zustände passieren lassen.

Zusätzlich verwenden 364 Tasks nicht-kanonische Requirement-Marker; 167
historische IDs besitzen keine Definition in der aktuellen Spec.

### MITTEL

| ID | Bereich | Befund |
|---|---|---|
| M-01 | Projekt | `/project/create` erstellt Ordner/DB/Metadaten ohne vollständige Kompensation; Fehler hinterlassen einen nicht wiederholbar erstellbaren Partialzustand. |
| M-02 | Render | RenderQueue dedupliziert auch terminale Jobs; nach Restart/Fehler kann derselbe Auftrag dauerhaft HTTP 409 liefern. Der Hash berücksichtigt keine Dateiinhalte. |
| M-03 | Brain | Globale SQLite-Verbindung wird beim Projektwechsel ohne Lifecycle-Synchronisation ersetzt/geschlossen, während Worker sie verwenden können. |
| M-04 | SSE | `SSELogHandler` umgeht die Drop-Oldest-Overflow-Policy; `QueueFull` kann ungefangen im Eventloop-Callback entstehen. |
| M-05 | Settings | FFmpeg-Pfad ist editierbar, Save akzeptiert aber nur die kanonische Runtime und überschreibt die Nutzerwahl. UI-Vertrag und Verhalten widersprechen sich. |
| M-06 | Settings | Save-/Load-Fehler werden verschluckt; die UI meldet trotzdem „Einstellungen gespeichert“ beziehungsweise fällt still auf Defaults zurück. |
| M-07 | Timeline | Preview-`CancellationToken` wird im ApiClient ignoriert; alte Vorschauen können nach Projektwechsel/Dispose fertig werden. |
| M-08 | API | `GetVramTelemetryAsync(modelId)` deserialisiert die Einzelmodellantwort als Mehrmodellantwort. Der Fehler ist im aktuellen Null-Call latent. |
| M-09 | Accessibility | 162 interaktive XAML-Controls, aber keine expliziten Automation-Namen, AccessKeys oder KeyboardNavigation; Timeline-Drag/Trim/Scrub ist mauszentriert. |
| M-10 | Responsive UI | Video-Toolbar ist eine nicht umbrechende horizontale Leiste. Bei 1400×900 war sie abgeschnitten; bei der frischen 2576×1408-Prüfung war sie vollständig sichtbar. |
| M-11 | WPF Recovery | Globaler Dispatcher-Handler markiert jede beliebige Exception als behandelt und lässt die App potenziell mit halbfertigem State weiterlaufen. |
| M-12 | UI-Wahrheit | Chat-Clear und GPU-Cleanup melden Erfolg auch bei negativem/fehlendem Backend-Ergebnis; KI-Empfehlungsantworten besitzen keinen Sequenzguard. |
| M-13 | Dependencies | Kein Python-/NuGet-Lockfile, kein `global.json`, offene `>=`-Ranges; Publish-Metadaten enthalten keinen Source-Commit, SDK-Lock oder Artefakthash. |
| M-14 | Teststrategie | Keine C#-Testprojekte; WPF-Vertragstests prüfen überwiegend Quelltext. Aktuelle Coverage fehlt, 11 Skips bleiben außerhalb des Standardlaufs. |
| M-15 | Security | Kein kontinuierlicher Secret-/SCA-/CVE-Scan in CI; Dependabot Alerts deaktiviert. Begrenzter Scan fand keine bestätigten Secrets, CVE-Status bleibt unbekannt. |
| M-16 | Dokumentation | `pb-master` behauptet noch „kein CLAP auf AMD“, obwohl aktuelle Hardwareevidenz CLAP DirectML bestätigt. `.github/sddp-config.md` verweist auf fehlendes `specs/dod.md`. |

### NIEDRIG

- Manuelle Runtime-DTOs driften trotz NSwag teilweise vom OpenAPI-Modell ab;
  aktuell fehlen beispielsweise ungenutzte `SpectralData`-Felder.
- `CachedTabControl` kann bei Template-Reapply Presenter im alten Holder
  behalten; nicht live beobachtet.
- Acht `.pytest_t362_*`-Verzeichnisse sind bewusst ungetrackt und bereits in
  T369 dokumentiert.

## 5. Bereichsbewertung

| Bereich | Status | Begründung |
|---|---|---|
| Audio | Gelb | Tests/Streaming/DirectML stark; Persistenz- und Projektkontext-Wahrheit offen |
| Video | Rot | partielle Analyse und Auswahl-Race können falschen sichtbaren Zustand erzeugen |
| Pacing/Timeline | Rot | projektübergreifende Commit-/Autosave-Races |
| Rendering | Gelb | AMF, Staging, Vollvalidierung und atomisches Publish stark; Retry-Idempotenz offen |
| Brain | Gelb | DirectML/CLAP und Lernpipeline vorhanden; Connection-Lifecycle projektwechselkritisch |
| Daten/Persistenz | Rot | aktuelle DB-Evidenz stark, aber Fehlerpropagation kann falschen Erfolg melden |
| WPF/UI | Gelb | 14/14 stabil gerendert; Races, Bestätigungen, Accessibility und Responsive-Verhalten offen |
| Backend/API/SSE | Gelb | Health/OpenAPI/Modelle schnell; Status- und Overflow-Wahrheit nicht durchgängig |
| GPU/DirectML | Grün lokal | Iron Rules und Hardwarebelege stark; Asset-Provisionierung fehlt |
| Tests/Build | Grün lokal | 1.090/11/0 und 0/0; Clean-Checkout und C#-Tests fehlen |
| SDD/QC | Rot | Marker aktuell vorhanden, aber Spec-Limit und Gate-Automatisierung verletzt |
| CI/Release | Rot | kein Branch-CI/PR/Schutz; Main-CI rot; kein reproduzierbares Installationsartefakt |
| Security | Gelb/Unbekannt | keine bestätigten Secrets; formelle Scan-/CVE-Coverage nicht verfügbar |

## 6. Verifizierte Stärken

- Zentraler DirectML-Vertrag setzt beide Pflichtflags, verlangt DML und
  deaktiviert CPU-Fallback für ONNX-Inferenz.
- Keine produktiven CUDA-/ROCm-/NVENC-/libx264-/pynvml-Aufrufe in den
  auditierten aktiven Backend/Core-Zonen.
- Render-Service arbeitet über `.partial`, validiert das vollständige Artefakt
  und publiziert atomar per `os.replace`.
- Chat-Mutationen besitzen inzwischen eine technische Bestätigungsschranke.
- H.264-/HEVC-Full-Length-Evidenz, GPU-PID/LUID-Belege und Provider-Receipts
  sind ungewöhnlich detailliert.
- Backend- und Frontend-Verkabelung ist außerhalb der genannten Ausnahmen
  überwiegend konsistent; Snake-Case-JSON und OpenAPI-Drift-Test funktionieren.
- SSE besitzt Generation-/Reconnect-Schutz; Render-Fortschritt ist per Task-ID
  korreliert.
- Aktive OBJ-71-Requirement-Matrix ist vollständig in Spec, Tasks und QC
  abgebildet.
- Brain-INDEX, CLAUDE-Status, aktuelle ADR und Remote-SHAs sind konsistent.

## 7. Entwicklungsstand

Die Entwicklung zeigt hohe technische Tiefe und eine ernsthafte
Evidence-Kultur. Seit dem Statusaudit vom 28. Juli wurden die damaligen 60
Findings systematisch bearbeitet, die Testzahl stieg von 853 auf 1.090, und
echte Full-Length-/GPU-/GUI-Gates wurden ergänzt.

Das Hauptproblem ist nicht fehlende Implementierungsleistung, sondern
Governance und Reproduzierbarkeit:

- lokale Evidenz ist stärker als CI-Evidenz,
- Hardware-Assets sind stärker als Installationsautomation,
- manuelle QC-Dokumentation ist stärker als automatische Gates,
- Python-Vertragstests sind stärker als native C#-Tests,
- der Feature-Branch ist deutlich reifer als `main`, aber nicht integriert.

## 8. Priorisierte Empfehlung

### P0 — vor jeder Release-Freigabe

1. Projektkontext/Epoch serverseitig durch alle mutierenden Jobs führen und vor
   jedem Commit prüfen; Timeline-Autosave und UI-Langläufer an denselben
   Projektkontext binden.
2. Persistenzfehler bis HTTP/UI propagieren; nur dauerhafte Writes als Erfolg
   markieren.
3. Clean-Checkout-WPF-Build reparieren und auf einem frischen CI-Agenten
   beweisen.
4. `spec.md` regelkonform aufteilen und SDD-Gate-Test auf offene Tasks,
   Markerreihenfolge und Evidence-Wahrheit härten.

### P1 — Release-Reproduzierbarkeit

1. DirectML-Assets deterministisch provisionieren oder als versioniertes,
   hashverifiziertes Release-Paket bereitstellen.
2. Feature-Branch per PR integrieren; CI für Feature-/PR-Branches,
   Branchschutz und Pflichtchecks aktivieren.
3. Video-Analyse-/Selection-Race, Partialstatus und Löschbestätigungen schließen.
4. Setup/Publish mit SDK-/Dependency-Locks, Source-SHA und Artefakthashes
   reproduzierbar machen.

### P2 — Qualitätsausbau

1. Native C#-Unit-/Integrationstests ergänzen.
2. Aktuelle Coverage im CI erfassen und kritische ungetestete Pfade priorisieren.
3. Secret-, SCA- und CVE-Scanner kontinuierlich aktivieren.
4. Accessibility, kleinere API-Verträge und responsive Toolbars schließen.

## 9. Nicht verifiziert / Unsicherheit

- Kein frischer 105-Minuten-End-to-End-Lauf; dafür wurde die gespeicherte,
  aktuelle T363–T368-Evidenz geprüft.
- Keine neue echte RAFT-/SigLIP-/CLAP-/MDX-Inferenz in diesem Audit.
- Kein frischer Clean-Clone-/Setup-/Publish-Test; der Clean-Checkout-Buildfehler
  ist durch CI und Projektlogik belegt.
- Kein aktueller Coverage-Lauf; 57,8 % stammen aus der vorhandenen
  `.coverage`-Datei vom 2026-07-29.
- Der Codex-Security-Scan konnte nicht laufen: Der Connector sucht die fehlende
  Datei
  `C:\Users\david\.codex\plugins\cache\openai-curated-remote\codex-security\0.1.14\scripts\workbench_db.py`.
  Auch Status-/Abbruchaufrufe scheitern daran.
- Keine vollständige aktuelle CVE-/Supply-Chain-Aussage.

## 10. Schlussurteil

**Bewertung: GO für weitere interne Entwicklung und manuelle Tests; NO-GO für
eine reproduzierbare externe Release-Freigabe.**

Die Anwendung ist lokal nachweisbar lauffähig und technisch weit entwickelt.
Release-Blocker sind die projektübergreifenden Schreib-Races, falsche
Erfolgszustände bei Persistenzfehlern, der nicht reproduzierbare Clean-Build
und die nicht durchgesetzte CI-/Installationskette.

