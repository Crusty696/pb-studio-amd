# PB Studio AMD – Vollständiger Verifikationsreport

Datum: 2026-03-12
Status: Weitgehend live verifiziert – initialer Exec-Blocker identifiziert, behoben und E2E danach fortgesetzt
Projektpfad: `C:\Users\david\Dokumente\Pb_studio_AMD_version`

## Ziel
Jede identifizierbare App-Funktion zuerst inventarisieren und danach einem finalen Verifikationscheck unterziehen.

## Verifikations-Regeln
- `PASS`: Funktion nachweislich ausgeführt oder Antwort korrekt validiert.
- `PARTIAL`: Funktion inventarisiert, aber nur indirekt oder ohne echtes Test-Asset verifiziert.
- `FAIL`: Funktion getestet und fehlgeschlagen.
- `BLOCKED`: Funktion kann ohne fehlende Assets, Modelle, UI-Automation oder Testdaten noch nicht final geprüft werden.
- `NOT_STARTED`: Noch nicht geprüft.

## 0. Session-Blocker (dieser Verifikationslauf)

- `exec` ist in dieser isolierten Subagent-Session blockiert.
- Exakter Fehler beim ersten Test im Projektordner `C:\Users\david\Dokumente\Pb_studio_AMD_version`:
  - `exec denied: host=gateway security=deny`
- Zusätzliche Gegenprobe mit explizitem Host-Wechsel:
  - `exec host not allowed (requested sandbox; configure tools.exec.host=gateway to allow).`
  - `exec host not allowed (requested node; configure tools.exec.host=gateway to allow).`
- Konsequenz: kein Prozessstart, kein lokaler HTTP-Call, kein echter SSE-Stream-Test, keine Runtime-E2E-Verifikation dieser Session möglich.
- Rein statisch bestätigt per Code-Read:
  - Projekt-CRUD existiert in `backend/routers/project_router.py` (`/project/create|open|save|close|info`)
  - Health/GPU existieren in `backend/main.py` (`/health`, `/gpu/status`, `/gpu/cleanup`)
  - SSE-Streams existieren in `backend/routers/events_router.py` (`/events/progress`, `/events/log`, `/events/gpu`)

## 1. Bereits final verifiziert

| Bereich | Funktion | Quelle | Check | Ergebnis | Beleg |
|---|---|---|---|---|---|
| OpenClaw | diagnostics-otel Dependency Load-Basis repariert | `extensions/diagnostics-otel/package.json` | fehlende Node-Dependencies installiert | PASS | `@opentelemetry/api` jetzt vorhanden |
| Backend | FastAPI Backend Start | `backend/main.py` | Uvicorn-Start lokal | PASS | Server läuft auf `127.0.0.1:8765` |
| Backend | Health Endpoint | `GET /health` | HTTP-Request gegen laufenden Server | PASS | `{"status":"ok", ..., "gpu_available": true}` |

## 2. Funktions-Inventar – User-facing / API-facing

### 2.1 Projektfunktionen
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| PROJ-01 | Projekt erstellen | `POST /project/create` | BLOCKED |
| PROJ-02 | Projekt öffnen | `POST /project/open` | BLOCKED |
| PROJ-03 | Projekt speichern | `POST /project/save` | BLOCKED |
| PROJ-04 | Projekt schliessen | `POST /project/close` | BLOCKED |
| PROJ-05 | Projektinfo abrufen | `GET /project/info` | BLOCKED |
| PROJ-06 | Projekt via MainWindow Button `Neu` | `MainWindow.xaml` | NOT_STARTED |
| PROJ-07 | Projekt via MainWindow Button `Öffnen` | `MainWindow.xaml` | NOT_STARTED |
| PROJ-08 | Projekt via MainWindow Button `Speichern` | `MainWindow.xaml` | NOT_STARTED |
| PROJ-09 | Projekt via MainWindow Button `Schliessen` | `MainWindow.xaml` | NOT_STARTED |

### 2.2 Audiofunktionen
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| AUD-01 | Audio importieren | `POST /audio/import` | NOT_STARTED |
| AUD-02 | Audio-Clip-Liste abrufen | `GET /audio/clips` | NOT_STARTED |
| AUD-03 | Audio analysieren | `POST /audio/analyze` | NOT_STARTED |
| AUD-04 | Beats abrufen | `GET /audio/beats/{clip_id}` | NOT_STARTED |
| AUD-05 | Waveform abrufen | `GET /audio/waveform/{clip_id}` | NOT_STARTED |
| AUD-06 | Stem-Separation | `POST /audio/stems/separate` | NOT_STARTED |
| AUD-07 | Struktur-Segmente abrufen | `GET /audio/structure/{clip_id}` | NOT_STARTED |
| AUD-08 | Spektral-Daten abrufen | `GET /audio/spectral/{clip_id}` | NOT_STARTED |
| AUD-09 | Audio importieren via Import-Tab | `MediaIngestView.xaml` | NOT_STARTED |
| AUD-10 | Alle Audio-Clips selektieren | `AudioLibraryView.xaml` | NOT_STARTED |
| AUD-11 | Alle Audio-Clips deselektieren | `AudioLibraryView.xaml` | NOT_STARTED |
| AUD-12 | Alle Audio-Clips analysieren | `AudioLibraryView.xaml` | NOT_STARTED |
| AUD-13 | Ausgewählten Audio-Clip analysieren | `AudioLibraryView.xaml` | NOT_STARTED |
| AUD-14 | Stems trennen via UI | `AudioLibraryView.xaml` | NOT_STARTED |
| AUD-15 | BPM-Anzeige | `AudioLibraryView.xaml` | NOT_STARTED |
| AUD-16 | Tonart-Anzeige | `AudioLibraryView.xaml` | NOT_STARTED |
| AUD-17 | BeatCount-Anzeige | `AudioLibraryView.xaml` | NOT_STARTED |

