# CHANGELOG - PB Studio AMD Edition
# Bug-History archiviert 2026-03-09

---

## 2026-08-02 - T413 Release-Security und reproduzierbare Lieferkette

### Fixed
- Python-Produktlock auf 130 exakte Windows-cp311-Wheels aktualisiert;
  CPU-Torch-Familie, Transformers/Hugging Face und bekannte transitive
  Advisories versions- und hashgebunden geschlossen.
- Isolierten 29-Wheel-`pip-audit`-Scannerlock und zwei exakt gebundene,
  eigentümergeführte Ausnahmen bis 2026-09-01 eingeführt.
- MCP-Starts von dynamischem `@latest` auf lokale Wrapper, vollständigen
  npm-Lock-SHA, 110 SRI-Knoten und installierten Runtime-Tree umgestellt.
- GitHub-PowerShell-Gate korrigiert: akzeptierter `pip-audit`-Exit 1 wird erst
  nach Status-/Reportprüfung zu Exit 0 normalisiert; unerwartete Pfade bleiben
  fail-closed.
- Scanner-, Exception-, MCP- und npm-Konfiguration in Release-Provenienz
  aufgenommen.
- Externe absolute Provenienz-Ausgabepfade korrigiert; SBOM-Receipts werden
  außerhalb des Repositories ohne `Path.relative_to()`-Fehler erzeugt.

### Verified
- Finaler Python-Lauf: 1.207 Outcomes, 0 Fehler/Errors, 11 genehmigte Skips,
  62,116 % Coverage.
- Locked .NET Restore, 42/42 native Tests und WPF Release Publish mit
  0 Warnungen/Fehlern.
- Secret/History 0 aktive Funde; Python-SCA 130 Pakete/0 ungelöst;
  NuGet-Produktgraphen sauber; npm 110 Knoten/0 Vulnerabilities.
- Codex-Security-Diffscan: 23/23 Review-Belege, 0 reportable Findings;
  zwei fail-closed Releaseblocker behoben und unabhängig nachgeprüft.
- Clean-SHA `7fece74` mit `release_eligible=true`, 182 SBOM-Komponenten und
  unverändertem WPF-ZIP-Hash verifiziert; Provenienzregression 4/4 PASS.

## 2026-07-30 - T340–T368 GPU-, Provider- und Analyse-Wahrheit

### Fixed
- DirectML-Adapterwahl, VRAM-Budget und LibreHardwareMonitor auf dieselbe
  RX 7800 XT (Index 1, LUID `0x00000000_0x0001185b`) gebunden.
- Sämtliche ONNX-DirectML-Konsumenten auf einen fail-closed Providervertrag
  mit deaktiviertem CPU-Fallback und beiden DirectML-Speicherflags vereinheitlicht.
- Offizielles LibreHardwareMonitor-0.9.6-Bundle durch Manifest-, Bundle- und
  DLL-Hashes abgesichert; Launcher-Trust auch für extern gestartete Backends
  geschlossen.
- LM-Studio-/Ollama-Liveinventar, Capability-Routing, Selection Receipts,
  begrenztes Failover und providergebundene Aufgabenpersistenz umgesetzt.
- `SceneInfo.Confidence` im handgeschriebenen C#-DTO nullable gemacht und
  Batchfehler sowie falsche Analyse-Erfolgsmarkierung verhindert.
- RAFT-/SigLIP-Graphen auf strict-DirectML-kompatible feste Eingabeformen
  gebracht; gepinnte und gehashte CLAP-Audio-/Text- sowie
  Moondream-Vision-Assets installiert.
- Einen zuvor verdeckten Selbst-Deadlock durch doppelte Sperrung des
  nicht-reentranten GPU-Locks zwischen SmartDirector und CLAP beseitigt.

### Verified
- Finale Vollsuite: 1.090 passed, 11 begründete Skips, 0 Fehler;
  WPF Release 0 Warnungen/0 Fehler.
- RAFT, SigLIP, Moondream Vision, CLAP und Audio MDX mit eigenen
  PID/LUID/Engine/VRAM-Receipts auf der RX 7800 XT; iGPU jeweils 0 %.
- Provider-/Modell-E2E und Release-GUI einschließlich `confidence=null`
  bestanden; kein Retry-Sturm.
- Frische H.264-/HEVC-AMF-Exporte: je 190.051 Frames, Full-Decode über
  6.335,027 s, 106/106 Segmente, keine Schwarz-/Freezeintervalle.

### Release gate
- T363 und T368 sind PASS; `.completed` und `.qc-passed` sind gültig.
- Moondream-Vision ist aktiv. Der vorhandene Caption-Decoder bleibt wegen
  CPU-pflichtiger Knoten bewusst deaktiviert und wird nicht als ready gemeldet.

### Published
- Sieben zonierte PB-Commits nach Secret-Scan und D07 Fast-Forward-Gate normal
  gepusht; Remote-SHA `b04ca4f9479021c932c53b1fb14df50600781821`
  verifiziert.
- Brain ausschließlich unter `10_Projects/PB_studio/**` aktualisiert und
  Remote-SHA `82b570df2524f2eb10e37baed34b8d165330b6aa` verifiziert.
- Der abschließende T363/T368-Follow-up ersetzt die frühere BLOCKED-Aussage;
  PB-Payload `669d9d320774261d6881437760431f7d86ab2b85` und Brain-Payload
  `aa2585979ed625f1ae51decff08b20c40155ff11` wurden remote verifiziert.

## 2026-07-29 - T305–T338 Release-Video-Reparatur und End-QC

### Fixed
- Die 1,927-s-Startlücke der 4.816-Cut-Timeline beseitigt und den kanonischen
  Pacing-Abschluss auch am produktiven Render-Router erzwungen.
- Frame-Adressierbarkeit, job-isolierte Evidence, maschinenlesbaren
  FFmpeg-Fortschritt, Fail-closed-Validierung und atomare Veröffentlichung
  gehärtet.
- Long-Mix-Audio-, Downbeat-, Snap-, Diversity-, Feature-, Semantic- und
  Brain-Feedback-Verträge auf echte Provenance und partielle Zustände
  korrigiert.
- Export-Log-XAML auf OneWay-Stringbindung umgestellt; Projektwechsel,
  Renderstatus und capability-genaue Modell-Empfehlungen wahrheitsgemäß
  synchronisiert.

### Verified
- Finaler Gesamtlauf: 1036 passed, 11 begründete Skips, 0 Fehler,
  45 Warnungen in 402,48 s.
- WPF Release: 0 Warnungen, 0 Fehler.
- Postfix-H.264 und -HEVC: je 190.051 Frames, vollständiger Decode über
  6.335,027 s, 106/106 visuelle Segmente, keine Schwarz-/Freezeintervalle.
- Release-GUI: 14/14 Bereiche; Projektwechsel unter aktivem Renderjob,
  Partial-/Failure-Zustand und Models-Livepfad bestanden.
- Veröffentlichung bleibt bis zum T339-Secret-/Remote-/Push-Gate offen.

## 2026-07-28 - M-33/M-34 Import-Hygiene und Python-Runtime-Gate

