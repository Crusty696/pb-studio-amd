# PB Studio AMD — End-to-End Wiring Audit

**Datum:** 2026-05-07
**Auditor:** Full-Stack-Auditor (read-only, KEINE Code-Änderungen)
**Scope:** Backend-Endpoints ↔ WPF-Frontend ↔ GUI-Sichtbarkeit ↔ Live-Aktualisierung
**Hauptfrage:** Ist alles verdrahtet, wird jede Funktion live im GUI angezeigt — auch fürs Brain?

---

## TL;DR — die wichtigsten Funde

1. 🔴 **`use_brain` ist im GUI nicht erreichbar.** Backend, ApiClient und DTO unterstützen Brain-Annotation, aber `DirectorViewModel.GenerateCutListAsync` setzt `UseBrain` nie auf `true`. Folge: keine `cut_id`-Persistenz → Confidence-Balken bleibt rot, `/brain/explain/{cut_id}` schlägt fehl, `/brain/feedback` wirft 404, Lern-Session ist leer.
2. 🟠 **`/brain/suggest`-Endpoint ist eine TOTE LEITUNG.** ApiClient hat `BrainSuggestAsync`, aber kein ViewModel ruft es auf. Endpoint existiert nur „auf dem Papier".
3. 🟠 **`/pacing/preview`-Endpoint ist eine TOTE LEITUNG.** Im Backend implementiert, im Frontend nirgends gerufen. TimelineView nutzt einen lokalen `MediaElement`-Preview ohne Backend-Generierung.
4. 🟠 **VRAM-Budget-Daten aus `/health/vram` werden nicht angezeigt.** `VramTelemetryResponse.Budget` ist im Model deserialisierbar, aber `VramTelemetryViewModel.LoadAsync` ignoriert das Feld komplett. max/usable/reserved/committed bleiben unsichtbar.
5. 🟠 **FFmpeg-Pfad-Setting hat keine Wirkung im Backend.** SettingsView speichert ihn nach `%APPDATA%\PBStudio\settings.json`, aber `PythonBridgeService.StartAsync` propagiert ihn weder als Env-Var (`PBSTUDIO_FFMPEG_PATH`) noch als CLI-Arg. Backend nutzt weiterhin den Default-Pfad aus `backend/config.py`.
6. 🟡 **HIRN-Tab zeigt keine Cold-Start-Achsen-Liste, keine Variance, keinen Posterior** — nur die nackten Zähler `total_clicks / learned / cold_start`. Von "Cold-Start-Achsen anzeigen" oder "Posterior-Werte" wie im Brief gewünscht ist nichts da.

---

## Teil A — Inventar (jeder Endpoint, jede Verdrahtung)