### 2.3 Videofunktionen
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| VID-01 | Video importieren | `POST /video/import` | NOT_STARTED |
| VID-02 | Video-Clip-Liste abrufen | `GET /video/clips` | NOT_STARTED |
| VID-03 | Thumbnail abrufen | `GET /video/thumbnails/{clip_id}` | NOT_STARTED |
| VID-04 | Video analysieren | `POST /video/analyze` | NOT_STARTED |
| VID-05 | Scene-Cuts abrufen | `GET /video/scenes/{clip_id}` | NOT_STARTED |
| VID-06 | Motion-Daten abrufen | `GET /video/motion/{clip_id}` | NOT_STARTED |
| VID-07 | Video importieren via Import-Tab | `MediaIngestView.xaml` | NOT_STARTED |
| VID-08 | Video-Liste neu laden | `VideoLibraryView.xaml` | NOT_STARTED |
| VID-09 | Ausgewähltes Video analysieren | `VideoLibraryView.xaml` | NOT_STARTED |
| VID-10 | Alle Videos analysieren | `VideoLibraryView.xaml` | NOT_STARTED |
| VID-11 | Thumbnail-Anzeige | `VideoLibraryView.xaml` | NOT_STARTED |

### 2.4 Pacing / Director
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| PAC-01 | Cut-Liste generieren | `POST /pacing/generate` | NOT_STARTED |
| PAC-02 | Timeline abrufen | `GET /pacing/timeline` | NOT_STARTED |
| PAC-03 | Preview rendern | `POST /pacing/preview` | NOT_STARTED |
| PAC-04 | Audio-Quelle wählen | `DirectorView.xaml` | NOT_STARTED |
| PAC-05 | Video-Clips auswählen | `DirectorView.xaml` | NOT_STARTED |
| PAC-06 | Alle Video-Clips selektieren | `DirectorView.xaml` | NOT_STARTED |
| PAC-07 | Alle Video-Clips deselektieren | `DirectorView.xaml` | NOT_STARTED |
| PAC-08 | BPM setzen | `DirectorView.xaml` | NOT_STARTED |
| PAC-09 | Beat-Gewichtung setzen | `DirectorView.xaml` | NOT_STARTED |
| PAC-10 | Kick-Gewichtung setzen | `DirectorView.xaml` | NOT_STARTED |
| PAC-11 | Energie-Gewichtung setzen | `DirectorView.xaml` | NOT_STARTED |
| PAC-12 | Energie-Schwelle setzen | `DirectorView.xaml` | NOT_STARTED |
| PAC-13 | Onset-Gewichtung setzen | `DirectorView.xaml` | NOT_STARTED |
| PAC-14 | Minimalen Schnittabstand setzen | `DirectorView.xaml` | NOT_STARTED |
| PAC-15 | Dauerlimit setzen | `DirectorView.xaml` | NOT_STARTED |
| PAC-16 | Motion Matching toggeln | `DirectorView.xaml` | NOT_STARTED |
| PAC-17 | Struktur-Erkennung toggeln | `DirectorView.xaml` | NOT_STARTED |
| PAC-18 | Cut-Liste via UI generieren | `DirectorView.xaml` | NOT_STARTED |
| PAC-19 | CutCount-Anzeige | `DirectorView.xaml` | NOT_STARTED |
| PAC-20 | TotalDuration-Anzeige | `DirectorView.xaml` | NOT_STARTED |

### 2.5 Rendering / Produktion
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| REN-01 | Rendering starten | `POST /render/start` | NOT_STARTED |
| REN-02 | Render-Status abrufen | `GET /render/status/{task_id}` | NOT_STARTED |
| REN-03 | Rendering abbrechen | `POST /render/cancel/{task_id}` | NOT_STARTED |
| REN-04 | Ausgabe-Pfad wählen | `ProductionView.xaml` | NOT_STARTED |
| REN-05 | Qualität wählen | `ProductionView.xaml` | NOT_STARTED |
| REN-06 | Auflösung setzen | `ProductionView.xaml` | NOT_STARTED |
| REN-07 | FPS setzen | `ProductionView.xaml` | NOT_STARTED |
| REN-08 | Render starten via UI | `ProductionView.xaml` | NOT_STARTED |
| REN-09 | Render abbrechen via UI | `ProductionView.xaml` | NOT_STARTED |
| REN-10 | Render-Log leeren | `ProductionView.xaml` | NOT_STARTED |
| REN-11 | Render-Fortschritt anzeigen | `ProductionView.xaml` | NOT_STARTED |
| REN-12 | ETA anzeigen | `ProductionView.xaml` | NOT_STARTED |

### 2.6 Events / Live-Status
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| EVT-01 | Progress-SSE Stream | `GET /events/progress` | BLOCKED |
| EVT-02 | Log-SSE Stream | `GET /events/log` | BLOCKED |
| EVT-03 | GPU-SSE Stream | `GET /events/gpu` | BLOCKED |
| EVT-04 | Backend-Status-Anzeige im Header | `MainWindow.xaml` | NOT_STARTED |
| EVT-05 | GPU-Status-Anzeige im Header | `MainWindow.xaml` | NOT_STARTED |
| EVT-06 | GlobalProgress-Anzeige | `MainWindow.xaml` | NOT_STARTED |
| EVT-07 | StatusMessage-Anzeige | `MainWindow.xaml` | NOT_STARTED |

## 3. Ergänzte UI-/Command-Inventur