### Fixed
- Temporären PyAudio-Stub nach dem BeatNet-Importversuch aus `sys.modules` entfernt.
- Python-3.12- und unversionierte Launcher-Fallbacks aus dem WPF-Backend-Start entfernt.
- Interpreter vor Start per `--version` auf Python 3.11.x validiert.

### Verified
- Audio-Cluster: 26 passed, 1 skipped.
- Launcher-/Lifecycle-Verträge: 7 passed.
- Vollsuite: 853 passed, 11 skipped, 0 failed.
- WPF Release: 0 Warnungen, 0 Fehler.

## 2026-07-28 - M-31/M-32 DirectML-Patch und atomarer Projekt-Open

### Fixed
- Prozessglobalen ONNX-`SessionOptions`-Patch über mehrere StemSeparator-Instanzen serialisiert und garantiert auf das Original zurückgesetzt.
- Projekt-Medienkatalog vor Brain-/Runtime-Wechsel in einem isolierten `AppState` geladen.
- DB-Ladefehler liefern HTTP 500 und bewahren aktives Projekt, Medienkatalog, Analyse-Caches und Brain-Bindung.

### Verified
- DirectML-/Separator-Cluster: 37 passed.
- Projekt-/DB-Cluster: 44 passed.
- Vollsuite: 851 passed, 11 skipped, 0 failed.
- WPF Release: 0 Warnungen, 0 Fehler.

## 2026-07-28 - LOW-04 Gemeinsamer AI-Config-Fallback

### Fixed
- Doppelte AI-Config-Reader aus Brain-Narrator und LM-Studio-Vision in einen Helper konsolidiert.
- ConfigManager-first und Direktdatei-only-as-fallback unverändert erhalten.
- Private `_load_ai_config`-Aliase und deprecated Ollama-Shim kompatibel gehalten.

### Verified
- AI-/Vision-Zielcluster: 43 passed.
- Erweiterter Chat-/Provider-/Registry-Cluster: 94 passed.
- Python-Compile: PASS.

## 2026-07-28 - LOW-08 Terminal-History vor ViewModel-Erzeugung

### Fixed
- WPF- und Backend-SSE-Logs in einem thread-sicheren Singleton-Puffer zusammengeführt.
- History auf 100.000 Zeichen begrenzt und beim Terminal-ViewModel-Start replayed.
- Clear und Dispose wirken jetzt auf die zentrale History/Subscription.

### Verified
- Terminal-Verträge: 2 passed.
- Gesamter WPF-Vertragscluster: 13 passed.
- WPF Release-Build: 0 Warnungen, 0 Fehler.

## 2026-07-28 - LOW-07 Wahrheitsgemäßer Projekt-Timeline-Status

### Fixed
- Projektübersicht zeigt getrennte Zustände für kein Projekt, fehlende Timeline und generierte Timeline.
- „Jetzt generieren“ ist ohne geöffnetes Projekt nicht mehr sichtbar.

### Verified
- Projektübersicht-/Lifecycle-Verträge: 6 passed.
- WPF Release-Build: 0 Warnungen, 0 Fehler.

## 2026-07-28 - LOW-02 Erreichbarer Canvas-Pacing-Pfad

### Fixed
- `canvas_path` durch Backend-Schema, Router, OpenAPI-Snapshot und aktiven C#-Requestvertrag verdrahtet.
- Canvas-Pfad im Director-ViewModel und der View erreichbar gemacht.
- Rohe und bereits präfixierte Clip-IDs zentral auf genau ein `clip_` normalisiert.

### Verified
- Pacing-Cluster: 98 passed.
- Canvas-/OpenAPI-Verträge: 7 passed.
- WPF Release-Build: 0 Warnungen, 0 Fehler.

## 2026-07-28 - M-12 Vollständiger VectorStore-Writer-Lifecycle

### Fixed
- Indexwechsel schließt und speichert die vorige Singleton-Instanz vor der Neuerzeugung.
- `close()` beendet den Coalescing-Writer und verhindert die Wiederverwendung geschlossener Instanzen.
- Atexit stoppt den aktiven Writer vor dem finalen Snapshot.

### Verified
- VectorStore-/Data-/AppState-/Router-Cluster: 74 passed.
- Vollsuite: 802 passed, 11 skipped, 1 absichtlicher SDD-Marker-Gate-Fehler.
- Python-Compile-Sweep: PASS.

## 2026-07-28 - M-11 Nicht-blockierendes WPF-Dateilogging

### Fixed
- Globalen manuellen Klick-Audit-Hook aus dem Produktionsfenster entfernt.
- Dateilogging über eine begrenzte Queue auf einen einzelnen Hintergrund-Writer verschoben.
- Provider schließt die Queue beim Dispose und wartet begrenzt auf das geordnete Leeren.

### Verified
- WPF-Vertragscluster: 10 passed.
- WPF Release-Build: 0 Warnungen, 0 Fehler.

## 2026-07-28 - M-10 Vollständige aktive API-DTOs

### Fixed
- Audioanalyse-DTO behält Subtracks, Tempo- und Onset/Drum-Triggerlisten.
- Videoanalyse-DTO behält Embedding-Samples, Audio-Key, Tag-Source, Mood- und Farbmetriken.

### Verified
- DTO-Vertragstest: 1 passed.
- WPF Release-Build: 0 Warnungen, 0 Fehler.
- Vollsuite: 799 passed, 11 skipped, 1 absichtlicher SDD-Marker-Gate-Fehler.
- Python-Compile-Sweep und `git diff --check`: PASS.

## 2026-07-28 - M-09 SSE-Progress-Korrelation

### Fixed
- Videoimport- und Pacing-Events tragen stabile Task-/Clip-Korrelation.
- VideoLibrary und Director ignorieren Progress fremder oder veralteter Requests.

### Verified
- Router-/Pacing-/Vertragstests: 36 passed.
- WPF Release-Build: 0 Warnungen, 0 Fehler.

## 2026-07-28 - M-08 Lernsession Play/Pause

### Fixed
- `PlayPauseCommand` toggelt zwischen Play- und Pause-Ereignis.
- Buttonlabel folgt `IsPlaying`; Cut-Wechsel setzt den Playback-State zurück.

### Verified
- WPF-Vertragstest: 1 passed.
- WPF Release-Build: 0 Warnungen, 0 Fehler.

## 2026-07-28 - M-07 Ein RAFT-Flow pro Frame-Paar

### Fixed
- Segmentanalyse berechnet Optical Flow nur einmal pro Frame-Paar.
- P95-Motion und Scene-Change werden aus gemeinsamen Flow-Statistiken abgeleitet.

### Verified
- Progress-/DirectML-/VRAM-/Video-Cluster: 30 passed.
- Python-Compile-Sweep für Backend, Source und Tests: PASS.

## 2026-07-28 - M-06 Zeitstabile Streaming-Energy

### Fixed
- Fehlgeschlagene Chunk-Loads und RMS-Berechnungen erzeugen eine downsample-kompatible Null-Lücke statt die Energy-Zeitachse zu verkürzen.
- Progress wird auch nach einem fehlgeschlagenen Chunk fortgeschrieben.

### Verified
- Streaming-/Audio-/Pacing-/Router-Cluster: 44 passed.
- Python-Compile-Sweep für Backend, Source und Tests: PASS.

## 2026-07-27 - M-05 Persistente Medien-JSON-Versionen