| Endpoint | Backend-Datei | aufgerufen von Frontend? | live aktualisiert? | im GUI sichtbar? | Klarheit-Note |
|---|---|---|---|---|---|
| `GET /health` | `backend/main.py` | `ApiClient.GetHealthAsync` | nur per Aufruf (kein Polling) | ja: SettingsView Backend-Status (grüne/rote Ellipse + Text) | ✅ klar (Online/Offline) |
| `GET /health/heartbeat` | `backend/main.py` | **niemand** | – | nein | 🔴 TOTE LEITUNG (geplant für UI-Resilienz, ungenutzt) |
| `GET /health/vram` | `routers/health_router.py` | `ApiClient.GetVramTelemetryAsync` | DispatcherTimer 5 s in `VramTelemetryView` (PERFORMANCE-Tab) | partial: nur `telemetry`, nicht `budget` | 🟠 Telemetry mit Histogram-Balken klar; Budget-Werte fehlen |
| `GET /gpu/status` | `backend/main.py` | `ApiClient.GetGpuStatusAsync` | manuell via Refresh-Button + bei `backend-ready` | ja: SettingsView (Name, VRAM-Total, VRAM-Used, Temp, Treiber); MainWindow Header zeigt nur `VramUsed/VramTotal` | ✅ klar (MB, °C, alles beschriftet) |
| `POST /gpu/cleanup` | `backend/main.py` | `ApiClient.CleanupGpuAsync` | – (Button) | ja: SettingsView "Cleanup" + StatusText | ✅ klar |
| `POST /shutdown` | `backend/main.py` | `ApiClient.ShutdownAsync` | – (App-Exit) | nein (UI-Lebenszyklus) | n/a |
| `POST /project/create` | `routers/project_router.py` | `IApiClient.CreateProjectAsync` | – | ja: MainViewModel.CreateProject + StatusMessage | ✅ |
| `POST /project/open` | `routers/project_router.py` | `IApiClient.OpenProjectAsync` | – | ja: MainViewModel.OpenProject | ✅ |
| `POST /project/save` | `routers/project_router.py` | `IApiClient.SaveProjectAsync` | – | ja: MainViewModel.SaveProject | ✅ |
| `POST /project/close` | `routers/project_router.py` | `IApiClient.CloseProjectAsync` | – | ja | ✅ |
| `GET /project/info` | `routers/project_router.py` | `IApiClient.GetProjectInfoAsync` | beim `backend-ready`-Event | ja: MainWindow Header (Projekt-Name) | ✅ |
| `POST /audio/import` | `routers/audio_router.py` | `IApiClient.ImportAudioAsync` | – | ja: AudioLibraryView | ✅ |
| `GET /audio/clips` | `routers/audio_router.py` | `IApiClient.GetAudioClipsAsync` (limit=200) | nach Import / Refresh / project-opened | ja: AudioLibraryView Liste | ✅ |
| `POST /audio/analyze` | `routers/audio_router.py` | `IApiClient.AnalyzeAudioAsync` | SSE `analysis_progress` aktualisiert StatusText | ja: BPM/Key/BeatCount in AudioLibraryView | ✅ |
| `GET /audio/beats/{id}` | `routers/audio_router.py` | `IApiClient.GetBeatsAsync` | beim Timeline-Refresh / Audio-Wahl | ja: TimelineView Beat-Marker (grüne Linien) | ✅ |
| `GET /audio/onsets/{id}` | `routers/audio_router.py` | `ApiClient.GetOnsetsAsync` (NICHT in `IApiClient` — nur konkretes Class) | beim Timeline-Refresh | ja: TimelineView Snap-Marker (Akzent-Linien) | 🟡 fehlt im Interface — funktioniert via `ApiClient`-Direkttyp |
| `GET /audio/waveform/{id}` | `routers/audio_router.py` | `IApiClient.GetWaveformAsync` | beim Audio-Wahl im Timeline | ja: TimelineView Waveform-Layer | ✅ |
| `POST /audio/stems/separate` | `routers/audio_router.py` | `IApiClient.SeparateStemsAsync` | SSE | ja: aufrufbar von AudioLibrary | ✅ |
| `GET /audio/structure/{id}` | `routers/audio_router.py` | `ApiClient.GetStructureAsync` & `GetAsync<List<SongSegmentModel>>` | beim Timeline-Refresh | ja: TimelineView Sections-Layer (chorus/verse/intro/outro Hintergrundfarben) | ✅ |
| `GET /audio/spectral/{id}` | `routers/audio_router.py` | `ApiClient.GetSpectralAsync` & `GetAsync<SpectralDataModel>` | beim Timeline-Refresh | ja: TimelineView DepthRenderer | ✅ |
| `POST /video/import` | `routers/video_router.py` | `IApiClient.ImportVideosAsync` | SSE `import_progress` | ja: VideoLibraryView | ✅ |
| `GET /video/clips` | `routers/video_router.py` | `IApiClient.GetVideoClipsAsync` | – | ja: VideoLibraryView, DirectorView (Liste mit Checkbox) | ✅ |
| `GET /video/thumbnails/{id}` | `routers/video_router.py` | `IApiClient.GetThumbnailAsync` | bei Clip-Listen-Render | ja: VideoLibraryView Thumbnails | ✅ |
| `POST /video/analyze` | `routers/video_router.py` | `IApiClient.AnalyzeVideoAsync` | SSE | ja: Status / Indikator | ✅ |
| `GET /video/scenes/{id}` | `routers/video_router.py` | `IApiClient.GetScenesAsync` | – | grenzwertig: nur intern für Director? Keine direkte UI-Anzeige der Scene-Cuts mit Confidence | 🟡 Daten kommen, werden aber nicht visualisiert (kein Scene-Inspektor-Panel) |
| `GET /video/motion/{id}` | `routers/video_router.py` | `IApiClient.GetMotionAsync` | – | grenzwertig: kein Motion-Curve-Plot in der UI | 🟡 wie Scenes |
| `POST /pacing/generate` | `routers/pacing_router.py` | `IApiClient.GenerateCutListAsync` | SSE `analysis_progress` | ja: DirectorView CutList + StatusText | 🟠 `UseBrain` und `BrainMinConfidence` werden im PacingConfig-Record an Default `false`/`0.0` gelassen — siehe Teil B |
| `GET /pacing/timeline` | `routers/pacing_router.py` | `IApiClient.GetTimelineAsync` (via `TimelineStateService`) | bei `timeline-refresh`/`project-opened`-Messages, manuell via Refresh-Button | ja: TimelineView ListView+Canvas, ProductionView AudioPath | ✅ |
| `POST /pacing/timeline` (update) | `routers/pacing_router.py` | `IApiClient.UpdateTimelineAsync` | – | ja: TimelineViewModel.SyncTimelineAsync (nicht direkt im UI gebunden — kein "Speichern"-Button in TimelineView sichtbar) | 🟡 Methode existiert, aber kein Button — nur Auto-Sync nach Drag/Trim |
| `POST /pacing/preview` | `routers/pacing_router.py` | **niemand** | – | nein | 🔴 TOTE LEITUNG |
| `POST /render/start` | `routers/render_router.py` | `IApiClient.StartRenderAsync` | SSE `render_progress` | ja: ProductionView Progress, ETA, Log | ✅ klar (Frames, %, ETA, MB-Ausgabe) |
| `GET /render/status/{id}` | `routers/render_router.py` | `IApiClient.GetRenderStatusAsync` | – (SSE übernimmt Live-Updates) | ja als Polling-Backstop | ✅ |
| `POST /render/cancel/{id}` | `routers/render_router.py` | `IApiClient.CancelRenderAsync` | – (Button) | ja: ProductionView | ✅ |
| `GET /events/progress` (SSE) | `routers/events_router.py` | `SSEClient.ListenAsync(progress)` | live Stream + auto-reconnect | ja: ProductionView Progress, DirectorView StatusText, MainViewModel StatusBar | ✅ klar |
| `GET /events/log` (SSE) | `routers/events_router.py` | `SSEClient.ListenAsync(log)` | live | ja: ProductionView Render-Log | ✅ |
| `GET /events/gpu` (SSE) | `routers/events_router.py` | `SSEClient.ListenAsync(gpu)` | live alle 5 s | ja: MainWindow Header + ProductionView ETA-Zeile (nur wenn nicht rendert) | ✅ |
| `POST /brain/suggest` | `routers/brain_router.py` | `ApiClient.BrainSuggestAsync` (deklariert, nie aufgerufen) | – | nein | 🔴 TOTE LEITUNG |
| `POST /brain/feedback` | `routers/brain_router.py` | `BrainViewModel`, `LearningSessionViewModel` über Hotkeys 1–4 / Buttons | nach Klick → `BrainFeedbackAppliedMessage` triggert TimelineView-Live-Refresh des Confidence-Balkens für genau diesen Cut | ja: HIRN-Tab + Lern-Session-Dialog | 🟠 funktioniert nur, wenn `cut_id > 0` (Pacing mit `use_brain=true`) — sonst 404 |
| `POST /brain/learning_session` | `routers/brain_router.py` | `BrainViewModel.LoadLearningSessionAsync`, `LearningSessionViewModel.LoadAsync` | manuell (Button "Liste"/"Walkthrough") | ja: HIRN-Tab Liste + Dialog mit Video-Preview | 🟠 leer wenn keine Cuts mit `use_brain=true` generiert wurden |
| `GET /brain/stats` | `routers/brain_router.py` | `BrainViewModel.RefreshStatsAsync` | im ctor + nach Feedback + nach Reset | ja: HIRN-Tab Header (Klicks, gelernt/17, Cold-Start) + Top+ / Top− Buckets (α, β, L) | 🟡 Posterior, Variance, Cold-Start-Liste sind in der API-Response, werden aber NICHT gerendert (nur die Counter) |
| `POST /brain/reset` (request + confirm) | `routers/brain_router.py` | `BrainViewModel.ResetRequest/ConfirmAsync` | – | ja: HIRN-Tab "Reset anfordern"/"Reset bestätigen" | ✅ klar (zwei-Schritt-Flow) |
| `GET /brain/explain/{cut_id}` | `routers/brain_router.py` | `ApiClient.BrainExplainAsync` aus `TimelineViewModel.LoadBrainExplainAsync` | lazy beim Tooltip-Hover + Live-Refresh nach Feedback (`BrainFeedbackAppliedMessage`) | ja: TimelineView Confidence-Balken-Tooltip | 🟠 Tooltip-Code-Pfad ist verdrahtet, aber wegen `UseBrain=false` steht 99% der Zeit "Erklärung nicht verfügbar (kein cut_id)" |