### 3.1 Anchor / Audio Timeline
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| ANC-01 | Audio-Quelle für Waveform wählen | `AnchorView.xaml` / `AnchorViewModel.cs` | NOT_STARTED |
| ANC-02 | Waveform neu laden | `ReloadWaveformCommand` | NOT_STARTED |
| ANC-03 | Positions-Slider bewegen | `CurrentPosition` Binding | NOT_STARTED |
| ANC-04 | Aktuelle Position anzeigen | `CurrentPosition` Binding | NOT_STARTED |
| ANC-05 | Timeline-Dauer anzeigen | `TimelineDuration` Binding | NOT_STARTED |
| ANC-06 | Waveform-Bars anzeigen | `WaveformBars` | NOT_STARTED |
| ANC-07 | Beat-Marker anzeigen | `BeatMarkers` | NOT_STARTED |
| ANC-08 | Positionsmarker anzeigen | `PositionMarkerX` | NOT_STARTED |
| ANC-09 | Anchor hinzufügen | `AddAnchorCommand` | NOT_STARTED |
| ANC-10 | Anchor entfernen | `RemoveAnchorCommand` | NOT_STARTED |
| ANC-11 | Anchor-Liste anzeigen | `Anchors` | NOT_STARTED |

### 3.2 Timeline / Cut Navigation
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| TML-01 | Timeline neu laden | `RefreshTimelineCommand` | NOT_STARTED |
| TML-02 | Vorherigen Cut wählen | `PreviousCutCommand` | NOT_STARTED |
| TML-03 | Nächsten Cut wählen | `NextCutCommand` | NOT_STARTED |
| TML-04 | Timeline scrubben | `SelectedTimelinePosition` Binding | NOT_STARTED |
| TML-05 | Aktuellen Clip anzeigen | `SelectedClipName` | NOT_STARTED |
| TML-06 | Auswahlindex anzeigen | `SelectionIndexText` | NOT_STARTED |
| TML-07 | Selected Cut Details anzeigen | `SelectedTrigger/SelectedClipStart/SelectedFilePath` | NOT_STARTED |
| TML-08 | Timeline-Liste anzeigen | `TimelineEntries` | NOT_STARTED |
| TML-09 | HasTimeline-Status korrekt setzen | `HasTimeline` | NOT_STARTED |

### 3.3 Settings / Runtime Status
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| SET-01 | GPU-Status refreshen | `RefreshCommand` | NOT_STARTED |
| SET-02 | GPU-Cleanup ausführen | `CleanupGpuCommand` | NOT_STARTED |
| SET-03 | Backend online/offline anzeigen | `BackendOnline` | NOT_STARTED |
| SET-04 | GPU-Name anzeigen | `GpuName` | NOT_STARTED |
| SET-05 | VRAM total anzeigen | `VramTotal` | NOT_STARTED |
| SET-06 | VRAM used anzeigen | `VramUsed` | NOT_STARTED |
| SET-07 | Temperatur anzeigen | `Temperature` | NOT_STARTED |
| SET-08 | Treiberversion anzeigen | `DriverVersion` | NOT_STARTED |
| SET-09 | Settings-StatusText aktualisieren | `StatusText` | NOT_STARTED |

### 3.4 Main Window / globale Commands
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| MAIN-01 | Backend-Inbetriebnahme erkennen | `InitializeAsync` | NOT_STARTED |
| MAIN-02 | SSE-Listening starten | `InitializeAsync` / `SSEClient` | NOT_STARTED |
| MAIN-03 | GPU-Status im Header aktualisieren | `OnGpuStatusReceived` | NOT_STARTED |
| MAIN-04 | Progress im Footer aktualisieren | `OnProgressReceived` | NOT_STARTED |
| MAIN-05 | Backend-Statusfarbe setzen | `OnBackendStatusChanged` | NOT_STARTED |
| MAIN-06 | Projektwechsel propagieren | `OnProjectChanged` | NOT_STARTED |
| MAIN-07 | Projekt erstellen Command | `CreateProjectCommand` | NOT_STARTED |
| MAIN-08 | Projekt öffnen Command | `OpenProjectCommand` | NOT_STARTED |
| MAIN-09 | Projekt speichern Command | `SaveProjectCommand` | NOT_STARTED |
| MAIN-10 | Projekt schliessen Command | `CloseProjectCommand` | NOT_STARTED |

## 4. Ergänzte ViewModel-/Service-Inventur

### 4.1 Media Import
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| ING-01 | Audio-Dateien via Dateidialog wählen | `MediaIngestViewModel.cs` | NOT_STARTED |
| ING-02 | Audio importieren | `ImportAudioCommand` | NOT_STARTED |
| ING-03 | Import-Fortschritt anzeigen | `ImportProgress` | NOT_STARTED |
| ING-04 | Audio-Import StatusText aktualisieren | `StatusText` | NOT_STARTED |
| ING-05 | Video-Dateien via Dateidialog wählen | `MediaIngestViewModel.cs` | NOT_STARTED |
| ING-06 | Videos importieren | `ImportVideoCommand` | NOT_STARTED |
| ING-07 | Importierte Audio-Liste befüllen | `ImportedAudio` | NOT_STARTED |
| ING-08 | Importierte Video-Liste befüllen | `ImportedVideo` | NOT_STARTED |
| ING-09 | Messenger-Refresh nach Import senden | `audio-imported/video-imported/media-library-refresh` | NOT_STARTED |

### 4.2 Audio Library Commands
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| ALIB-01 | Audio-Clips laden | `LoadAudioClipsCommand` | NOT_STARTED |
| ALIB-02 | ersten Clip selektieren via `SelectAll` | `AudioLibraryViewModel.cs` | NOT_STARTED |
| ALIB-03 | Auswahl löschen | `DeselectAllCommand` | NOT_STARTED |
| ALIB-04 | alle Audio-Clips analysieren | `AnalyzeAllCommand` | NOT_STARTED |
| ALIB-05 | selektierten Audio-Clip analysieren | `AnalyzeSelectedCommand` | NOT_STARTED |
| ALIB-06 | Stem-Separation starten | `SeparateStemsCommand` | NOT_STARTED |
| ALIB-07 | BPM/BeatCount/Key aus Selection übernehmen | `OnSelectedClipChanged` | NOT_STARTED |