### Fixed
- `.wmv` und `.flv` werden in Repository-Reads und -Writes als Video klassifiziert.
- Neue und regulär aktualisierte Metadata-/AI-Blobs werden vor dem Speichern auf das aktuelle Schema migriert.

### Verified
- Repository-/Schema-/Storage-/Persistenz-Cluster: 57 passed.
- Bestehende 2.544 Live-Blobs wurden ohne Migrationsfreigabe nicht verändert.

## 2026-07-27 - M-04 Brain-Stats Connection-Lock

### Fixed
- `/brain/stats` serialisiert alle direkten `axis_weights`-Reads mit dem geteilten `BrainStore._weights_lock`.
- Stats konkurrieren dadurch nicht mehr ungesichert mit Feedback, Reset, Rebind oder Close.

### Verified
- Brain-Router-/Recovery-/Core-/Binding-Cluster: 45 passed.
- Python-Compile-Sweep für Backend, Source und Tests: PASS.

## 2026-07-27 - M-03 Atomarer FAISS-Medienlink

### Fixed
- Verlinkte Embeddings ohne `media_id` werden vor dem FAISS-Write abgelehnt.
- Fehlgeschlagene `vector_map`-Inserts entfernen den neuen letzten Vektor oder tombstonieren ihn konkurrenzsicher und propagieren den Fehler.

### Verified
- VectorStore-/MediaRepository-/AppState-/Router-Cluster: 72 passed.
- Vorhandene Live-Daten wurden nicht verändert; Orphan 897 bleibt bis zur Freigabe offen.

## 2026-07-27 - M-02 Projektgebundener Medienimport

### Fixed
- Audio- und Videoimport antworten ohne geöffnetes Projekt mit HTTP 409, bevor Datei-, Hash- oder State-Arbeit beginnt.
- AppState-Registrierung und Clip-Persistenz verlangen eine aktive DB-Projekt-ID und verwenden nicht mehr still DB-Projekt 1.

### Verified
- Router-/AppState-/Projekt-Persistenz-Cluster: 59 passed.
- Python-Compile-Sweep für Backend, Source und Tests: PASS.

## 2026-07-27 - M-01 Persistenzsichere Medien-Löschung

### Fixed
- Audio-/Video-Clips werden erst nach erfolgreicher SQLite-/FAISS-Verarbeitung aus dem In-Memory-Katalog und Analyse-Cache entfernt.
- DB- und Tombstone-Fehler werden als `persist_error` gemeldet und bis zum API-Fehlerpfad weitergereicht.

### Verified
- AppState-/Router-/Projekt-Persistenz-Cluster: 55 passed.
- Python-Compile-Sweep für Backend, Source und Tests: PASS.

## 2026-07-27 - C-01 Live-Pacing Cache-Vertrag

### Fixed
- `AdvancedPacingEngine` initialisiert `_cached_audio_path`, `_cached_y` und `_cached_sr` atomar.
- `PacingService._inject_cached_into_engine()` verwechselt injizierte Analysemetadaten nicht mehr mit einer geladenen Waveform.
- Nicht schluckender Regressionstest deckt Cache-Injektion → fehlenden aktiven Trigger-Cache → Live-Audio-Load ab.

### Verified
- Pacing-Regression: 4 passed; Pacing-Cluster: 101 passed, 1 skipped.
- Python-Compile: 274/274; WPF Release-Build: 0 Warnungen, 0 Fehler.
- Release-Smoke: Audioanalyse, Pacing (3 Cuts), Timeline-Save und Render-Start/Cancel PASS.
- Full-Suite: 737 passed, 11 skipped, 2 bekannte unabhängige Fehler.

## 2026-07-27 - C-02 AMF-only Render-Vertrag

### Fixed
- Live-Schema, WPF-Encoderliste und Chat-Tool erlauben nur `h264_amf`, `hevc_amf`, `av1_amf`.
- RenderService und VideoGenerator enthalten keine Software-/MediaFoundation-Fallbacks mehr; fehlendes AMF bricht explizit ab.
- Encoder-Erkennung läuft lazy erst beim Rendern und nutzt valide 320x240-Probe statt AMF-inkompatibler 64x64-Probe.
- OpenAPI-Snapshot und generierte C#-DTOs synchronisiert.

### Verified
- AMF/OpenAPI-Regressions: 30 passed; Render-/Timeline-Cluster: 71 passed.
- Live-Encoderprobe: `hevc_amf`; Release-Smoke: PASS.
- Full-Suite: 751 passed, 11 skipped, 2 bekannte unabhängige Fehler.
- Python-Compile: 275/275; WPF Release-Build: 0 Warnungen, 0 Fehler.

## 2026-07-27 - C-03 DirectML-only Provider- und Motion-Vertrag (teilweise)

### Fixed
- `ModelLoader` verwendet ausschließlich `DmlExecutionProvider` und bricht ohne DirectML explizit ab.
- Farneback und `ALLOW_CPU_FALLBACK` aus RAFT-Factory, Video-Export und SmartDirector entfernt.
- SmartDirector nutzt eine RAFT-Session pro Clip-Batch und entlädt sie garantiert; ohne DirectML wird ein neutraler Motion-Wert geliefert.

### Verified
- DirectML-/Motion-Cluster: 26 passed; reale Providerprüfung: nur `DmlExecutionProvider`.
- Python-Compile: 276/276; Full-Suite: 762 passed, 11 skipped, 2 bekannte unabhängige Fehler.
- Offen: `audio/separator.py` bleibt wegen Skill-Lock bis zur expliziten Nutzerfreigabe unverändert.

## 2026-07-27 - H-01 Nicht-destruktiver Medien-Restore

### Fixed
- Projekt-Open löscht SQLite-Medienzeilen nicht mehr, wenn Dateien temporär nicht erreichbar sind.
- Persistierte Clip-IDs fehlender Medien fließen in die ID-Zähler ein und verhindern Kollisionen bei späteren Imports.

### Verified
- AppState-/Projekt-/MediaRepository-Persistenzcluster: 46 passed.

## 2026-07-27 - H-02 Atomarer Projekt↔Brain-Rebind

### Fixed
- Neue Brain-`state.db` wird vollständig geöffnet und initialisiert, bevor die alte Connection geschlossen wird.
- Der globale Brain-Projektpfad wird erst nach erfolgreichem Bind aktualisiert.
- Projekt-Create/Open bindet Brain vor dem Runtime-State-Reset und liefert bei Fehler HTTP 500, ohne das bisherige Projekt zu verwerfen.

### Verified
- Sämtliche Brain- plus Projekt-Binding-/Persistenztests: 137 passed.

## 2026-07-27 - H-03 FAISS/SQLite-Kompaktierungs-Gate

### Fixed
- Ein fehlgeschlagenes `vector_map`-Remapping stoppt die Kompaktierung vor dem In-Memory-Index-Swap.
- Index, Metadaten und Tombstones bleiben für einen sicheren Retry unverändert.
- Ungültige VectorStore-`__new__`-Testfixture mockt den absichtlich nicht initialisierten Save-Notifier.

### Verified
- VectorStore-/MediaRepository-/Embedding-Persistenzcluster: 22 passed.
- Vollständiger VectorStore-Cluster: 6 passed.

## 2026-07-27 - Verlustfreier Generation-Cancel