---

## Teil B — TOTE LEITUNGEN

Backend-Endpoints, die existieren, aber von keinem Frontend-Konsumenten gerufen werden:

| Endpoint | Status | Auswirkung |
|---|---|---|
| `GET /health/heartbeat` | nie aus dem WPF gerufen | UI hat keine "billige" Lebenszeichen-Sonde — nutzt stattdessen `/health` (etwas teurer) und SSE-Reconnect-Heuristik |
| `POST /pacing/preview` | nie gerufen | Preview-Video wird nicht generiert; TimelineView spielt nur direkt die Originaldatei via lokalem `MediaElement` ab. Backend-Preview-Code ist totes Holz |
| `POST /brain/suggest` | nie gerufen | Top-N-Cut-Vorschläge werden niemandem gezeigt. Keine "AI-empfohlene Cuts" UI |

Frontend-DTO-Felder, die aus der Backend-Antwort verfügbar sind, aber nirgends gerendert werden:

| Feld | Quelle | warum tot |
|---|---|---|
| `VramTelemetryResponse.Budget` (max/usable/reserved/committed/safety/headroom) | `/health/vram` | `VramTelemetryViewModel` ignoriert `resp.Budget`. PERFORMANCE-Tab zeigt nur Telemetry pro Modell, nicht die VRAMBudgetManager-Stats. |
| `BrainStatsResponse.Posterior` (in jedem Bucket) | `/brain/stats` | HIRN-Tab Top+/Top− Listen zeigen nur α/β/L, nicht den `posterior`-Wert. |
| `BrainExplainResponse.BottomAxes` | `/brain/explain` | `TimelineViewModel.FormatExplainTooltip` schreibt nur `TopAxes` und `ColdStartAxes` — `BottomAxes` werden ignoriert. |
| `BrainExplainResponse.ContextKeys` | `/brain/explain` | nicht im Tooltip. |
| `VideoAnalysisResult.Scenes / Motion` (Detail-Daten) | `/video/scenes`, `/video/motion` | Endpunkte werden gerufen, aber kein Inspektor-Panel zeigt Scene-Cuts / Motion-Curve grafisch (nur intern fürs Pacing genutzt). |