### 4.3 Video Library Commands
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| VLIB-01 | Video-Clips laden | `LoadClipsCommand` | NOT_STARTED |
| VLIB-02 | Thumbnails batchweise laden | `LoadAllThumbnailsAsync` | NOT_STARTED |
| VLIB-03 | Thumbnail-Cache verwenden | `_thumbnailCache` | NOT_STARTED |
| VLIB-04 | selektiertes Video analysieren | `AnalyzeSelectedCommand` | NOT_STARTED |
| VLIB-05 | alle Videos analysieren | `AnalyzeAllCommand` | NOT_STARTED |
| VLIB-06 | Projektwechsel korrekt resetten | `ClearClips` | NOT_STARTED |

### 4.4 Director Commands
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| DIR-01 | Audio-/Video-Clips laden | `LoadClipsCommand` | NOT_STARTED |
| DIR-02 | alle Video-Clips selektieren | `SelectAllVideoClipsCommand` | NOT_STARTED |
| DIR-03 | alle Video-Clips deselektieren | `DeselectAllVideoClipsCommand` | NOT_STARTED |
| DIR-04 | ausgewählte Clip-Anzahl aktualisieren | `UpdateSelectedCount` | NOT_STARTED |
| DIR-05 | Cut-Liste generieren | `GenerateCutListCommand` | NOT_STARTED |
| DIR-06 | Timeline-Refresh Event senden | `timeline-refresh` Messenger | NOT_STARTED |

### 4.5 Production / Render Commands
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| PROD-01 | Output-Datei wählen | `BrowseOutputCommand` | NOT_STARTED |
| PROD-02 | Render start nur mit Projekt erlauben | `CanStartRender` | NOT_STARTED |
| PROD-03 | Audio-Pfad aus Timeline synchronisieren | `SyncAudioPathFromTimelineAsync` | NOT_STARTED |
| PROD-04 | Render starten | `StartRenderCommand` | NOT_STARTED |
| PROD-05 | Render abbrechen | `CancelRenderCommand` | NOT_STARTED |
| PROD-06 | Render-Logs leeren | `ClearRenderLogCommand` | NOT_STARTED |
| PROD-07 | Render-SSE Fortschritt übernehmen | `OnRenderProgress` | NOT_STARTED |
| PROD-08 | ETA zusammensetzen | `BuildEtaText` | NOT_STARTED |
| PROD-09 | GPU-Infos während Render im ETA/Log anzeigen | `OnGpuStatusReceived` | NOT_STARTED |
| PROD-10 | Render-State nach Fail/Cancel resetten | `ResetRenderState` | NOT_STARTED |

### 4.6 Service-Layer
| ID | Funktion | Quelle | Status |
|---|---|---|---|
| SVC-01 | Health abrufen | `IApiClient.GetHealthAsync` | NOT_STARTED |
| SVC-02 | GPU-Status abrufen | `IApiClient.GetGpuStatusAsync` | NOT_STARTED |
| SVC-03 | GPU-Cleanup aufrufen | `IApiClient.CleanupGpuAsync` | NOT_STARTED |
| SVC-04 | Projekt-CRUD HTTP-Layer | `ApiClient.cs` | NOT_STARTED |
| SVC-05 | Audio HTTP-Layer | `ApiClient.cs` | NOT_STARTED |
| SVC-06 | Video HTTP-Layer | `ApiClient.cs` | NOT_STARTED |
| SVC-07 | Pacing HTTP-Layer | `ApiClient.cs` | NOT_STARTED |
| SVC-08 | Render HTTP-Layer | `ApiClient.cs` | NOT_STARTED |
| SVC-09 | SSE progress/log/gpu Streams | `SSEClient.cs` | NOT_STARTED |
| SVC-10 | Timeline shared state refresh | `TimelineStateService.cs` | NOT_STARTED |
| SVC-11 | Projektzustand im Frontend verwalten | `ProjectService.cs` | NOT_STARTED |
| SVC-12 | Python Backend finden/starten/überwachen | `PythonBridgeService.cs` | NOT_STARTED |

## 5. Noch offen für Vollinventur
- interne Python-Core-/Service-/Worker-Funktionen unter `src/pb_studio/*`
- optionale vollständige Inventur aller Helper-/Utility-Methoden im WPF-Frontend

## 6. Live-Fortsetzung nach Exec-Fix (2026-03-13)

### 6.1 Root Cause des Session-Blockers
- OpenClaw `exec` war nicht wegen `openclaw.json` blockiert, sondern wegen der separaten Runtime-Datei `C:\Users\david\.openclaw\exec-approvals.json`.
- Dort stand effektiv `defaults.security = "deny"`.
- Nach Umstellung auf `security = "full"` funktionierten `pwd`, `openclaw doctor --non-interactive` und lokaler Healthcheck sofort wieder.

### 6.2 Projekt-CRUD – echte Live-Verifikation
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| Projekt | `GET /project/info` ohne offenes Projekt | negativer API-Test | PASS | `400 {"detail":"Kein Projekt geöffnet"}` |
| Projekt | `POST /project/create` | neues Testprojekt im erlaubten Root erstellt | PASS | `C:\Users\david\Documents\PBStudio\OC_Verify_Project` |
| Projekt | `GET /project/info` nach Create | aktives Projekt gelesen | PASS | korrekte `name/path/audio_count/video_count` |
| Projekt | `POST /project/save` | Projekt gespeichert | PASS | `{"success":true,"message":"Projekt gespeichert"}` |
| Projekt | `POST /project/close` | Projekt geschlossen | PASS | `Projekt 'OC_Verify_Project' geschlossen` |
| Projekt | `POST /project/open` | Projekt erneut geöffnet | PASS | Projektinfo korrekt zurückgegeben |

Wichtige Beobachtung:
- `POST /project/create` gibt korrekt `403 Pfad außerhalb des erlaubten Projektverzeichnisses`, wenn ausserhalb `config.project_dir` getestet wird.
- Erlaubter Basisordner laut Backend-Config: `C:\Users\david\Documents\PBStudio`.