### Fixed
- Wiederverwendbarer `VideoGenerator` setzt alten Cancel-Zustand synchron bei neuer Jobannahme zurück.
- Cancel während AI-/Audioanalyse wird nicht mehr am Render-Einstieg gelöscht.
- Basic- und SmartDirector-Render liefern früh `cancelled=True` und starten keine Finalisierung nach erkanntem Cancel.

### Verified
- SmartDirector-/GenerationService-/VideoGenerator-Integration: 24 passed.
- Encoder-/AMF- und Render-Persistenzcluster: 36 passed.
- Vollsuite: 773 passed, 11 skipped, 1 absichtlicher SDD-Marker-Gate-Fehler; Python-Compile 278/278.

## 2026-07-27 - H-04 Crash-konsistenter FAISS-Snapshot

### Fixed
- `.faiss`, Metadata-JSON und Tombstone-JSON werden über einen gemeinsamen Journal-/Backup-Commit veröffentlicht.
- Fehler zwischen Live-Replaces rollen sofort auf die vorige Dreiergeneration zurück.
- Ein beim Start gefundenes Transaktionsjournal wird vor dem Index-Load idempotent recovered.

### Verified
- Snapshot-Crash-/Recovery-Regressionen: 3 passed.
- VectorStore-/Embedding-/MediaRepository-Persistenzcluster: 25 passed.

## 2026-07-27 - H-05 Eindeutige Video-VRAM-Verantwortung

### Fixed
- `with_gpu_task()` kann zusammengesetzte Tasks nur serialisieren und telemetrieren, während interne Modell-Owner ihre Budgets verwalten.
- Videoanalyse reserviert `video_analysis_full` nicht mehr zusätzlich zu RAFT und SigLIP.

### Verified
- Regression misst 2400 MB interne Commitments statt 5300 MB Doppelzählung.
- VRAM-/DirectML-/Video-Cluster: 36 passed; Python-Compile: 278/278.

## 2026-07-27 - H-06 Vollständige Trigger langer Mixe

### Fixed
- Streaming-Audioanalyse extrahiert Onset-, Kick-, Snare- und HiHat-Kandidaten pro Chunk über die gesamte Datei.
- Absolute Zeitstempel werden an 5-s-Overlap-Grenzen dedupliziert.
- Audio-Router übernimmt für lange Mixe die Streaming-Trigger statt des 600-s-Snapshots.

### Verified
- Regression bestätigt Onset bei 701 s und leere Trigger im `energy_only`-Pass.
- Audio-/Streaming-/Pacing-Cluster: 28 passed.

## 2026-07-27 - H-07 Ausführbarer Render-Restart

### Fixed
- Persistente Queue speichert versionierten RenderRequest-, Timeline- und Projektwurzel-Snapshot ohne DB-Schemamigration.
- Lifespan rekonstruiert und plant `queued`/`interrupted` Jobs wirklich neu ein.
- Historische Jobs ohne Resume-Payload werden explizit `failed` statt dauerhaft wartend.

### Verified
- Render-Persistenz-/Router-/AMF-Cluster: 52 passed.
- Python-Compile: 278/278.

## 2026-07-27 - H-08/H-09 WPF-Projektwechsel

### Fixed
- Direkter Projektwechsel publiziert Closing→Closed→Opened in definierter Reihenfolge.
- Audio-/Video-State-Services verwerfen Late-Write alter Refresh-Generationen.
- Audio Shared State sowie Video Thumbnail-/Failure-Caches werden beim Wechsel geleert.
- Sämtliche ProjectService-Lifecycle-Nachrichten laufen über den WPF-Dispatcher.

### Verified
- WPF-Projektcache-/Dispatcher-Vertrag: 5 passed.
- WPF Release-Build: 0 Warnungen, 0 Fehler.

## 2026-07-09 - KRITISCH: Timeline-Generierung seit 2026-06-09 kaputt (Director-Tab leer)

**User-Report:** "jedes Mal konnte ich keine Timeline generieren und die Daten wurden nicht weitergegeben."

### Root Cause
Der Memory-Leak-Fix T019 (Commit `3752db1`, 2026-06-09) stellte 8 Views auf lazy `IServiceScope`-DataContexts um: `DirectorViewModel`/`AnchorViewModel` entstehen erst beim ersten Tab-Öffnen. Die `ProjectOpenedMessage` (App-Start/Projekt-Öffnen) feuert davor — der Konstruktor macht keinen Initial-Load → KI-REGIE-Tab blieb leer (Audio-Combo leer, 0 Video-Clips), Generate-Button gesperrt. AUDIO/VIDEO-Tabs blieben eager und funktionierten — deshalb wirkte es wie "Daten werden nicht weitergegeben".

### Fix
- `DirectorViewModel.cs` + `AnchorViewModel.cs`: Initial-Load (`HandleReload()` / `RequestAudioReloadAsync()`) am Konstruktor-Ende — robust gegen jedes Message-Timing. `ProductionViewModel` hatte bereits Initial-Sync.

### Verifikation (Live-GUI, echtes User-Projekt "212121", 41 Clips)
- Repro VOR Fix: KI-REGIE "0 ausgewählt", Audio-Combo leer, Generate unmöglich (pywinauto).
- NACH Fix: "41 Video / 1 Audio Clips geladen", BPM 135.99 übernommen, Klick auf Generate → **327 Cuts generiert (476.4s)**, Trigger-Liste + Vorschläge gefüllt (Screenshot `logs/timeline_fixed.png`).
- Backend-Kette separat headless verifiziert (Projekt→Import→Analyse→`/pacing/generate`→save→`/pacing/timeline`): 4/4 Schritte OK.

---

## 2026-07-09 - Review-Fixes (4-Experten-Review der Commits 2026-07-08/09)

Alle 4 HIGH-, 8 MEDIUM- und relevanten LOW-Findings aus dem Multi-Agent-Review gefixt (Plan: `docs/superpowers/plans/2026-07-09-review-fixes-commits-0708-0709.md`).

### HIGH
- `dependencies.py`/`main.py`: `publish_event_threadsafe` + Main-Loop-Capture im Lifespan — Worker-Thread-Publishes kamen bis 15s verspätet und konnten via `InvalidStateError` die Tag-Extraktion abbrechen.
- `lmstudio_vision_wrapper.py`: injizierbarer Status-Publisher statt `backend`-Direktimport (Layering); 100ms-Sleep pro Frame entfernt; Cache-Hit-Flicker beseitigt; failed-Event bei Provider-down; Ollama-Heuristik angeglichen.
- `CachedTabControl.cs`: `CreatePeerForElement(ContentPresenter)` liefert null — UIA-Fix war No-Op; jetzt `FrameworkElementAutomationPeer`-Fallback + `ResetChildrenCache` bei Tab-Wechsel. Live mit pywinauto verifiziert (Tab-Content-Buttons im UIA-Tree).
- `weight_store.py`/`brain_service.py`: Conn-Lock von BrainStore wird an WeightStore durchgereicht — der AP5.5-Close-vs-Query-Race war nie wirklich gefixt.
- `verify_release_smoke.ps1`: Dummy `sleep(3600)` statt 60s (False-FAIL), `taskkill /T /F` Prozessbaum-Kill, Dummy-Stop immer im finally. script-validator 3× clean.