---

## Teil C — Brain-spezifische Lücken (HAUPTFOKUS)

### C1. 🔴 Pacing wird nie mit `use_brain=true` gestartet

**File:** `PBStudio.UI/ViewModels/DirectorViewModel.cs` (`GenerateCutListAsync`, Zeile 216)
**Symptom:** `PacingConfig` wird ohne `UseBrain` und ohne `BrainMinConfidence` konstruiert → Default ist `false` / `0.0`.
**Folge-Effekte (Kaskade):**
- `pacing_router.generate_cut_list` skipped den `annotate_cuts_with_brain`-Block (Zeile 87 `if getattr(config, "use_brain", False)`).
- Cuts werden NICHT in `timeline_cuts` SQLite-Tabelle persistiert → **kein `cut_id`**.
- `TimelineEntry.BrainConfidence = 0.0` für alle Cuts → Confidence-Balken zeigt einheitlich rot (`ConfidenceToBrushConverter`).
- `TimelineEntry.CutId = null/0` → `LoadBrainExplainAsync` schreibt sofort `"Erklärung nicht verfügbar (kein cut_id)"` und ruft `/brain/explain` gar nicht erst.
- `/brain/learning_session` queryt `timeline_cuts` und liefert leere Liste → Lern-Session-Dialog hat keine Cuts.
- `/brain/feedback` über HIRN-Tab `SelectedCutId` schlägt mit 404 fehl, da der Cut in der DB nicht existiert.