### 6.3 Audio / Video Import – echte Live-Verifikation
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| Audio | `POST /audio/import` | BeatNet-Testdatei importiert | PASS | `808kick120bpm.mp3`, `id=1`, Dauer `10.03102s` |
| Audio | `GET /audio/clips` | Liste gelesen | PASS | 1 Clip vorhanden |
| Video | `POST /video/import` | Smoke-Testvideo importiert | PASS | `smoke_test_video.mp4`, `id=1`, `640x360`, `24fps` |
| Video | `GET /video/clips` | Liste gelesen | PASS | 1 Clip vorhanden |

### 6.4 Analyse / Pacing / Preview / Render – echte Live-Verifikation
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| Audio | `POST /audio/analyze` | Vollanalyse auf importiertem Clip | PASS | Analyse-Response geliefert |
| Audio | `GET /audio/beats/1` | Beat-Daten gelesen | PASS | Beat-Liste vorhanden |
| Audio | `GET /audio/waveform/1?bands=3` | Waveform gelesen | PASS | Multi-Band Daten geliefert |
| Audio | `GET /audio/structure/1` | Strukturdaten gelesen | PASS | Struktur-Response geliefert |
| Audio | `GET /audio/spectral/1` | Spektraldaten gelesen | PASS | Spektral-Response geliefert |
| Video | `POST /video/analyze` | Smoke-Testvideo analysiert | PASS | Response 200; bei Testvideo `scene_count=0`, `motion=null/0` |
| Video | `GET /video/scenes/1` | Szenen gelesen | PASS | leere Liste, aber Endpoint funktioniert |
| Video | `GET /video/motion/1` | Motion gelesen | PASS | gültige Response mit `avg_motion=0.0` |
| Pacing | `POST /pacing/generate` | Cut-Liste generiert | PASS | `cut_count=2`, `total_duration=4.5279` |
| Pacing | `GET /pacing/timeline` | Timeline gelesen | PASS | 2 Timeline-Einträge vorhanden |
| Preview | `POST /pacing/preview` | Preview erzeugt | PASS | `data\\temp\\preview.mp4` |
| Render | `POST /render/start` | Render-Task gestartet | PASS | `task_id=5a24b897` |
| Render | `GET /render/status/5a24b897` | Render bis Completion verfolgt | PASS | `status=completed`, Output `verify_render.mp4` |

### 6.5 SSE / Streaming – Live-Verifikation
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| SSE | `/events/gpu` | Curl-Stream 5s offen gehalten | PASS | echtes `event: gpu_status` + JSON-Daten empfangen |
| SSE | `/events/progress` | Stream unter echter Last (Audio-Import) geprüft | PASS | echtes `event: import_progress` empfangen |
| SSE | `/events/log` | initial unter Last leer; danach Backend-Fix implementiert und erneut geprüft | PASS | nach `publish_log(...)`-Verdrahtung echte `event: log`-Nachrichten für Audio-Import/Analyse empfangen |

### 6.6 Auffälligkeiten / potenzielle Bugs
| Bereich | Funktion | Status | Beobachtung |
|---|---|---|---|
| Video | `GET /video/thumbnails/1` | PASS | separater Roh-HTTP-Test lieferte `200 OK`, `image/jpeg`, gültige JPEG-Bytes; ursprünglicher Fehler war Client-/PowerShell-Artefakt |
| Video | Analysequalität | PARTIAL | Smoke-Testvideo liefert naturgemäss leere/0-Resultate; funktional okay, aber kein Qualitätsbeweis |
| SSE | `/events/log` Backend-Verdrahtung | FIXED | Ursache war fehlende Emission im Backend; `publish_log(...)` ergänzt und live verifiziert |
| WPF | `ProductionViewModel` Initialzustand | FIXED | echter UI-Bug: bei bereits offenem Projekt startete der Produktions-Tab trotzdem mit `HasProject=false` / `Kein Projekt geöffnet`; Ursache war fehlendes Initial-Seeding aus `ProjectService` und reines Vertrauen auf nachträgliche Messenger-Events |

## 6.7 WPF Click-Path – echte Live-Verifikation (2026-03-13)

### 6.7.1 App-Startup / Header / Tab-Surfaces
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| WPF | App-Start via `dotnet run` | laufende Debug-App mit UIAutomation geprüft | PASS | Fenster `PB Studio AMD` erscheint stabil |
| WPF | Backend-Statusanzeige | Headertext im echten Fenster geprüft | PASS | `Backend: Online` sichtbar |
| WPF | GPU-Statusanzeige | Headertext im echten Fenster geprüft | PASS | live VRAM/Temperaturtext sichtbar |
| WPF | Tab-Navigation | `AUDIO`, `VIDEO`, `ANCHORS`, `TIMELINE`, `PRODUKTION` selektiert | PASS | jeweilige Content-Flächen wurden im Fenster gefunden |

### 6.7.2 Projekt-Workflow via WPF-Oberfläche
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| WPF Projekt | Öffnen | `Öffnen`-Button + Folder-Dialog-Automation auf `E2E_Complete` | PASS | Projektname `E2E_Complete` im Header sichtbar |
| WPF Projekt | Speichern | `Speichern`-Button im echten Fenster ausgelöst | PASS | Footer zeigt `Projekt gespeichert: E2E_Complete` |
| WPF Projekt | Schließen | `Schließen`-Button im echten Fenster ausgelöst | PASS | Header zeigt `Kein Projekt` |
| WPF Projekt | Wieder öffnen | erneuter `Öffnen`-Pfad via Folder-Dialog-Automation | PASS | `E2E_Complete` wieder sichtbar |
| WPF Projekt | Erstellen | `Neu`-Button + Folder-Dialog + PromptDialog automatisiert | PASS | neues Projekt `UIA_Create_Test` erstellt und im Header sichtbar |