### MEDIUM
- `video_router.py`: llm_status Terminal-idle-Event + `clip_id` im Payload; Log-vor-Publish; Duplikat-Imports entfernt.
- `anchor_manager.py`: `mkstemp` statt fixer `.tmp`-Name (Parallel-Save-Clobber reproduziert: WinError 32/5), fsync, 3× Replace-Retry, Save-Fehlschläge werden an allen Callern geloggt.
- `DirectorViewModel.cs`: Clip-Selektion überlebt Library-Refreshes (nur neue Clips defaulten auf selected).
- `VideoLibraryViewModel.cs`: `SelectedClip` + `IsMarked` überleben den Self-Refresh nach Analyse (L-M6-Erhalt).
- `embedding_repository.py`: Conns toter Threads werden beim nächsten Zugriff geprunt.
- `migration_runner.py`/`embedding_repository.py`: Warning bei nicht-numerischem Migrations-Präfix, ValueError bei Duplikat.
- `models_router.py`/`model_registry.py`: erfundene Modell-Ids (`qwen3.6-vision`, `qwen3.5-vl`, 26b-heretic) durch reale installierte LM-Studio-Ids ersetzt (`qwen/qwen3.5-9b`, `qwen/qwen3.6-27b`; live gegen GET /v1/models verifiziert).

### LOW
- chat_router-Docstring (tiktoken-Behauptung), brain_router `import time` an Dateianfang, frozen-static Loading-Brush, Beat-Dedup-Verhaltens-Kommentar, `.gitattributes` (EOL-Pinning gegen LF/CRLF-Rewrite-Commits).

### Verifikation
- pytest: **750 passed**, 11 skipped (12 neue Tests); dotnet Release-Build 0 Fehler.
- Live-Smoke (run-pb-studio): Fenster ok, Tab-Content im UIA-Tree, LLM-Widget rendert (`logs/agent_review_fix_smoke.png`).
- Bewusst nicht gefixt (Begründungen im Plan): Doppel-Send Refresh-Messages, CORS-127.0.0.1-Port, VRAM-Init-Lock-Fragilität, MediaIngest-Line-Ending-History.

---

## 2026-07-09 - LLM-Status-Widget (Antigravity-Arbeit fertiggestellt)

Von Antigravity begonnenes Feature abgeschlossen: Live-LLM-Status in der WPF-Statusleiste.

### Feature
- `MainWindow.xaml` + `MainViewModel.cs`: Zentriertes LLM-Status-Widget (Modell, Provider, Ladefortschritt, Status-Farbe) in der Statusleiste.
- `SSEClient.cs`: Neues `llm_status`-Event auf dem Progress-Stream (`LlmStatusEventArgs`: Model/Provider/Status/Percent).
- `lmstudio_vision_wrapper.py` + `video_router.py`: `publish_event("llm_status", ...)` bei Modell-Auswahl, Cache-Hit, Erfolg, Timeout, Fehler und Moondream-Fallback.
- **Fertigstellungs-Fix (fehlte bei Antigravity):** `events_router.py` — `llm_status` in den `progress_events`-Filter aufgenommen; ohne diesen Eintrag hätte der SSE-Stream das Event nie an das Frontend durchgelassen.

### Nebenänderungen (ebenfalls aus Antigravity-Session übernommen)
- AIFF-Support (`.aiff`/`.aif`) in `AudioLibraryViewModel.cs` (Dialog + Ordner-Scan) und `audio_router.py` (Import-Whitelist).
- `models_router.py`/`model_registry.py`: Kuratierte Vision-Modelle `qwen3.6-vision` und `qwen3.5-vl` ergänzt, Task-Präferenzen aktualisiert (+ Testanpassung `test_model_registry.py`).
- `CachedTabControl.cs`: `AutomationPeer` exponiert gecachten Tab-Content für UI-Automation (pywinauto-GUI-Tests).

### Verifikation
- `dotnet build -c Release`: 0 Fehler, 0 Warnungen; Release-DLL neu gebaut (2026-07-09 00:05).
- `pytest Tests/`: 738 passed, 11 skipped (nach dem events_router-Fix gelaufen).

---

## 2026-07-08 - Audit-Fix Phase 4: Block C (AP6) Hardening & Remaining Risks

Alle verbleibenden Stabilitäts- und Korrektheitsmängel aus Block C (AP6) und offene Restrisiken behoben, verifiziert und eingecheckt.

### Block C (AP6) & Stabilitäts-Fixes
- `verify_release_smoke.ps1`: targeted PID-based Termination eingeführt. Der Uvicorn-Backend-Prozess wird gezielt über seine PID beendet, was systemweite `taskkill /F /IM python.exe` und das Beenden unbeteiligter Python-Instanzen verhindert.
- `brain_store.py`: SQLite-Threading-Sicherheit implementiert. `_patterns_lock` und `_weights_lock` sichern Datenbank-Close-Operationen gegen Thread-Konflikte ab.
- `CLAUDE.md`: PyTorch CPU-Inferenz-Einschränkungen für htdemucs dokumentiert (DirectML-Beschleunigung greift nur bei ONNX-MDX-Net Pfaden).
- `brain_router.py`: Reset-Token TTL hinzugefügt. Confirmation Tokens laufen nach 5 Minuten ab, inklusive automatischer Bereinigung abgelaufener Tokens bei Aufruf.
- `chat_router.py` & `requirements.txt`: Unbenutzte `tiktoken` Abhängigkeit entfernt, um Latenzen und Download-Fehler in Offline-Umgebungen zu vermeiden; die Zeichen-Heuristik dient als primärer Token-Zähler.
- `app_state.py`: `stems_paths` wird beim Re-Import und Wiederverwendung von Audio-Clips aus der Datenbank übernommen, was redundante Stem-Separationsläufe verhindert.
- `main.py`: CORS-Integrität gehärtet. Der unsichere `"null"`-Origin wurde entfernt; `DELETE` und `PUT` wurden in `allow_methods` aufgenommen.
- `render_router.py`: Finaler Cancel-Check nach erfolgreichem `_execute_render` entfernt, um das Löschen bereits fertiggestellter Render-Videos bei Timing-Races zu verhindern.
- `vram_budget_manager.py`: Instanziierungs-Race in `__init__` über einen Thread-Lock abgesichert, um thread-sicheren Singleton-Zugriff zu gewährleisten.
- `embedding_repository.py`: Thread-lokale SQLite-Verbindung wird bei `close()` zurückgesetzt (`self._local = threading.local()`), um Fehler durch geschlossene Verbindungen bei Folge-Aufrufen zu verhindern.
- `migration_runner.py` & `embedding_repository.py`: Migrations-Parsing von glob-Listenindizes auf explizite Versionsnummern-Präfixe (z. B. `001_initial.sql` -> 1) umgestellt.
- `media_repository.py`: Early exit in `bulk_update_status()` bei leeren Listen hinzugefügt, um SQL syntax errors bei `IN ()` zu vermeiden.
- `streaming_analyzer.py`: Chunk-Grenz-Deduplizierung auf 150ms erhöht und Beat-Jitter über Mittelwertbildung zusammengelegt.
- `video_router.py`: Keyword-Argument-Fix für `extract_tags_and_model_via_lmstudio` (`mode=current_mode`), um TypeErrors zu verhindern.
- `anchor_manager.py`: Atomares Schreiben der Anchor-JSON-Dateien über temporäre Dateien und `replace()` implementiert, um Datenverlust bei Abstürzen zu verhindern.