**Bottom line:** Die GESAMTE Brain-UI ist im Default-Pfad mausetot, weil das Frontend dem Backend nie sagt "schalte das Brain ein".

### C2. 🟠 HIRN-Tab zeigt nicht alle Brain-Stats-Felder

**File:** `PBStudio.UI/Views/BrainView.xaml`
- `BrainStatsResponse.TopPositive[*].Posterior` (`(α+1)/(α+β+2)`) wird zurückgeliefert, aber nirgends gerendert. Das ist genau die Zahl, die "wie sicher" auf einer Achse aussagt.
- Keine Anzeige der Variance pro Bucket (Bayes-Varianz, die der `SmartSampler.select_uncertain` intern nutzt).
- Keine Liste aller Cold-Start-Achsen — nur ein Counter "Cold-Start: N". Welche 11 von 17 Achsen sind kalt?
- **Cold-Start-Achsen fürs Brain-Coaching** (vom Brief explizit gewünscht): nirgends sichtbar, weder in HIRN noch im Tooltip.

### C3. 🟠 LearningSessionDialog: holt Cuts via Sampler — aber Pfade können nie gefunden werden

**File:** `PBStudio.UI/ViewModels/LearningSessionViewModel.cs` (`ResolveVideoUri`, `LoadAsync`)
- `LoadAsync(audioPath, videoBasePath)` erwartet zwei Strings — aber **`BrainViewModel.OpenLearningSessionDialogAsync` ruft `vm.LoadAsync()` ohne Argumente** (Zeile 117 `await vm.LoadAsync();`). → `_projectAudioPath` und `_projectVideoBasePath` bleiben `null`.
- `ResolveVideoUri` returnt deshalb immer `null` → kein Video-Preview im Walkthrough.
- `CurrentAudioUri` ist immer `null` → kein Audio-Playback.
- **Hotkeys 1–4 + `/brain/feedback`-Aufruf funktionieren** (sind korrekt verkabelt, `BrainFeedbackAppliedMessage` wird gesendet).
- **Verdict:** Lern-Session ist „blind" — User sehen nur Score-Zahlen, keine Medien.

### C4. 🟡 Brain-Tooltip ist verdrahtet, aber inhaltlich unvollständig

**File:** `PBStudio.UI/ViewModels/TimelineViewModel.cs` (`FormatExplainTooltip`)
- ✅ TopAxes (Top-3) werden formatiert mit Achse, Score%, n_samples.
- ✅ ColdStartAxes-Liste wird angezeigt (max 6 + Overflow).
- ❌ `BottomAxes` (was zieht die Confidence runter?) wird nicht ausgegeben.
- ❌ `ContextKeys` (welche Kontexte greifen?) nicht angezeigt.
- ❌ Posterior und bridge_value pro Achse nicht ausgewiesen — nur der finale Score.
- 💡 Live-Update nach Feedback ist sauber: `BrainFeedbackAppliedMessage` → `TimelineViewModel.OnBrainFeedbackAppliedAsync` lädt `/brain/explain` neu, setzt `BrainConfidence` und Tooltip-Cache. **Das Live-Refresh-Mechanismus funktioniert wie spezifiziert** — wenn `cut_id` valide ist (siehe C1).