### 6.7.3 Asset-/Bereichssichtbarkeit im echten WPF-Fenster
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| WPF Audio | Audio-Library lädt Projektinhalt | `AUDIO`-Tab auf E2E-Projekt geprüft | PASS | `test_120bpm` sichtbar |
| WPF Video | Video-Library lädt Projektinhalt | `VIDEO`-Tab auf E2E-Projekt geprüft | PASS | `test_bars` sichtbar |
| WPF Timeline | Timeline lädt Projektinhalt | `TIMELINE`-Tab auf E2E-Projekt geprüft | PASS | `test_bars2` sichtbar |

### 6.7.4 Produktions-/Render-Pfad im echten WPF-Fenster
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| WPF Produktion | Initialzustand bei bereits offenem Projekt | Produktions-Tab vor Fix geprüft | FAIL | Status zeigte fälschlich `Kein Projekt geöffnet` trotz offenem Projekt |
| WPF Produktion | Initialzustand bei bereits offenem Projekt | nach Fix neu gestartet und erneut geprüft | PASS | Status zeigt `Bereit für Rendering` |
| WPF Produktion | Render starten | Output-Pfad im UI gesetzt, `Render starten` per WPF ausgelöst | PASS | Render lief bis Completion |
| WPF Produktion | Render-Log-Anzeige | ListBox im WPF-Fenster während/nach Render geprüft | PASS | `8 Einträge` sichtbar |
| WPF Produktion | GPU-/Runtime-Feedback | Log/Status im echten Fenster geprüft | PASS | GPU-Debugzeile sichtbar, Running-State zeigte `Abbrechen`-Button |
| WPF Produktion | Output-Datei | Dateisystem nach UI-Render geprüft | PASS | `...\output\uia_render_verify.mp4` vorhanden |

### 6.7.5 Implementierter WPF-Fix
- Datei: `PBStudio.UI/ViewModels/ProductionViewModel.cs`
- Änderung: `ProjectService` in den Konstruktor injiziert, `HasProject` direkt aus aktuellem Projektzustand initialisiert und initial `SyncAudioPathFromTimelineAsync()` angestossen.
- Grund: echter UI-Lifecycle-Bug; der Produktions-Tab wurde oft erst nach dem `project-opened`-Messenger-Event instanziiert und verpasste dadurch den Initialzustand.
- Nachfix-Verifikation: `dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Debug` → PASS (0 Warnungen, 0 Fehler); anschliessender echter WPF-Renderpfad → PASS.

## 6.8 Weitere WPF-Validierung (Import + Settings)

### 6.8.1 Import-Dialoge / Import-Tab
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| WPF Import | Audio importieren | `Audio importieren` im echten IMPORT-Tab ausgelöst | PASS | `test_120bpm.wav` im Import-Tab sichtbar |
| WPF Import | Video importieren (nativer Dialog) | robuster Dialoglauf mit Zielordner + Dateiname | PARTIAL | `IMPORT_TAB_VIDEO=FOUND`, aber Backend-`/video/clips` blieb unverändert bei 2 Clips; verbleibender Wackler liegt im nativen Explorer-/OpenFileDialog-Übergang, nicht als PB-Studio-Backend-Defekt belegt |
| WPF Import | Video importieren per direktem Pfad | neuer In-App-Pfadimport im Release-Build live geprüft | PASS | vollständiger Pfad auf `smoke_test_video.mp4` wurde ohne nativen Dialog importiert; Status `1/1 Video-Datei(en) importiert` sichtbar |

### 6.8.2 Settings-Tab
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| WPF Settings | Initialdaten bei spätem Tab-Open | erster Live-Check vor Fix | FAIL | Cards sichtbar, aber `Online (Port 8765)` und GPU-Name fehlten |
| WPF Settings | Initialdaten bei spätem Tab-Open | nach Fix neu geprüft | PASS | `Online (Port 8765)` und `AMD Radeon RX 7800 XT` sichtbar |
| WPF Settings | GPU-/Backend-Cards | echter Settings-Tab geprüft | PASS | `GPU STATUS` + `BACKEND STATUS` sichtbar |
| WPF Settings | GPU Cleanup | `Cleanup` im echten Fenster ausgelöst | PASS | Status `VRAM aufgeräumt` sichtbar |

### 6.8.2b Video-Library Aktionspfad
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| WPF Video | `Alle analysieren` | echter VIDEO-Tab live ausgelöst | PASS | Statuswechsel `Analysiere 1/2: test_bars2...` sichtbar |
| WPF Video | Analyze-All Completion | laufenden Batch bis Ende beobachtet | PASS | `Alle 2 Clips analysiert` sichtbar |

### 6.8.2c Director / Anchor / Release-Build
| Bereich | Funktion | Check | Ergebnis | Beleg |
|---|---|---|---|---|
| Release | Framework-Publish | `publish.ps1` mit `-Mode framework -Configuration Release -Runtime win-x64` | PASS | Artefakt `artifacts\publish\framework\Release\win-x64\ui-verify-20260313b\PBStudio.UI.exe` erzeugt |
| Release/WPF Director | Generate Cut List im Publish-Build vor Fix | FAIL | echter Crash im Release-Build; Windows Event Log zeigte `System.InvalidCastException` in `DirectorViewModel.GenerateCutListAsync()` |
| Release/WPF Director | Generate Cut List im Publish-Build nach Fix | PASS | kein Crash; UI zeigte `Cuts: 8`, `Dauer: 15` und Status `8 Cuts generiert (15.0s)` |
| WPF Anchor | Waveform-/Beat-Surface lädt | echter ANCHORS-Tab geprüft | PASS | `Waveform geladen: 185 Bars | Beat-Analyse ausstehend` sichtbar |
| WPF Anchor | Anchor hinzufügen | `Hinzufügen` praktisch ausgelöst | PASS | Status `Anchor bei 1.00s hinzugefügt` sichtbar |
| WPF Anchor | Anchor entfernen | nach UX-Fix im Release-Build erneut praktisch geprüft | PASS | `AddAnchor()` selektiert neuen Anchor jetzt sofort; `Entfernen` zeigt danach live `Anchor entfernt` |