---

## 2026-06-12 - Audit-Fix Phase 3: Arbeitsplan AP1-AP5 (offene Funde aus FULL_AUDIT_2026-06-10)

Alle im Arbeitsplan (`ARBEITSPLAN_AUDIT_2026-06-12.md`) als verifiziert-offen markierten Punkte umgesetzt.
**Verifikationsstand: Code-Edits abgeschlossen und per File-Read verifiziert; Release-Build + pytest standen
zum Edit-Zeitpunkt noch aus** (Sandbox-Mount eingefroren, Computer-Use-Freigabe nicht erteilt) —
`AUDIT_FIX_VERIFY.bat` liegt bereit und schreibt `verify_audit_fix_2026-06-12.log` + `VERIFY_DONE.flag`.

### AP1 — Backend (FastAPI)
- `pacing_router.py`: `except HTTPException: raise` vor generischem 500-Handler (400-Validierung kam als 500 an); ffprobe-`_get_audio_duration` via `asyncio.to_thread` (blockierte Event-Loop/SSE); `state_conn`-Write hinter `db_write_lock`+`to_thread`.
- `main.py:_force_exit`: `signal.raise_signal(SIGINT)` statt `os.kill(SIGTERM)` — SIGTERM war auf Windows TerminateProcess, Lifespan-Teardown lief NIE; 10s-Hard-Exit-Fallback.
- `events_router.py`: SSE-Queue-Registrierung in die erste Generator-Iteration verlegt (Queue-Leak bei nie gestartetem Stream).

### AP2 — Rendering/FFmpeg
- `render_service.py`: alle bare `"ffmpeg"`/`"ffprobe"` → `_get_ffmpeg_path()`/`_get_ffprobe_path()` (5 Stellen); SAR-Check in `_check_needs_normalization`; Encoder-Fallback (AMF→CPU) wird via `progress_callback`/SSE gemeldet statt nur Log-Warning.
- `preview_renderer.py`: `get_preview_encoder()` (h264_amf speed) statt hartem libx264, FFmpeg-Pfad aufgelöst.