### C5. 🟠 `/brain/suggest` unbenutzt

`BrainSuggestAsync` ist in `IApiClient` deklariert, in `ApiClient` implementiert — aber kein ViewModel ruft es. Wenn der Use-Case "zeige Top-20 KI-Vorschläge fürs aktuelle Pacing" gewollt ist, fehlt die UI dafür komplett.

---

## Teil D — Konkrete Fix-Vorschläge (read-only Audit, NICHT umgesetzt)

| # | Lücke | Datei | Änderung | Größe |
|---|---|---|---|---|
| D1 | C1: `use_brain` nie aktiviert | `PBStudio.UI/Views/DirectorView.xaml` + `DirectorViewModel.cs` | CheckBox `IsChecked="{Binding UseBrain}"` ergänzen; `[ObservableProperty] _useBrain;` und im PacingConfig-Konstruktor `UseBrain: UseBrain` mitgeben | **S** (3 Properties + 1 CheckBox + 1 ctor-Arg) |
| D2 | C1: Min-Confidence-Filter | DirectorView + VM | Slider 0.0..1.0 für `BrainMinConfidence` (nur sichtbar wenn UseBrain=true) | **S** |
| D3 | C2: HIRN-Tab Posterior-Anzeige | `BrainView.xaml` ItemTemplate für TopPositive/Negative | Eine Zeile `<Run Text="{Binding Posterior, StringFormat={}{0:P0}}"/>` ergänzen | **S** |
| D4 | C2: Cold-Start-Achsen-Liste | `BrainView.xaml` neuer Card "COLD START" + `BrainViewModel` ObservableCollection<string> ColdStartList aus `/brain/stats` | API muss um `cold_start_axes_list: list[str]` erweitert werden ODER `axis NOT IN (learned_axes)` clientseitig gerechnet werden (BRIDGE_AXES kennt das C# nicht — also Backend-API erweitern) | **M** (Schema + Router + VM + XAML) |
| D5 | C2: Bayes-Varianz pro Bucket | Backend `/brain/stats`-Schema + HIRN-Tab | `posterior_variance` aus α,β rechnen `αβ/((α+β)²(α+β+1))`, in Schema + Spalte ergänzen | **M** |
| D6 | C3: LearningSessionDialog ohne Medien | `BrainViewModel.OpenLearningSessionDialogAsync` | `vm.LoadAsync(audioPath, videoBasePath)` mit echten Pfaden aus aktuellem Projekt aufrufen — ProjectService.CurrentProjectPath + state.current_audio_path nutzen | **S** |
| D7 | C4: Tooltip um BottomAxes/ContextKeys | `TimelineViewModel.FormatExplainTooltip` | Einen weiteren `sb.AppendLine("Bottom-Achsen:")`-Block anhängen + `e.ContextKeys` ausgeben | **S** |
| D8 | TOTE LEITUNG `/brain/suggest` | neue UI oder löschen | Entweder im DirectorView "Top-N Vorschläge" Panel ergänzen, oder Endpoint deprecaten | **M** (UI) bzw. **S** (Cleanup) |
| D9 | TOTE LEITUNG `/pacing/preview` | ProductionView oder TimelineView | "Preview rendern"-Button → `POST /pacing/preview` → `MediaElement` mit dem Result | **M** |
| D10 | VRAM Budget-Anzeige fehlt | `VramTelemetryView.xaml` Header + `VramTelemetryViewModel` | Neue Card oben mit max/usable/reserved/committed/safety/headroom aus `resp.Budget` rendern | **S** |
| D11 | FFmpeg-Pfad wirkt nicht im Backend | `PythonBridgeService.StartAsync` | Vor `Process.Start`: `startInfo.Environment["PBSTUDIO_FFMPEG_PATH"] = settings.FfmpegPath` setzen (analog `PYTHONPATH` und `PB_STUDIO_FORCED_VRAM`); SettingsService injizieren | **S** |
| D12 | `/health/heartbeat` ungenutzt | `MainViewModel` oder neuer `BackendHealthService` | DispatcherTimer alle 3 s ruft `/health/heartbeat` statt nichts → präziseres Online/Offline-Flag, früherer Reconnect-Trigger | **S** |
| D13 | `GetOnsetsAsync` fehlt im `IApiClient` | `IApiClient.cs` | Methode in Interface ergänzen — sonst nicht mockbar in Tests | **S** |
| D14 | Scene-/Motion-Daten nirgends sichtbar | VideoLibraryView Inspektor-Panel oder TimelineView Overlay | Scene-Cuts als Marker im Clip-Thumbnail, Motion-Curve als kleines Sparkline neben jedem Clip | **L** (echtes UI-Konzept) |

---

## Teil E — Was funktioniert gut (NICHT kaputtmachen)

1. **SSE-Architektur ist sauber.**
   - 3 Streams (`progress`, `log`, `gpu`) mit per-client Queues (kein Fan-out-Bug mehr).
   - Auto-Reconnect mit exponential backoff + max 50 Versuche.
   - Keepalive-Kommentare alle 15 s.
   - Verbraucher (DirectorView, ProductionView, MainViewModel) abonnieren disjunkte EventTypes.
   - Saubere Disposal-Order in `SSEClient.Dispose` (Tasks first, dann HttpClient).

2. **Render-Live-Updates sind exemplarisch.**
   - Backend pusht `render_progress` mit Frame, FPS, ETA.
   - `ProductionViewModel.ApplyProgressUpdate` rendert Status, Progress, ETA-Text korrekt.
   - Cancel-Flow ist robust (Progress-Callback prüft Cancel-Flag pro Frame).

3. **Confidence-Balken Live-Refresh nach Feedback.**
   Der Loop `BrainViewModel.SendFeedbackAsync` → `BrainFeedbackAppliedMessage` → `TimelineViewModel.OnBrainFeedbackAppliedAsync` → `BrainExplainAsync` neu laden + `BrainConfidence` updaten ist **architektonisch sauber gelöst**. Nur an der Eintrittsbedingung (`cut_id > 0`) hapert es wegen C1.

4. **VRAM-Telemetry-Auto-Refresh** mit DispatcherTimer im PERFORMANCE-Tab hat sauberes Loaded/Unloaded-Lifecycle (`IsActive`-Property), sortiert Cards nach Beobachtungszahl, Histogram-Balken sind relativ skaliert. Nur Budget-Block fehlt.

5. **Path-Traversal-Schutz** in `project_router` und `render_router` (`Path.is_relative_to(allowed_base)`) ist sauber gegen aktive Projekt-Root oder globalen project_dir geprüft.

6. **Settings-Persistenz** für `VramCapMb` und `ForcedVramMb` funktioniert: `SetForcedVramEnvVar` wird beim Load **und** beim Save aufgerufen → Env-Var wirkt nach Backend-Restart. Korrekt.

7. **Atomic Writes** für `project.json` und `timeline.json` (tmp + `os.replace`) sind R17-konform.

8. **GPU-Status im Header** (`MainWindow`) wird live von SSE `gpu_status` gefüttert (alle 5 s) → korrekt formatiert als `MB/MB`. Beschriftung klar.

9. **Render-Log** in `ProductionView` führt Level-Präfixe (`[INF] [WRN] [ERR] [DBG]`), Zeitstempel, ringbuffer 300 Zeilen — robust und klar.

10. **Log-Rotation in Backend** (Punkt 4 des Briefs): `backend/main.py` Z34–63 initialisiert sauber `setup_rotating_logging` mit 10 MB / gzip / 7-Tage-Retention. Keine GUI nötig — Anforderung erfüllt.

---

## Selbst-Kritik (Auditor-Limitierungen)

- **Nicht überprüft:** ob `WaveformBars`/`BeatMarkers`/`SnapMarkers` tatsächlich pixelgenau auf der Timeline-Achse landen — das ist Pixel-Math, der hier nicht laufzeitgetestet wurde.
- **Nicht überprüft:** ob `ConfidenceToBrushConverter` in allen Schwellenwert-Bereichen einen sinnvollen Farbverlauf liefert — nur die Verkabelung, nicht das visuelle Ergebnis.
- **Nicht überprüft:** dass die SQLite-`timeline_cuts`-Tabelle existiert und in `/state.db` initialisiert wird, wenn ein Projekt zum ersten Mal mit `use_brain=true` gerendert wird (wäre eine separate Brain-DB-Schema-Prüfung).
- **Nicht laufend getestet:** die SSE-Reconnect-Logik unter realem Backend-Crash (statisch korrekt, aber Race-Conditions beim Backend-Restart-during-Stream nicht beobachtet).
- **VideoLibraryViewModel + AudioLibraryViewModel** wurden nicht bis ins Detail durchforstet — Fokus war Brain-/VRAM-/Settings-/Timeline-Verdrahtung. Falls dort ungenutzte Endpoints oder fehlende Live-Updates bestehen, sind sie hier nicht erfasst.
- **Annahme:** `IApiClient` ist die einzig genutzte Frontend-Backend-Schnittstelle — nicht geprüft ob es einen weiteren HTTP-Pfad (`PythonBridgeService` hat eigenen `HttpClient` für `/health` und `/shutdown`) gibt, der parallele Verdrahtung darstellt. Sieht aber so aus, als ob das nur Lifecycle-Operationen sind.

---

## Antwort auf die zentrale User-Frage

> "Ist ALLES verdrahtet? Wird jede Funktion im GUI angezeigt und kontinuierlich aktualisiert? Ist die Anzeige im GUI korrekt und klar — auch fürs Brain?"

**Kurz:** Nein, nicht ganz.
- ⚙️ **Verdrahtung Backend↔ApiClient:** zu ~90 % vollständig. 3 echte tote Leitungen (`/health/heartbeat`, `/pacing/preview`, `/brain/suggest`).
- 🧠 **Brain im GUI:** technisch vorhanden (HIRN-Tab + Confidence-Balken + Tooltip + Lern-Session-Dialog), aber **funktional gelähmt**, weil das Frontend kein `use_brain=true` an Pacing schickt. Sobald D1 (CheckBox + Pass-through) gefixt ist, lebt die ganze Brain-Pipeline auf einen Schlag.
- 🔄 **Live-Aktualisierung:** SSE-basiert ausgezeichnet für Render und Analysis. Brain-Confidence-Balken ist live (per Messenger). VRAM-Telemetry läuft mit 5-s-Polling. GPU-Status mit 5-s-Push. Was fehlt: **Brain-Stats werden NICHT auto-refresht** — nur nach manuellem Klick auf "↻ Aktualisieren". Bei aktiver Lern-Session sieht man Klick-Fortschritt nur durch erneutes Drücken des Buttons.
- 📐 **GUI-Klarheit:** Einheiten überall vorhanden (MB, ms, %, °C, s, fps). Error-States in VRAM-Cards farbcodiert. Loading-States als IsLoading/IsGenerating boolean → Buttons disablen, ProgressBar IsIndeterminate. Backend-Online-Anzeige mit grüner/roter Ellipse. Klarheit insgesamt: **gut**, mit Schwächen in der HIRN-Sektion (Posterior/Variance/Cold-Start-Liste fehlen wie oben beschrieben).

---

**Status:** Audit abgeschlossen. Keine Code-Änderungen vorgenommen.
**Nächster Schritt** (User entscheidet): Welche der 14 Fix-Vorschläge sollen umgesetzt werden? D1+D6+D11 sind die strategisch wichtigsten (kleinste Fixes, größte Funktions-Wiederbelebung).