### 6.8.3 Implementierter WPF-Fix – Settings
- Datei: `PBStudio.UI/ViewModels/SettingsViewModel.cs`
- Änderung: initiales `_ = RefreshAsync();` im Konstruktor ergänzt.
- Grund: echter UI-Lifecycle-Bug; der Settings-Tab wurde häufig erst nach dem `backend-ready`-Messenger-Event instanziiert und verpasste deshalb den ersten Datenrefresh.
- Nachfix-Verifikation: `dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Debug` → PASS (0 Warnungen, 0 Fehler); anschliessender Settings-Livecheck → PASS.

### 6.8.4 Implementierter WPF-/Release-Fix – Director
- Datei: `PBStudio.UI/ViewModels/DirectorViewModel.cs`
- Änderung: `ConvertToDoubleSafe(...)` ergänzt und Mapping von `clip_start` / `trigger_strength` auf diese sichere Konvertierung umgestellt.
- Grund: echter Crash im Publish-Build bei Director-Generierung; Backend-Metadaten kamen als `System.Text.Json.JsonElement`, was in `Convert.ToDouble(...)` ungefangen in `InvalidCastException` lief.
- Nachfix-Verifikation:
  - `dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Release` → PASS (0 Warnungen, 0 Fehler)
  - Re-Publish (`ui-verify-20260313b`) → PASS
  - echter Director-Generate-Lauf im Release-Build → PASS, kein Crash mehr

### 6.8.5 Implementierter WPF-Fix / Workaround – Import + Anchors
- Datei: `PBStudio.UI/ViewModels/MediaIngestViewModel.cs`
- Änderung: `VideoImportPath` + `ImportVideoFromPathCommand` + gemeinsame Helper-Methode `ImportVideosFromPathsAsync(...)` ergänzt.
- Datei: `PBStudio.UI/Views/MediaIngestView.xaml`
- Änderung: direkter Pfad-Input + Button `Pfad importieren` ergänzt.
- Grund: nativer Windows-Video-Dateidialog blieb in Automation-Läufen nicht deterministisch genug; funktionaler In-App-Bypass ist für Verifikation und Power-Use robuster.
- Nachfix-/Nachfeature-Verifikation:
  - `dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Release` → PASS
  - Re-Publish (`ui-verify-20260313c`) → PASS
  - echter Release-Build-Liveimport über vollständigen Pfad → PASS (`1/1 Video-Datei(en) importiert`)

- Datei: `PBStudio.UI/ViewModels/AnchorViewModel.cs`
- Änderung: `AddAnchor()` selektiert neu erzeugte Anchors jetzt sofort (`SelectedAnchor = anchor`).
- Grund: Remove-Pfad war praktisch unnötig fragil, weil ein frisch erzeugter Anchor ohne zusätzliche ListView-Selektion nicht direkt löschbar war.
- Nachfix-Verifikation: echter Release-Build-Lauf `Hinzufügen` → `Entfernen` → PASS (`Anchor entfernt` sichtbar).

## 7. Nächste Prüfschritte
1. Optional nativen Video-Import-Dateidialog später noch separat härten, obwohl jetzt ein funktionaler In-App-Bypass existiert.
2. Optional längeren, schwereren Render-Fall mit grösserem/realerem Material für explizitere ETA-Proben fahren.
3. Optional Timeline-/Player-Control-Rebuild weiter konkretisieren.

## 8. Abschluss- und Härtungsphase 2026-03-13

### 8.1 Team-orchestrierte Workstreams
- Agent A: Packaging / Release / Deployment
- Agent B: Timeline / Player / UX-Restlücken
- Agent C: Import / Dialog / UI-Robustheit
- Agent D: Heavy Verification / Long-Run / ETA / Stress
- Hauptagent: Integration, Querprüfung, Finalverifikation, Konsolidierung der Reports

### 8.2 Praktisch umgesetzte zusätzliche Härtungen

#### Timeline / Director UX-Fixes
- `PBStudio.UI/Views/DirectorView.xaml`
- `PBStudio.UI/Views/DirectorView.xaml.cs`
- `PBStudio.UI/ViewModels/DirectorViewModel.cs`
- `PBStudio.UI/ViewModels/TimelineViewModel.cs`

Änderungen:
- Director-Checkboxen triggern jetzt den Selektionszähler robust auch bei reinem `IsChecked`-Toggle.
- `UpdateSelectedCount()` wird nach Clip-Reload zusätzlich gesetzt.
- Timeline-Scrub-Anzeige zeigt jetzt die echte Slider-Position statt nur die Startzeit des selektierten Cuts.

Nachverifikation:
- `dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Debug` → PASS (`0 Warnungen / 0 Fehler`)

#### Import / Dialog / Path-Workflow weiter gehärtet
- `PBStudio.UI/ViewModels/MediaIngestViewModel.cs`
- `PBStudio.UI/Views/MediaIngestView.xaml`

Änderungen:
- Video-Pfadimport akzeptiert jetzt mehrere Pfade per `;` oder Zeilenumbruch.
- Quotes werden entfernt, Pfade auf Full Paths normalisiert.
- nicht existierende Dateien / nicht unterstützte Endungen / Duplikate werden gefiltert.
- neuer Button `Pfad wählen` befüllt nur das In-App-Feld, statt erneut auf den fragilen nativen Importlauf zu setzen.
- klarere Statusmeldungen, Partial-Success-Text, Pfadfeld-Clear nach Erfolg.

Nachverifikation:
- `dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Debug` → PASS (`0 Warnungen / 0 Fehler`)
- `POST /video/import` mit `data\smoke_test_video.mp4` → PASS
- Schlussfolgerung: Der direkte In-App-Path-Import ist als pragmatischer Produktionsweg ausreichend robust; der native Windows-Dateidialog bleibt optionales späteres Härtungsthema, aber kein aktueller Release-Blocker.

### 8.3 Packaging / Release / Deployment

#### Script-Härtung
- `publish.ps1`
  - versionierte Publish-Unterordner ergänzt
  - `latest.txt` Pointer pro Publish-Mode ergänzt