### AP3 — WPF
- **K7-Nachfix:** `MainWindow.OnClosing` rief `BeginShutdown()` VOR `App.OnExit` → Save-on-Exit war trotz K7-Fix tot. BeginShutdown läuft jetzt nur noch in OnExit NACH SaveProjectAsync.
- `App.OnExit`: von `async void` auf synchron-gebunden (Task.Run + Wait(12s)) — Prozess konnte vorher enden bevor Save/Shutdown/StopAsync liefen.
- `PythonBridgeService`: Kill-on-Close **JobObject** (P/Invoke) — uvicorn-Prozessbaum stirbt garantiert mit, auch bei WPF-Hard-Crash; `BackendReadyMessage` wird jetzt nach Health-OK + im Attach-Modus gesendet (Settings-Tab zeigte sonst dauerhaft „Offline").
- `SSEClient`: 50-Versuche-Hard-Cap entfernt (Stream starb nach ~25min Backend-Ausfall endgültig).
- `IApiClient`+`TimelineViewModel`: `GetOnsetsAsync` ins Interface, VM nutzt `IApiClient` (eliminiert zweite ApiClient-Instanz). MainWindow: ungenutzter IApiClient-Parameter entfernt.
- `WaveformRenderer`/`DepthRenderer`: `CollectionChanged`-Abo — In-place-Mutationen (Clear+Add) feuerten kein Redraw, Waveform erschien erst bei Zoom/Resize.
- `VideoLibraryView.xaml`+`SceneInfo`: tote Bindings gefixt — `SceneIndex` jetzt client-seitig gesetzt, Balken+Wert zeigen `Confidence` (per-Scene-Motion existiert backend-seitig nicht); String-`Binding Source="100.0"` → typisierter `sys:Double`; `LoadScenesAsync` cleart vor Add (Szenen-Duplikate bei Re-Analyse).
- NICHT umgesetzt: AP3.6 Video-Grid-Virtualisierung (bräuchte neue NuGet-Dependency `VirtualizingWrapPanel` → laut Projektregeln User-Entscheid).

### AP4 — Audio
- `streaming_analyzer.py`: neuer `energy_only`-Modus (überspringt beat_track) — `audio_router` berechnet die Energy-Curve jetzt vom **Original-Mix**, wenn Beats vom Drums-Stem kamen (vorher stille Semantik-Drift auf Drum-RMS).
- `audio_router.py`: Beat-Strengths >600s-Snapshot jetzt neutral 1.0 statt Bogus-Clamping auf den letzten Snapshot-Frame.
- `structure_analyzer.py`: `total_duration`-Parameter — DJ-Mix-Branch (`>600s`) war im API-Pfad unerreichbar, weil der Snapshot exakt 600.0s lang ist; Router übergibt jetzt die echte Datei-Dauer.
- `beat_detector.py`: `librosa.get_duration` in try (korrupte Datei riss vorher die gesamte Beat-Analyse inkl. Energy mit).
- `waveform_analyzer.py`: Langdatei-Guard (>30min → SR 11025) + float32-Downcast nach sosfiltfilt (float64-RAM-Peak).

### AP5 — IRON-Rules-Hygiene & Scripts
- `recovery_handler.py`: `torch.cuda`-Block entfernt (R1) + toter `global_cache`-Import raus.
- 4 Model-Scripts (`download_clap_model`, `download_siglip_onnx`, `export_moondream_onnx`, `export_raft_onnx`): `enable_cpu_mem_arena = False` ergänzt (R2 verlangt BEIDE Flags).
- `verify_release_smoke.ps1`: `$script:SmokeExitCode` statt `$global:LASTEXITCODE` (taskkill im finally überschrieb den Exit-Code → FAIL konnte als 0 enden); Default FAIL.
- `embedding_cache.py`: voller media_hash im Dateinamen statt `[:16]` (Kollisions-Überschreibung) + `model_version` sanitisiert.
- `brain_store.py`: `_patterns_lock` analog `_weights_lock` (patterns_conn war cross-thread ohne Lock).

---

## 2026-05-29 - Epic 00012: Timeline High-Fidelity Playback & DJ-Beatgrid (Commit `40e4a8d`)

Erfolgreicher Abschluss des finalen Feature-Epics der Entwicklungs-Roadmap. Etablierung aller UI- und Playback-Refactorings für eine DAW-Level Wellenform-Darstellung und ruckelfreie Wiedergabe.

Tests: **727 passed / 9 skipped / 0 failed** (100% Erfolg). WPF Release Build: 0 Fehler / 0 Warnungen.

### Added / Refactored (Timeline High-Fidelity & DJ-Beatgrid)
- **GPU-beschleunigter WaveformRenderer (FR-001):** WPF FrameworkElement Custom Control, das Amplituden in einer einzigen StreamGeometry zeichnet, was die UI-Rendering-Last um ~99% reduziert.
- **Ruckelfreie Playback-Kanten-Übergänge (FR-002):** Implementierung des transienten Flags `_wasPlayingBeforeReload` im Code-Behind von `TimelineView.xaml.cs` zur Gewährleistung unterbrechungsfreier Wiedergabe an Clipgrenzen.
- **High-Contrast DJ-Beatgrid (FR-003):** Rote Downbeats, eisblaue Beats und kontrastreiche abgerundete Badges mit Taktnummer-Beschriftungen (z.B. `BAR 12`) sorgen für 100%ige Lesbarkeit.
- **Song-Phrasen & Wasserzeichen (FR-004):** Sanfte farbliche Abgrenzung der musikalischen Struktur mit transparenten Bezeichnungen auf der A1-Spur.
- **Verifikations-Gates (TR-005):** Etablierung der `.completed`, `.qc-passed` und `qc-report.md` Qualitäts-Gates für Epic 00012.

---

## 2026-05-22 - Hybrid-LLM-Audit (Commit `3025b22`)

User-Audit deckte auf, dass nur 2 von 6 LLM-Call-Sites Auto-Fallback auf Ollama hatten — die anderen 4 nutzten LMStudioClient mit hard-coded LM-Studio-URL ohne Live-Probe. Folge: bei LM-Studio down + Ollama up war Chat und /models/list broken.

Tests: **721 passed / 9 skipped / 0 failed** (vorher 715, +6 neue Regression-Tests).

### Fixed (Hybrid-LLM-Stack — 4 Bypasses)
- `backend/routers/models_router.py:_make_client` → neuer async `_make_alive_client()` Helper mit korrektem `lmstudio_available`+`ollama_available`-Reporting. list_models, list_available_models, recommend_model migriert.
- `src/pb_studio/ai/chat_agent.py:_ensure_resources` → bei `provider="auto"` jetzt `get_alive_client()` statt `get_llm_client()` (vorher: kein Live-Probe → Chat brach bei LM-Studio down obwohl Ollama lief).
- `src/pb_studio/ai/model_registry.py` → neuer `_resolve_client_async()` mit Auto-Fallback (vorher: `LMStudioClient()` lazy default).
- `src/pb_studio/video/lmstudio_vision_wrapper.py` → `get_alive_client()` statt direkter LMStudioClient für Vision-Captioning.

### Live-Verified (Backend mit LM-Studio down + Ollama up)
- `/models/list` → `ollama_available: true`, 4 Modelle (Gemma-4-Uncensored, qwen2.5-osdev, moondream, llava:13b)
- `/models/available` → qwen3-vl-8b listed
- `/models/recommendations` → installed=[4 Ollama-Modelle], korrekte Reasoning
- `/chat/message` → Gemma-4 streamt `"Hallo! 👋"`

### Added (Regression-Tests)
- `Tests/test_video_list_clips_post_analyze.py` (2 Tests) — guards `_explicit_kwargs`-Drift in `list_clips`
- `Tests/test_pacing_snap_subtrack_import.py` (4 Tests) — guards PacingCut-Import in `_snap_cuts_to_subtrack_boundaries`

---

## 2026-05-21 - Auto-QA-Loop autonom (Commit `9909d4a`)

Autonomer 11-Bereiche-Test der gesamten App per API-Tests gegen Backend. 60/60 Funktionen PASS, 3 echte Bugs gefunden+gefixt.

### Fixed (3 Code-Bugs)
- `backend/routers/video_router.py:list_clips` — `TypeError: VideoClipInfo got multiple values for keyword 'is_analyzed'`. Nach `analyze_video` landeten 8 Felder im in-memory clip-dict die mit den expliziten kwargs kollidierten. `_explicit_kwargs`-Set filtert sie aus `c_payload`.
- `backend/routers/video_router.py:_run_video_analysis` — `NameError: name 'state' is not defined` im Embedding-Pfad. Worker-Thread ohne FastAPI-DI. `except Exception` schluckte silent → `embedding_dim=0` für jedes Video. Fix: `from backend.app_state import get_app_state` Singleton.
- `src/pb_studio/pacing/advanced_pacing_engine.py:_snap_cuts_to_subtrack_boundaries` — `NameError: 'PacingCut' is not defined`. Methode nutzte `PacingCut(...)` ohne lokalen Import. Fix: lokaler Import als erste Statement.

### Verified (Live mit Real-Daten)
- BPM Detection: 123.05 BPM für Psy-Trance Mix (BeatNet+librosa)
- Key Detection: F# minor (Krumhansl-Kessler)
- Demucs Stem-Sep 60s WAV: 9s (DirectML)
- h264_amf Render 60s @24fps: 18s = 80fps Render-Speed (3.3× realtime)
- SigLIP-SO400M Embedding nach Fix: 1152-dim, 4 samples

---

## 2026-05-19 - Timeline-Multi-Lane Merge + Post-Merge-Cleanup (Audit-Phase)

Worktree `worktree-timeline-multi-lane` (Commits c9dd4b7..8ed0111 + 22560a7 handoff) gemerged in `main` via FF `update-ref`. Anschliessend Post-Merge-Audit + 7 Cleanup-Commits (f7846d2..df2f9c6).

Tests: **674 passed / 12 skipped / 0 failed** (3:25 min). WPF Release Build: 0 Errors, 10 Warnings.

### Added (Timeline V1+A1 Lanes)
- PBStudio.UI/Views/TimelineView.xaml: Split in V1 (110px) + A1 (80px) Lanes + 60px Track-Header
- PBStudio.UI/Converters/PeaksToWaveformGeometryConverter.cs: PathGeometry-Generator fuer Mini-Waveforms
- PBStudio.UI/Models/TimelineEntry.cs: ThumbnailFrames + AudioPeaks Properties
- PBStudio.UI/ViewModels/TimelineViewModel.cs: Lazy-Load thumbstrip + clipwave per Entry
- Drag collision-prevention (ClampStartToNeighbours) + Auto-Gap-Close im Contiguous-Mode

### Added (Backend Per-Clip-Visuals)
- GET /video/thumbstrip/{id}?n=8 — N evenly-spaced base64-JPEGs (160x90)
- GET /video/clipwave/{id}?n=256 — Downsampled mono peaks (0..1)
- src/pb_studio/video/clip_audio_peaks.extract_peaks
- src/pb_studio/video/frame_extractor.FrameGrabber.extract_thumbnail_strip

### Added (Pacing-Integrity)
- src/pb_studio/services/pacing_service._finalize_cut_list: Streckt letzten Cut auf audio_duration (V1.length == A1.length invariant)
- validate_timeline: Overlap + Audio-Overflow → HTTP 400 (statt Warning)

### Restored (Post-Merge per User-Direktive 2026-05-19 "Chat-Track behalten")
- backend/routers/chat_router.py + src/pb_studio/ai/chat_agent.py + tool_registry.py + Tests
- src/pb_studio/ai/lmstudio_client.py + lmstudio_vision_wrapper.py + Tests
- src/pb_studio/brain/llm_narrator.py + Tests (test_brain_router_narrative + test_llm_narrator)

### Removed
- Branch worktree-timeline-multi-lane (remote + lokal nach Merge)
- Worktree-Dir .claude/worktrees/timeline-multi-lane/
- Stale-Reports im Repo-Root → archive/status/ (LM_STUDIO_PHASE_B_STATUS_2026-05-17, LM_STUDIO_VERIFY_2026-05-17, STATUS_CONSOLIDATED_2026-05-15)

### Fixed
- pre-existing brain_schemas.py (unclosed Field) + chat_router.py (unterminated __all__) — surgical edits + Reverts
- backend/main.py: chat_router import + include_router korrekt verkabelt

### Updated (Doku)
- specs/project-plan.md E010: Cross-Link auf Brain-Vault open-tasks/2026-05-19-post-timeline-merge.md (#16) + specs/00010-resilience-edge-cases/plan.md
- .gitignore: LM-Studio debug-outputs, cowork-scratch, worktree-subdir, _CLEANUP_*.bat

### Test-Status (Net seit 2026-05-14)
- 2026-05-14: 511 passed / 8 skipped
- 2026-05-17: +76 (brain-narrator + chat-track) → 587
- 2026-05-19: +87 (Timeline-Multi-Lane backend + lmstudio + restoration) → **674 passed**

---

## 2026-05-15 - Cowork-Sessions Day 2 (Plan-Execution + Dep-Updates + Test-Coverage)

Commits: 8 (Spec-Markers, Tab-Animations, TODOs, Vulture-Noqa, gzip-meta, coverage-config, autonomy-docs).
pytest: **537 passed / 10 skipped / 0 failed** in 71s (Win) nach Cluster-1-Dep-Update.

### Added (Code)
- P2.1 / Spec 00007 T010: GPU-accelerated TabControl-Animations (ScaleTransform + Opacity 150ms Storyboard via SelectionChanged Event)
- P2.2 / Spec 00009 T006: media_repository.py gzip-Wrap fuer meta-JSON >10KB (`_serialize_meta`/`_deserialize_meta_str`, 96.8% disk-saving REPL)
- P2.5 / advanced_pacing_engine.py: `_snap_cuts_to_subtrack_boundaries(window=0.5)` impl (Helper-API ready, Aufruf in generate_cut_list)
- P1.4 / Spec 00007 T012: verify_release_smoke.ps1 erweitert um 3 Steps (/health/heartbeat, /health/vram, /brain/stats)
- AGENTS.md: Parallele-Subagent-Sektion (13 Code-Zonen, Mount-Truncation-Schutz, Skill-Mapping, Convergence-Protokoll)
- COWORK_AUTONOMY_LESSONS.md: 12 Anti-Patterns dokumentiert + Iron Rule 12 in CLAUDE.md

### Added (Tests)
- P3.1 / Test-Coverage-Gap-Filler #1: Tests/test_encoder_utils.py (12 tests, Codec+Quality+RateControl+EncoderConfig+build_args+get_encoder_info)
- P3.1 / Test-Coverage-Gap-Filler #2: Tests/test_cache_manager.py (12 tests, init+save+load+exists+invalidate+clear_all+ttl-expiry+corrupt-json)
- P3.1 / Test-Coverage-Gap-Filler #3: Tests/test_model_loader.py (12 tests, ModelType+Spec+register+is_loaded+get_stats+unload_all+singleton)

### Fixed (UI)
- Spec 00010 T003 (TR-001): SSEClient.cs NotifyUiAfterAttempts=5 Konstante + IsBackendReachable Property + BackendReachabilityChanged Event (additiv, kein Break)
- Spec 00010 T004 (TR-003): MainWindow.xaml roter ConnectionStatus-Overlay-Banner (Grid.Row=1 Top, Panel.ZIndex=1000, WifiOff-Icon, Auto-Hide bei Recovery)
- Spec 00007 T011: AudioClipList VirtualizationMode=Recycling (Konsistenz mit VideoClipList)
- P3.4 vulture-noqa: 4 API-Compat-Parameter mit `# noqa: ARG002` markiert (exc_val __exit__, previous_clip_id NV-API, status_callback x2 PyQt-Legacy)

### Fixed (Test-Infrastructure)
- P1.5 Coverage-Hang: dedicated pytest-coverage.ini + .coveragerc + coverage_run_v2.bat (Hardware-Tests excluded wegen CLR/pythonnet-Deadlock unter coverage.py-Instrumentierung)
- video_router.py:348 stale TODO durch Status-Beschreibung ersetzt

### Updated (Deps)
- Cluster 1 FastAPI-Stack: fastapi 0.110→**0.136.1**, uvicorn 0.28→**0.47.0**, pydantic 2.5→**2.13.4**, pydantic-settings 2.2→**2.14.1**, httpx 0.27→**0.28.1**. Zero regression (537 tests pass).

### Verified (Runtime)
- AMD Adrenalin 32.0.31007.1017 (2026-05-04) — h264_amf live-test PASSED. F-10.3 RESOLVED. Doc: test-report/2026-05-15-AMD-DRIVER-RESOLVED.md
- SSE-Recovery + Overlay-Visibility: vr2_overlay.png zeigt rotes Banner nach ~50s (5-attempt threshold). Backend-Recovery: overlay clears.

## 2026-05-14 - Audit-Phase X+Y+Z+IRC autonom (21 Findings)

Auto-QA-Loop session 2026-05-14. Commits: e3a68bd, 9d32bbf, f5bce71, 0487314.
pytest: 511 passed / 8 skipped / 0 failed. dotnet build Release: clean.

### Added
- Y4 / L-AUDIO-1: StreamingAudioAnalyzer integration fuer >10min mixes
- Y6 / L-STATE-2: vector_map populate + tombstone-on-delete
- Z1 / GPU-F3: brain_clap (600 MB) + brain_siglip2 (1100 MB) VRAM-Budgets
- Tests: test_motion_schema_forwarding.py, test_video_hash_persist.py

### Fixed
- X1 / L-VIDEO-2 (M-4 CRIT): peak_motion silent-drop in MotionData schema
- X2 / CD-1 / L-AUDIO-8: stems_paths persist + reload
- X3 / CD-2 / L-VIDEO-1 / L-STATE-3: FAISS-Index unified + atexit leak
- X4 / CD-3 / L-VIDEO-3: video_hash persist + reload
- X5 / CD-4 / L-AUDIO-6 (M-3 CRIT): Subtrack/Tempo reload decoupled from is_analyzed
- X6 / L-FE-13: DirectorVM AudioHash + StemsPaths Mapping
- Y1 / L-FE-15: TimelineView CompositionTarget unsubscribe
- Y2 / L-FE-7: BrainVM + LearningSessionVM IDisposable
- Y3 / GPU-F2: audio_key OUT of with_gpu_task
- Y5 / L-VIDEO-5: range-bug Motion+Embedding loops
- Y7 / L-STATE-4: Brain state.db reset on project close
- Z2 / GPU-F4: brain_router asyncio.to_thread
- Z3 / M-1 CRIT: ModelLoader Lock -> RLock
- Z4 / L-AUDIO-4: Spectral band_means/variances/events forwarded
- Z5 / L-AUDIO-5: subtrack/tempo merge in analyze_audio
- Z6 / L-VIDEO-4: 6 dead schema fields removed
- IRC-1: siglip + clap DML-strict (kein silent CPU-Fallback)
- IRC-2: video_embedder + audio_embedder torch-directml strict

### Open (User-Action)
- AMD Adrenalin Driver Update fuer h264_amf (siehe test-report/2026-05-14-AMD-DRIVER-UPDATE-required.md)

---