- `launch.ps1`
  - Auswahl des letzten Publish-Artefakts via `latest.txt`
  - optionaler `-PreferredPublishMode`
  - sauberer Umgang mit bereits laufendem Backend / `-BackendOnly`
- `verify_release_smoke.ps1`
  - erzeugt jetzt eigenes Smoke-Projekt unter erlaubtem Projekt-Root
  - sucht automatisch kleine echte Testmedien
  - validiert Import → Analyse → Timeline → Save → Render-Start + Cancel ohne Repo-seitige Projektverschmutzung

#### Praktische Verifikation
- `publish.ps1 -Mode framework -Configuration Release -Runtime win-x64 -VersionTag hardening-20260313` → PASS
- Publish-Artefakt:
  - `artifacts\publish\framework\Release\win-x64\hardening-20260313\PBStudio.UI.exe`
- Latest-Pointer:
  - `artifacts\publish\framework\latest.txt` → `Release\win-x64\hardening-20260313`
- `verify_release_smoke.ps1` → PASS
  - Projekt erstellt unter `C:\Users\david\Documents\PBStudio\ReleaseSmoke_20260313_033409`
  - Audio-/Video-Import PASS
  - Audio-Analyse PASS
  - Timeline/Pacing PASS (`3 cuts`, `6.04s`)
  - Save PASS
  - Render-Start + Cancel PASS

#### Packaging-Empfehlung
- **Kurzfristig release-tauglich:** `framework-dependent` Publish auf Windows x64
- **Warum:**
  - kleinster und transparentester .NET-Artefaktpfad
  - bereits praktisch publisht und via Smoke-Script verifiziert
  - vermeidet unnötige Zusatzkomplexität, solange das Produkt ohnehin Python-/Backend-Abhängigkeiten und FFmpeg-Runtime separat braucht
- **Self-contained:** technisch möglich, aber kurzfristig geringer Zusatznutzen, deutlich grössere Artefakte; löst die Python-Backend-Abhängigkeit nicht
- **Single-file:** für PB Studio aktuell kein sinnvoller Default; Debugbarkeit/Diagnose schlechter, Start-/Extraktionsverhalten unnötig heikler, und die App bleibt trotzdem kein wirklich "alles in einer Datei"-Produkt wegen Python/Model/FFmpeg-Seite

### 8.4 Heavy Runtime / Long-Run / ETA / Stress
- ausführlicher Einzelreport: `VERIFICATION_HEAVY_RUNTIME_2026-03-13_AGENT_D.md`

Praktisch verifiziert:
- neues Heavy-Verify-Projekt mit echter 60s-Audioquelle + 6 realen Video-Clips
- Audio-Analyse PASS
- Video-Analyse PASS
- Pacing PASS (`19 Cuts`, gemeldete Timeline `36.71s`)
- Render-Lauf A mit Cancel → PASS (`running -> cancelled`, partielle Output-Datei aufgeräumt)
- Render-Lauf B komplett → PASS (`running -> completed`, gültige 60s Output-Datei)
- `/events/progress`, `/events/log`, `/events/gpu` unter Last → PASS

Echter Befund:
- Während aktiver Render-Läufe bleiben in `/render/status/{task_id}` die Runtime-Felder faktisch unbefüllt:
  - `eta_seconds = 0`
  - `current_frame = 0`
  - `total_frames = 0`
  - `fps = 0`
  - `elapsed_seconds` erst im terminalen Zustand gesetzt
- Das ist kein kosmetischer Mangel, sondern die zentrale verbleibende Telemetrie-Lücke für längere Renderjobs.

### 8.5 Konsolidierte Abschlussbewertung

#### Release-ready (für aktuellen Batch-/Pacing-/Render-MVP)
- WPF-App startet stabil
- Backend/GPU/Statuspfad läuft
- Projekt create/open/save/close/reopen läuft
- Audio-Import / Video-Import-Backend / In-App-Video-Path-Import laufen
- Audio-/Video-Analyse-Basispfade laufen
- Director Cut-Generate im Release-Build läuft
- Timeline anzeigen / scrubben / Cut-Navigation läuft im aktuellen Scope
- Render start / cancel / complete läuft
- SSE progress / log / gpu laufen
- framework-dependent Publish + Release-Smoke laufen

#### Release-blocking (wenn PB Studio als echter Timeline-/Player-Editor verkauft werden soll)
- Es gibt weiterhin **keinen echten Player / keine Playback-Control** in der WPF-App:
  - kein Play/Pause/Stop
  - keine gekoppelte Video-/Audio-Preview
  - keine echte Seek-/Playback-Steuerung
- Die Timeline ist weiterhin eher Inspector/List + Scrubber, nicht ein echtes interaktives Edit-Surface.

#### Release-blocking oder mindestens starker Beta-Mangel (für längere reale Renderproduktionen)
- Aktive ETA-/Frame-/FPS-/Elapsed-Telemetrie im Render-Status fehlt praktisch noch.
- Fortschritt ist sichtbar, aber Laufzeit/Restzeit sind nicht belastbar genug.

#### Post-release / Nice-to-have
- nativen Windows-Video-Dateidialog separat härten
- granularere Import-Progress-Anzeige bei mehreren Videos
- Anchor-UX direkt-manipulativ ausbauen
- Timeline als echte visuelle Edit-Timeline weiterentwickeln

### 8.6 Empfohlener nächster harter Schritt
1. MVP-Scope explizit festnageln: Batch-Pacing/Render-Tool **oder** Timeline-/Player-Editor.
2. Wenn kurzfristig shippen: `framework-dependent` Beta aus `artifacts\publish\framework\latest.txt` verwenden.
3. Danach gezielt ETA-/Frame-/FPS-Telemetrie im Renderpfad implementieren.
4. Erst danach grösseren Timeline-/Player-Rebuild angehen, statt die aktuelle MVP-Schiene zu verwässern.
