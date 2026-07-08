# AUDIT — Frontend Wiring (WPF) — 2026-05-11

Read-only Deep-Audit der PBStudio.UI WPF-Schicht.
Scope: `Services/`, `ViewModels/`, `Views/`, `Models/`, `Converters/`, `Services/Messages/`, `App.xaml(.cs)`, `MainWindow.xaml`.

---

## 0. Pipeline-Flow (How does it actually wire today?)

```
              ┌────────────────────────────────────────────────────────┐
              │           App.xaml.cs (DI Composition Root)            │
              │  AddHttpClient<ApiClient> ─▶ Singleton IApiClient      │
              │  Singleton SSEClient (separater HttpClient, 127.0.0.1) │
              │  Singleton PythonBridgeService (eigener HttpClient)    │
              │  Singleton State-Services (Audio/Video/Timeline)       │
              │  Transient ViewModels (Ioc.Default)                    │
              └────────────────────────────────────────────────────────┘
                                       │
       ┌───────────────────────────────┼───────────────────────────────┐
       ▼                               ▼                               ▼
 ┌───────────┐               ┌─────────────────┐               ┌────────────┐
 │ ApiClient │               │   SSEClient     │               │   Python   │
 │   (HTTP)  │  REST/JSON    │ (3 SSE streams) │  Backend SSE  │   Bridge   │
 └─────┬─────┘               └────────┬────────┘               └──────┬─────┘
       │                              │                               │
       │ Methoden                     │ Events                        │ Lifecycle
       │  ImportAudio /VideosAsync    │  ProgressReceived             │  Start/Stop
       │  AnalyzeAudio /VideoAsync    │  LogReceived                  │  Watchdog
       │  GenerateCutListAsync        │  GpuStatusReceived            │  Env-Vars
       │  StartRenderAsync            │  ConnectionStateChanged       │  (PB_STUDIO_FORCED_VRAM
       │  BrainSuggest /Feedback /…   │                               │   PBSTUDIO_FFMPEG_PATH)
       │  GetVramTelemetryAsync       │                               │
       └──────┬───────────────────────┴───────────────────────────────┘
              │
              ▼ (subscribed in VMs via events oder WeakReferenceMessenger)
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  ViewModels (alle ObservableObject, mit Ausnahme Brain/LearningSession   │
 │  alle IDisposable + UnregisterAll<this>)                                 │
 │                                                                          │
 │  MainViewModel ─── TabSelectedIndex ──┐                                  │
 │  ProjectOverview / MediaIngest         │                                 │
 │  AudioLibrary / VideoLibrary           │── State-Services (cache)        │
 │  Anchor                                │                                 │
 │  Director (Pacing-Config + Brain)      │── ApiClient                     │
 │  Timeline (Waveform, Beats, Spectral,  │── SSEClient                     │
 │            MotionCurve, BrainExplain)  │── WeakReferenceMessenger        │
 │  Production (Render + L-N5 Bitrate +   │   (typed F4 records,            │
 │              L-N6 Encoder)             │    Director/Brain/Feedback)     │
 │  Settings / Brain / LearningSession    │                                 │
 │  VramTelemetry                         │                                 │
 └─────────────────────────────────┬────────────────────────────────────────┘
                                   │ DataBinding (Ioc.Default DataContext)
                                   ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ Views (alle UserControl + Code-Behind nur fuer DataContext + 3 wirklich  │
 │ View-spezifische Aufgaben: MultiSelect-Sync, MediaElement-Playback,      │
 │ Clip-Drag/Trim in TimelineView)                                          │
 └──────────────────────────────────────────────────────────────────────────┘
```

**Messenger-Topologie (typed F4 records):**

| Sender → Subscriber | Message | Subscriber |
|---|---|---|
| `ProjectService` | `ProjectOpenedMessage` | Main, ProjectOverview, MediaIngest (kein listener?), AudioLib, VideoLib, Anchor, Director, Timeline, Settings (indirect via BackendReady) |
| `ProjectService` | `ProjectClosedMessage` | Audio/Video/Anchor/MediaIngest/Director/Timeline/Production |
| `AudioLibraryVM` / `MediaIngestVM` | `AudioImportedMessage` | AudioLib, Anchor, ProjectOverview |
| `AudioLibraryVM` | `AudioLibraryRefreshMessage` | AudioLib, Anchor, Director |
| `VideoLibraryVM` / `MediaIngestVM` | `VideoImportedMessage` | VideoLib, ProjectOverview |
| `VideoLibraryVM` | `VideoLibraryRefreshMessage` | VideoLib, Director |
| `AudioLib` / `VideoLib` / `MediaIngest` | `MediaLibraryRefreshMessage` | AudioLib, VideoLib, Anchor, Director, ProjectOverview |
| `DirectorVM` | `TimelineRefreshMessage` | Timeline |
| `ProjectOverviewVM` | `NavigateDirectorMessage` | Main |
| `MainVM` (post-init) | `ProjectOpenedMessage` (re-fire) | (alle Subscriber, redundant zu ProjectService) |
| `BrainVM` / `LearningSessionVM` | `BrainFeedbackAppliedMessage(int CutId)` | Timeline |
| (nirgendwo gesendet) | `BackendReadyMessage` | SettingsVM (subscribed-but-never-fired) |
| (nirgendwo gesendet) | `AppShutdownMessage` | VideoLib, Settings (subscribed-but-never-fired) |
| (nirgendwo gesendet) | `ProjectClosingMessage` | VideoLib, MediaIngest (subscribed-but-never-fired) |

---

## 1. Findings (L-FE-N)

> Schweregrade: **HIGH** (Crash-/Drift-/Leak-Risiko), **MED** (Funktional eingeschraenkt), **LOW** (Cleanup/Polish).

### L-FE-1 — `TimelineViewModel` haengt an konkretem `ApiClient` statt `IApiClient` (HIGH, Architektur-Bruch)

**Datei:** `PBStudio.UI/ViewModels/TimelineViewModel.cs:22, 119`

```csharp
private readonly ApiClient _api;           // <-- konkret, nicht Interface
public TimelineViewModel(TimelineStateService …, AudioLibraryStateService …, ApiClient api)
```

Alle anderen VMs (Audio, Video, Director, Production, Settings, Anchor, Brain, LearningSession, MediaIngest, VramTelemetry, ProjectOverview, Main) injizieren `IApiClient`. TimelineVM bricht die Abstraktion. DI funktioniert nur, weil `App.xaml.cs:107` `IApiClient` als `sp.GetRequiredService<ApiClient>()` registriert — **wenn jemand `IApiClient` umstellt auf einen Decorator/Mock, faellt Timeline raus**. Auch fuer Tests blockierend.

**Sekundaereffekt:** TimelineVM ruft `_api.GetOnsetsAsync()` (L-FE-2) — diese Methode existiert nur auf der Klasse, nicht im Interface. Daher MUSSTE der Autor die Klasse direkt injizieren. Echte Bug-Wurzel.

---

### L-FE-2 — `IApiClient` fehlt `GetOnsetsAsync` und `GetAsync<T>` Konsumenten unterlaufen Interface (HIGH, Schema-Drift Risiko)

**Datei:** `PBStudio.UI/Services/IApiClient.cs` (kein Eintrag fuer `GetOnsets`)
**Datei:** `PBStudio.UI/Services/ApiClient.cs:123`

```csharp
// IApiClient.cs:30
Task<List<BeatData>?> GetBeatsAsync(int clipId);
// ... aber KEIN:
// Task<List<double>?> GetOnsetsAsync(int clipId);
```

**TimelineViewModel.cs:445** ruft `_api.GetOnsetsAsync(audioClip.Id)`. Endpoint `GET /audio/onsets/{clip_id}` existiert im Backend (`audio_router.py:386`).

**Genauso problematisch:** TimelineVM nutzt `_api.GetAsync<SpectralDataModel>($"/audio/structure/{id}")` und `_api.GetAsync<SpectralDataModel>($"/audio/spectral/{id}")` zwar uebers Interface (das `GetAsync<T>` ist im Interface) — aber damit **wird das Schema-Mapping (Backend SpectralData mit `List<float>` vs UI `List<double>`) implizit gemacht**. Mismatch zwischen `SpectralData` (in `ApiClient.cs:436`: `Dictionary<string, List<float>>`) und `SpectralDataModel` (`SpectralDataModel.cs:12`: `Dictionary<string, List<double>>`) wird durch case-insensitive JSON parser nur ueber `double`-Cast gerettet. Sollte vereinheitlicht werden.

---

### L-FE-3 — Stale-`SeparateStems` Endpoint nicht im Interface (MED, Schema-Drift)

**Datei:** `PBStudio.UI/Services/IApiClient.cs:31` (alt) vs `ApiClient.cs:126`

Interface hat die Methode `SeparateStemsAsync(...)`. **Aber:** `DeleteAudioClipAsync` und `DeleteAudioClipsBatchAsync` sind im Interface (Zeilen 32/33). **`SeparateStemsAsync` ist auch drin, OK.** Kein Drift hier — nur Kontroll-Pruefung. ✅

---

### L-FE-4 — Tote `[ObservableProperty]` in DirectorViewModel: SnareWeight, HihatWeight, MaxClipLength, OnsetSensitivity, MinClipLength (MED, Dead Code)

**Datei:** `PBStudio.UI/ViewModels/DirectorViewModel.cs:28-37`

```csharp
[ObservableProperty] private double _snareWeight = 1.0;
[ObservableProperty] private double _hihatWeight = 0.3;
[ObservableProperty] private double _maxClipLength = 8.0;
[ObservableProperty] private double _minClipLength = 1.0;
[ObservableProperty] private double _onsetSensitivity = 0.5;
```

DirectorView.xaml bindet **nur** `BeatWeight`, `KickWeight`, `EnergyWeight`, `EnergyThreshold`, `OnsetWeight`, `MinCutInterval`, `UseMotion/Semantic/Structure/Brain/Key/StemMatching`, `BrainMinConfidence`. Die fuenf obigen Properties werden in der UI **nie gesetzt**, aber als Konstrukturargumente fuer `TriggerSettings` an `/pacing/generate` geschickt (Zeile 255-266). User sieht z.B. "Snare-Gewichtung" gar nicht — Backend bekommt Default 1.0.

**Effekt:** drei AddedFeatures ohne UI. Entweder Slider in der XAML nachruesten (Pacing-Card erweitern) oder Felder entfernen falls bewusst stale.

---

### L-FE-5 — `TimelineViewModel.HorizontalOffset` Property nirgends gebunden (LOW, Dead Code)

**Datei:** `PBStudio.UI/ViewModels/TimelineViewModel.cs:38`

```csharp
[ObservableProperty] private double _horizontalOffset = 0.0;
```

Wird nirgends in der XAML konsumiert. TimelineView code-behind nutzt direkt `ScrollViewer.HorizontalOffset` ueber den Visual-Tree (Zeilen 84-97). **Dead** — vermutlich wurde geplant das ueber TwoWay-Binding zu synchronisieren, dann durch das direkte VisualTree-Scrolling ersetzt.

---

### L-FE-6 — `AudioClipModel.Channels` / `SampleRate` / `Format` nirgends in Views gebunden (LOW, Display-Gap)

**Datei:** `PBStudio.UI/Models/AudioClip.cs:14-16`

Felder werden persistiert + befuellt (ApiClient → VM → Model), aber AudioLibraryView.xaml zeigt nur Bpm/Key/BeatCount/Duration in den Metric Cards. Sample-Rate (44.1k/48k) ist normalerweise eine fuer DJ-Workflow relevante Info — sollte irgendwo angezeigt werden. Aktuell tote Information.

---

### L-FE-7 — `BrainViewModel` und `LearningSessionViewModel` ohne IDisposable + WeakReferenceMessenger-Leak (HIGH, Memory-Leak)

**Datei:** `PBStudio.UI/ViewModels/BrainViewModel.cs:12`, `PBStudio.UI/ViewModels/LearningSessionViewModel.cs:14`

```csharp
public partial class BrainViewModel : ObservableObject       // <-- kein : IDisposable
public partial class LearningSessionViewModel : ObservableObject // <-- kein : IDisposable
```

`BrainViewModel.SendFeedbackAsync` ruft `WeakReferenceMessenger.Default.Send(new BrainFeedbackAppliedMessage(...))`, ist also Sender, nicht Subscriber — aber holt sich aus DI `LearningSessionViewModel` (`BrainViewModel.cs:124`). Die Brain/Learning VMs sind transient, leben pro Tab-Switch (Brain) bzw. pro Dialog-Open (LearningSession). **Beide cleanen weder `WeakReferenceMessenger.Default.UnregisterAll(this)` noch sind sie disposable.** Service-Provider disposed sie nicht weil kein IDisposable → Subscriptions persistieren. Aktuell keine `Register` calls in BrainVM (= kein direkter Leak), aber LearningSessionVM sendet auch via WeakReferenceMessenger und sammelt Event-Handlers (`RequestClose`, `PlayRequested`, etc.) die der Dialog (`LearningSessionDialog.xaml.cs`) abonniert — auch keine Unsubscribe. Wenn der Dialog `.Close()` wird, bleiben Event-Handler-Bindings stehen → Dialog kann nicht GCd werden bis VM gehoer endet.

**Fix:** beide VMs `: IDisposable` machen, ServiceProvider macht Cleanup; oder Dispose-Pattern beim Schliessen.

---

### L-FE-8 — `ConfigureAwait` inkonsistent (LOW, Convention-Drift)

**Beispiele:**
- `TimelineViewModel.cs:443-447` (`GetWaveformAsync`, `GetBeatsAsync`, `GetOnsetsAsync`, `GetAsync<...>`) → **alle ohne** `.ConfigureAwait(false)`.
- `TimelineViewModel.cs:211` (`GetMotionAsync`) → **mit** `.ConfigureAwait(false)`.
- `AudioLibraryViewModel.cs:227, 341, 386` → ohne ConfigureAwait.
- `ApiClient.cs:*` → **konsequent mit** `.ConfigureAwait(false)`.

WPF mit MVVM-Toolkit ist toleranter (Dispatcher-Context), aber Mischbetrieb erschwert das Reasoning ueber Thread-Affinitaet. Die VM-Methoden setzen alle danach ObservableProperties oder rufen `Application.Current.Dispatcher.InvokeAsync` — d.h. `ConfigureAwait(false)` waere noetig fuer korrekten Off-UI-Resume, aber dann sind direkte Property-Sets danach falsch. Aktueller Code passt nur weil die Methoden mehrheitlich vom UI-Thread starten und Sync-Context kapturen.

---

### L-FE-9 — `Subscribed-but-never-fired` Messages (`AppShutdownMessage`, `BackendReadyMessage`, `ProjectClosingMessage`) (MED, Dead Wire)

**Datei:** `PBStudio.UI/Services/Messages/AppMessages.cs:28-29, 25`

| Message | Sender? | Subscriber |
|---|---|---|
| `AppShutdownMessage` | **NIRGENDS gesendet** | VideoLibraryVM:87, SettingsVM:69 |
| `BackendReadyMessage` | **NIRGENDS gesendet** | SettingsVM:68 |
| `ProjectClosingMessage` | **NIRGENDS gesendet** | VideoLibraryVM:85, MediaIngestVM:38 |

Symptome:
- VideoLib + MediaIngest haben einen `HandleProjectEnd`-Pfad an `ProjectClosingMessage` — wird nie aufgerufen, nur `ProjectClosedMessage` triggert ihn. Fuer den User unsichtbar weil beide Pfade dasselbe tun.
- SettingsVM erwartet ein `BackendReadyMessage` um nach dem ersten Start die GPU-Stats neu zu laden — kommt aber nie. Stattdessen funktioniert die Settings-Page nur weil der Ctor sofort `_ = RefreshAsync()` aufruft. Wenn das Backend zu spaet kommt, sieht User permanente "Backend: Offline" bis manueller "↻ Refresh"-Klick. **Spuerbar.**

**Fix:** `BackendReadyMessage` aus `MainViewModel.InitializeAsync` senden wenn `_bridge.IsRunning` true wird; `AppShutdownMessage` aus `App.xaml.cs:OnExit`; `ProjectClosingMessage` aus `ProjectService.CloseProjectAsync` vor `_api.CloseProjectAsync`.

---

### L-FE-10 — `MainViewModel.OnProgressReceived` schreibt `StatusMessage = e.Message` ohne Event-Type-Filter (MED, UI-Spam)

**Datei:** `PBStudio.UI/ViewModels/MainViewModel.cs:191-197`

```csharp
private void OnProgressReceived(object? sender, ProgressEventArgs e) {
    _ = App.Current.Dispatcher.InvokeAsync(() => {
        StatusMessage = e.Message;
    });
}
```

Subscribed an `_sse.ProgressReceived` — wird fuer `analysis_progress`, `render_progress`, `stem_progress`, `import_progress`, `gpu_error` gefeuert. Alle ueberschreiben den globalen Status-Bar-Text in MainWindow. Bei parallelen Operations (z.B. Render + Stem im Hintergrund) flackert die Status-Bar.

**Fix:** Nur fuer Top-Level-Events (z.B. `render_progress` oder Fehler), oder ein Stack/Queue von Progress-Meldungen.

---

### L-FE-11 — `MainWindow.xaml` Resource `BooleanToVisibilityConverter` doppelt definiert (LOW, Resource-Pollution)

**Datei:** `PBStudio.UI/MainWindow.xaml:23`

```xml
<BooleanToVisibilityConverter x:Key="BooleanToVisibilityConverter"/>
```

Existiert bereits in `App.xaml:16` global. Lokales Override macht keinen Schaden (gewinnt Lookup-Hierarchie), ist aber unnoetig.

---

### L-FE-12 — `Application.Current.Dispatcher.Invoke` vs `InvokeAsync` Mischbetrieb (LOW, Latency)

VMs nutzen mal `.Invoke(...)` (synchron, blockierend) mal `.InvokeAsync(...)` (asynchron). Mehrheitlich `.InvokeAsync`, aber:

- `AudioLibraryViewModel.cs:57, 64, 77` `.Invoke` (synchron)
- `VideoLibraryViewModel.cs:182` `.Invoke` (synchron)
- `TimelineViewModel.cs:82, 95` `.Invoke` (synchron)
- `DirectorViewModel.cs:96, 406` `.Invoke` (synchron)
- `ProductionViewModel.cs:62, 69` `.Invoke` (synchron)

In SSE-Event-Handlern (auf Background-Thread): `.Invoke` blockiert den Thread bis UI-Dispatch fertig — der naechste SSE-Event wartet → potentiell langsam wenn UI gerade busy. `.InvokeAsync` waere idiomatisch. Kein Crash, nur Latenz.

---

### L-FE-13 — `DirectorViewModel.cs` Audio-Clip mappt `StemsPaths`/`AudioHash` NICHT (MED, Feature-Drift L-N2/L-N4)

**Datei:** `PBStudio.UI/ViewModels/DirectorViewModel.cs:141-154`

```csharp
AvailableAudioClips.Add(new AudioClipModel {
    Id = clip.Id, Name = …, Path = …, DurationSeconds = …,
    SampleRate = …, Channels = …, Format = …,
    Bpm = …, Key = …, BeatCount = …, IsAnalyzed = …,
    // KEIN AudioHash, KEIN StemsPaths
});
```

Im AudioLibraryView macht der ViewModel das (Zeile 270-287). Im Director NICHT. Bedeutet: wenn der User im Director-Tab den AudioComboBox aufmacht, sieht er **keinen** "STEMS"-Badge oder Hinweis dass der Clip stem-paths hat. **Effekt:** das UseStemPacing-Toggle (L-K5) im Director ist blind — User aktiviert es ohne zu wissen ob Stems verfuegbar sind. Backend matched Cuts → leere/keine Stem-Triggers. Verwirrung.

---

### L-FE-14 — `LearningSessionViewModel` Memory-Leak via `MediaElement`-Events + Dialog-Close ohne Unsubscribe (MED, Memory-Leak)

**Datei:** `PBStudio.UI/Views/LearningSessionDialog.xaml.cs:8-25`

```csharp
public LearningSessionDialog(LearningSessionViewModel vm) {
    DataContext = vm;
    vm.RequestClose += () => Close();
    vm.PlayRequested += () => { … };
    vm.PauseRequested += () => { … };
    vm.RestartRequested += () => { … };
}
```

Dialog abonniert vier Event-Handler auf der VM, **subscribed nie ab**. Wenn der Dialog `Close()` wird, halten die Lambdas (mit Capture auf `this` Dialog) den Dialog am Leben → Dialog kann nicht GCd werden. Da VM transient ist (Ioc.Default.GetRequiredService → neue Instanz pro Open) hat jeder Open eine neue VM, die alten halten alte Dialogs. **Bei wiederholtem Oeffnen Memory-Wachstum.**

**Fix:** `vm.RequestClose -= …` etc. in `OnClosed` oder mit `WeakReference`-Pattern.

---

### L-FE-15 — `TimelineView.xaml.cs` `CompositionTarget.Rendering` ohne Unsubscribe (HIGH, Memory-Leak)

**Datei:** `PBStudio.UI/Views/TimelineView.xaml.cs:69`

```csharp
public TimelineView() {
    …
    CompositionTarget.Rendering += OnCompositionTargetRendering;
}
```

Niemals unsubscribed (`Unloaded`-Handler in derselben Datei laesst dieses Event stehen — Zeile 127-134). Wenn der TimelineTab geschlossen/neu-instanziert wird (z.B. nach Project-Close/Open), bleibt dieser Render-Tick auf alten View-Instanzen + alten VMs aktiv → memory leak + Lambdas die `_viewModel` halten = transient-VM bleibt im Speicher. **Pro Reopen ein VM-Leak.**

`CompositionTarget.Rendering` ist 60Hz globaler Event-Hub — pro Frame eine Iteration ueber alle subscribed Listener. Bei 10 Tab-Cycles → 10× pro Frame der gleiche Code → CPU-Drain.

**Fix:** Unsubscribe in `OnUnloaded`.

---

### L-FE-16 — `SSEClient.ListenAsync` haelt 3 separate HTTP-Pollings → 3 Reconnect-Loops, kein Single-Stream (LOW, Architektur)

**Datei:** `PBStudio.UI/Services/SSEClient.cs:74-76`

```csharp
_listenTasks.Add(Task.Run(() => ListenAsync("/events/progress", …)));
_listenTasks.Add(Task.Run(() => ListenAsync("/events/log",      …)));
_listenTasks.Add(Task.Run(() => ListenAsync("/events/gpu",      …)));
```

Drei separate Tasks, drei `HttpClient`-Connections, drei Reconnect-Schleifen. Backend hat (vermutlich, nicht im Audit-Scope) auch separate Endpoints. Wenn das Backend einen `publish_event`-Fan-out hat, koennte man `/events/all` mit `event:`-Typ pro Line verwenden — ein TCP-Connection waere sparsamer. Aber: Trennung erlaubt unabhaengige Reconnects (z.B. Log ist tot, GPU laeuft). Tradeoff, kein Bug.

**Note:** `Dispose` wartet 2s auf alle drei Tasks. Wenn nur einer haengt → 2s Blockade auf App-Exit. `Task.WaitAll([.. _listenTasks], TimeSpan.FromSeconds(2))` — `WaitAll` blockiert. Sollte `await Task.WhenAll(...)` mit timeout im async-Pattern sein (aber `Dispose` ist void).

---

### L-FE-17 — `SSEClient` Events feuern auf **Background-Threads** ohne Dispatcher-Garantie (MED, Race-Condition)

**Datei:** `PBStudio.UI/Services/SSEClient.cs:228-260`

`ProgressReceived?.Invoke(...)` etc. werden im `ListenAsync`-Background-Task ausgeloest. Subscriber sind verantwortlich, auf den UI-Thread zu marshalen. **Die meisten machen das richtig** (`Application.Current.Dispatcher.Invoke/InvokeAsync`), aber:

- `MainViewModel.OnBackendStatusChanged` (an `_bridge.StatusChanged` — auch Background) macht **kein** Dispatcher-Marshalling (Zeile 177-189) — setzt `BackendStatusText` und `BackendStatusColor` direkt. WPF erlaubt Property-Set vom Bg-Thread via ObservableObject, aber `Brushes.LimeGreen` etc. sind nicht-frozen `SolidColorBrush` → Cross-Thread-Access auf `Foreground`-Bindings kann werfen.
  - Tatsaechlich `Brushes.Red`, `Brushes.LimeGreen`, `Brushes.Gray` sind **frozen** (`Brushes` ist static + sealed mit frozen instances). Daher kein Crash. **Safe.**
- `SSEClient.IsConnected` setter (Zeile 36-47) feuert `ConnectionStateChanged` aus Background-Thread — kein Subscriber heute.

Insgesamt: Threading **safe**, aber durch `Dispatcher.Invoke` (blockierend) statt `InvokeAsync` (siehe L-FE-12) langsamer als noetig.

---

### L-FE-18 — `App.xaml.cs:OnExit` ruft `await` aber Methode ist `async void` (MED, Race auf Shutdown)

**Datei:** `PBStudio.UI/App.xaml.cs:134`

```csharp
protected override async void OnExit(ExitEventArgs e) {
    …
    await Task.WhenAll(api.SaveProjectAsync().WaitAsync(token), api.ShutdownAsync()…).WaitAsync(token);
    …
    base.OnExit(e);
}
```

`async void` in `OnExit` heisst: WPF haengt nicht auf den Task — wenn der Shutdown laenger braucht als 8s (CTS-Timeout), kehrt OnExit zurueck, aber der Hintergrund-Task laeuft weiter, danach kommt `base.OnExit(e)` aber die App-Domain ist evtl. schon abgebrochen. Generell ist Override-Async-Void der einzige Weg bei WPF-Lifecycle-Methoden, aber **das `_serviceProvider?.Dispose()` im finally nach `await ... Bridge.StopAsync()` kann uebersprungen werden** wenn der Watchdog ApplicationShutdown bereits ausgeloest hat.

**Mildernd:** `try { ... } catch { } finally { _serviceProvider?.Dispose(); }` — Dispose ist im finally. Trotzdem: bei harten Crashes (Domain-Unload) kommt's nicht zur Dispose, dann sind `_shutdownCts` und HttpClients geleakt — beim Prozess-Ende ist das aber tolerabel.

---

### L-FE-19 — `ProjectService` ruft `WeakReferenceMessenger.Default.Send(...)` von Background-Thread direkt (LOW, Konvention)

**Datei:** `PBStudio.UI/Services/ProjectService.cs:37, 50, 74, 84`

Subscriber kapseln das richtig (Director.cs:96 macht `Dispatcher.Invoke(ResetProjectState)`), aber alle anderen nehmen einfach das Message und stossen `_ = LoadAudioClipsAsync()` an — was wiederum schon innerhalb der ersten dispatch-fragmentierten Coroutine laeuft. Funktioniert, aber konzeptionell sollte ProjectService das Send ueber Dispatcher.Invoke abbilden oder die Message als "fire-and-forget vom Bg-Thread" dokumentieren.

---

### L-FE-20 — `Brain/HirnView`: `[ObservableProperty] private string _status = ""` ohne Notify zu computed View-Property "Status" - typisch (LOW)

Kein Issue, nur Hinweis: `Status` in BrainView geht direkt durch ObservableProperty. Konvention ist konsistent. **No-op finding** — als Sanity-Check gelistet.

---

### L-FE-21 — DI-Anomalie: `PythonBridgeService` registriert mit **eigenem** HttpClient (Zeile 65), umgeht den `AddHttpClient<>`-Pool (LOW, Diskussion)

**Datei:** `PBStudio.UI/Services/PythonBridgeService.cs:65, PBStudio.UI/App.xaml.cs:105`

Kommentar in App.xaml.cs:105 sagt: `"erstellt HttpClient intern (kein DI-HttpClient)"`. Bewusste Entscheidung — Lebenszyklus an Backend-Lifecycle gekoppelt. Aber `HttpClient` direkt instanziieren ist Microsoft-best-practice-Verstoss (Socket-Exhaustion bei Reuse). Hier OK weil **eine** Instanz fuer App-Lifetime, aber falls jemand spaeter Multiple-Bridges baut → Bug.

---

### L-FE-22 — `RenderConfig.cs` ist auskommentiert "DEAD CODE - Nirgends referenziert" — sollte geloescht werden (LOW)

**Datei:** `PBStudio.UI/Models/RenderConfig.cs`

```csharp
/* 
// DEAD CODE - Nirgends referenziert
namespace PBStudio.UI.Models;
…
*/
```

Datei existiert nur als Kommentar. Loeschen (oder, falls geplant, restoren + wiren).

---

### L-FE-23 — `TimelineViewModel.GeneratePreviewAsync` `cancellationToken` Param ungenutzt (LOW, API)

**Datei:** `PBStudio.UI/Services/ApiClient.cs:222-227`

```csharp
public async Task<PacingPreviewResponse?> GenerateTimelinePreviewAsync(double startSec, double duration,
    CancellationToken ct = default)
    => await PostAsync<PacingPreviewResponse>("/pacing/preview", new { start_sec = startSec, duration }).…;
```

Der `CancellationToken ct` Parameter wird ignoriert — `PostAsync` nutzt nur `_shutdownCts.Token`. Caller die Cancellation erwarten kriegen sie nicht. Aktuell ruft niemand mit Token (TimelineVM:378 ruft ohne), trotzdem inkonsistent.

---

### L-FE-24 — `SettingsView` haengt an `BackendOnline` aber wird nie zurueckgesetzt wenn Backend abstuerzt (MED)

**Datei:** `PBStudio.UI/ViewModels/SettingsViewModel.cs:236-239`

`_api.GetHealthAsync()` ruft alle Refresh-Intervalle, aber wenn Backend nach erfolgreichem Start crasht, gibt es **kein periodisches Refresh** — der User klickt manuell. Im Header der MainWindow gibt es `BackendStatusText/-Color` (MainViewModel) die via `_bridge.StatusChanged` + `_sse.ConnectionStateChanged` updaten — aber **`ConnectionStateChanged` ist nicht in MainViewModel abonniert** (Zeile 61: `_sse.ProgressReceived`, `_sse.GpuStatusReceived` — kein `ConnectionStateChanged`). SSE-Reconnect-State bleibt unsichtbar.

---

### L-FE-25 — `TimelineEntryModel.CutId` ist `[ObservableProperty]` aber `IsBrainExplainLoaded` ist normales Property — Inkonsistenz im Reactive-Pattern (LOW)

**Datei:** `PBStudio.UI/Models/TimelineEntry.cs:24, 35`

```csharp
[ObservableProperty] private int _cutId;
…
public bool IsBrainExplainLoaded { get; set; }   // Kein ObservableProperty
```

`IsBrainExplainLoaded` wird in `TimelineViewModel.OnBrainFeedbackAppliedAsync` (Zeile 595) gesetzt — aber kein Notify, also kein UI-Refresh. **Heute** kein Binding auf das Feld — nur als interner Cache-Flag genutzt. Wenn man jemals einen "Tooltip-loaded?"-Indikator in der UI bauen will, geht's lautlos kaputt.

---

### L-FE-26 — XAML-Bindings auf nicht-existierende Properties? (Audit-Sanity)

Stichproben:
- `AudioLibraryView.xaml:165` `HasCacheHash` → existiert in `AudioClipModel.cs:28` ✅
- `AudioLibraryView.xaml:178` `HasStems` → existiert ✅
- `AudioLibraryView.xaml:221` `SelectedClip.HasStems` → ✅
- `VideoLibraryView.xaml:284` `SelectedClip.MotionCategoryDisplay` → existiert in `VideoClipModel.cs:30` ✅
- `TimelineView.xaml:117` `MotionCurve` → ObservableProperty in TimelineViewModel:49 ✅
- `TimelineView.xaml:512` `PlacementTarget.DataContext.BrainExplainTooltip` → existiert in TimelineEntryModel:28 ✅
- `MainWindow.xaml:43` `CurrentProjectName` (computed, mit `OnPropertyChanged(nameof(...))` getrieben via `OnProjectChanged`) ✅

Keine offenen XAML→VM-Drifts gefunden. ✅

---

### L-FE-27 — `Audit L-TI-4 SortEntriesByTime` korrekt verdrahtet (✅)

**Datei:** `TimelineView.xaml.cs:481-484`

```csharp
if (wasDragging) { _viewModel.SortEntriesByTime(); }
```

Wird nach Drag-MouseUp aufgerufen. VM-Methode `SortEntriesByTime` (Zeile 694) sortiert die ObservableCollection in-place. `NotifyCanExecuteChanged` fuer Prev/NextCut wird gerufen. **Wiring OK.** Trim-Operations (left/right) triggern NICHT die Sortierung — bewusste Entscheidung weil Trim die `StartTime`-Reihenfolge nicht aendert (nur Dauer). ✅

---

### L-FE-28 — `Audit L-TI-2 Trim` korrekt verdrahtet (✅)

**Datei:** `TimelineView.xaml.cs:283-294, 332-381` (Trim-Origin, Trim-Left, Trim-Right)

Trim-Origin (`_dragStartX`, `_originalStartTime`, `_originalEndTime`, `_originalClipStart`) wird bei MouseDown wenn `hitPosition < 10 || > ActualWidth-10` korrekt gespeichert. MinClipDuration=0.1 enforced. Constraint Clamps fuer `newStart < 0` und `newClipStart < 0` korrekt. ✅

---

### L-FE-29 — `Audit L-M5 MotionCurve` korrekt verdrahtet (✅)

**Datei:** `TimelineViewModel.cs:191-235`

`LoadMotionCurveAsync` mit Sequence-Token (Interlocked.Increment) verhindert Race wenn User schnell durch Cuts klickt. `int.TryParse` fuer ClipId-String. `MotionCurve = null` bei Fehler. Visibility-Binding in XAML auf MotionCurve != null via `NullToVisibilityConverter`. ✅

---

### L-FE-30 — `Audit L-N2/L-N3 Cache-Hash-Badges` korrekt verdrahtet (✅)

- `AudioClipModel.HasCacheHash` → AudioLibraryView Badge ✅
- `VideoClipModel.HasCacheHash` → VideoLibraryView Badge ✅
- Property-Notification (partial method on AudioHash/VideoHash changed) ✅

---

### L-FE-31 — `Audit L-N5/L-N6 Bitrate + Encoder` korrekt verdrahtet (✅)

- `ProductionViewModel.BitrateMbps` → Slider 4-50 → in `RenderRequest` (Zeile 134) ✅
- `ProductionViewModel.Encoder` → ComboBox 5 options → null wenn "auto" ✅

---

### L-FE-32 — `Audit F4 typed Messenger records` korrekt verdrahtet (✅)

`Services/Messages/AppMessages.cs` definiert 12 typed records. Alle Sender/Subscriber stimmen ueberein. Hat aber 3 Subscribed-but-never-fired (siehe L-FE-9).

---

## 2. Matrix: Property/Command Coverage

### ViewModel → View Binding Coverage

| ViewModel | ObservableProperty count | Bound in XAML | Unbound (Dead?) |
|---|---:|---:|---:|
| MainViewModel | 5 | 5 | 0 |
| ProjectOverviewViewModel | 8 | 7 | 1 (`IsBusy` — nicht gebunden) |
| MediaIngestViewModel | 4 | 4 | 0 |
| AudioLibraryViewModel | 13 | 11 | 2 (`DurationSeconds` doppelt — VM + Model, ok) |
| VideoLibraryViewModel | 18 | 14 | 4 (`IsLoadingClips`, `IsLoadingScenes` — UI hat keinen Spinner; `CurrentStepIndex/Total` partial) |
| AnchorViewModel | 6 | 6 | 0 |
| DirectorViewModel | 25 | 18 | 7 (siehe L-FE-4) |
| TimelineViewModel | 13 | 11 | 2 (`HorizontalOffset` — siehe L-FE-5; `IsLoadingWaveform` partial) |
| ProductionViewModel | 11 | 10 | 1 (`AudioPath` indirekt via Timeline-Sync) |
| SettingsViewModel | 14 | 13 | 1 (`IsProbingFfmpeg` UI-Spinner OK) |
| BrainViewModel | 7 | 7 | 0 |
| LearningSessionViewModel | 10 | 10 | 0 |
| VramTelemetryViewModel | 14 + Card-VM | 14 | 0 |

**Total Unbound:** ~17 ObservableProperties (~10%).

### Command Coverage

Alle `[RelayCommand]` werden in XAML als Command="…Command" gebunden:
- `MainViewModel`: CreateProject/OpenProject/SaveProject/CloseProject — **nicht in MainWindow.xaml gebunden!** → siehe L-FE-33 unten.
- Andere VMs: alle Commands gebunden.

### L-FE-33 — `MainViewModel` Commands `CreateProject/OpenProject/SaveProject/CloseProject` nirgends in MainWindow.xaml verlinkt (MED, Tote Commands)

**Datei:** `MainWindow.xaml` (kein Menue/Toolbar fuer File-Operations), `MainViewModel.cs:74-142`

Die `[RelayCommand]`s sind definiert, aber MainWindow hat nur Tab-Switching + Status-Bar. Projekt-Operations passieren ueber `ProjectOverviewView` (per `RelayCommand` direkt im ProjectOverviewVM). **MainVM-Commands sind toter Duplikat-Code** — vermutlich Ueberbleibsel aus einer frueheren UI-Iteration.

---

## 3. Top 5 (Schwerste Findings)

1. **L-FE-1** — `TimelineViewModel` injiziert konkrete `ApiClient`-Klasse statt `IApiClient` → Interface-Bruch, Tests blockiert, Decorator-Pattern unmoeglich (Architektur-Hot-Spot).
2. **L-FE-2** — `IApiClient` fehlt `GetOnsetsAsync` → TimelineVM musste die Klasse direkt injizieren (Wurzel von L-FE-1). Behebung: Methode ins Interface lifteN, dann L-FE-1 nachziehen.
3. **L-FE-15** — `TimelineView.xaml.cs` abonniert `CompositionTarget.Rendering` ohne Unsubscribe → **echter** Memory-Leak + 60Hz-CPU-Drain pro VM-Reincarnation.
4. **L-FE-7** — `BrainViewModel` + `LearningSessionViewModel` ohne IDisposable + ohne `WeakReferenceMessenger.UnregisterAll` + Event-Lambdas in Dialog-CodeBehind ohne Unsubscribe → Memory-Leak pro Dialog-Open.
5. **L-FE-9** — Drei Messages (`AppShutdownMessage`, `BackendReadyMessage`, `ProjectClosingMessage`) sind **subscribed-but-never-fired** → Settings-Page-Refresh nach Backend-Start fehlt (spuerbarer Bug), VideoLib/MediaIngest haben einen toten Cleanup-Pfad.

---

## 4. Empfehlung (Priorisiert)

| Prio | Aktion | Aufwand |
|---|---|---|
| P0 | L-FE-2 (GetOnsetsAsync ins Interface) + L-FE-1 (TimelineVM → IApiClient) | 15 min |
| P0 | L-FE-15 (CompositionTarget.Rendering Unsubscribe in OnUnloaded) | 5 min |
| P0 | L-FE-7 (BrainVM/LearningSessionVM IDisposable + Unsubscribe-Pattern im Dialog) | 30 min |
| P1 | L-FE-9 (BackendReadyMessage in MainVM senden; ProjectClosingMessage in ProjectService.CloseAsync vor API-Call; AppShutdownMessage in App.OnExit) | 20 min |
| P1 | L-FE-13 (DirectorVM AudioHash/StemsPaths mappen) | 5 min |
| P1 | L-FE-33 (MainVM Tote Commands entfernen oder MainWindow Menue/Toolbar nachziehen) | 10 min |
| P2 | L-FE-4 (DirectorView: Slider fuer Snare/Hihat/MaxClipLength/OnsetSensitivity/MinClipLength nachruesten) | 30 min |
| P2 | L-FE-10 (MainVM.OnProgressReceived filtert nur render_progress/gpu_error) | 5 min |
| P2 | L-FE-24 (MainVM auf `SSEClient.ConnectionStateChanged` abonnieren) | 10 min |
| P3 | L-FE-5, L-FE-11, L-FE-22 (Dead Code entfernen) | 10 min |
| P3 | L-FE-8, L-FE-12 (ConfigureAwait/Invoke-Konsistenz, idiomatisches Refactor) | 60 min |
| P3 | L-FE-23, L-FE-25 (CancellationToken-Propagation, IsBrainExplainLoaded ObservableProperty) | 20 min |

**Geschaetzter Total-Aufwand fuer P0+P1:** ~80 Minuten Engineering + Test.

---

## 5. Findings ohne Code-Aenderung (Sanity-Checks die OK sind)

- L-FE-26 — XAML→VM Property-Drift: keine gefunden ✅
- L-FE-27 — L-TI-4 SortEntriesByTime: korrekt verdrahtet ✅
- L-FE-28 — L-TI-2 Trim: korrekt verdrahtet ✅
- L-FE-29 — L-M5 MotionCurve: korrekt verdrahtet ✅
- L-FE-30 — L-N2/L-N3 Cache-Hash-Badges: korrekt verdrahtet ✅
- L-FE-31 — L-N5/L-N6 Bitrate + Encoder: korrekt verdrahtet ✅
- L-FE-32 — F4 typed Messenger records: korrekt (bis auf L-FE-9 Subscriber-without-Sender)

**Schema-Drift Backend↔Frontend stichprobenartig geprueft:**
- `AudioClipInfo` (audio_schemas.py:13 ↔ ApiClient.cs:415): match auf Felder + snake_case-Lower JSON-Policy ✅
- `VideoClipInfo` (video_schemas.py:12 ↔ ApiClient.cs:440): match, **aber** Backend `has_video_embedding` + `embedding_dim` + `embedding_samples` + `has_embedding` Felder werden vom Frontend-Record **ignoriert** (case-insensitive Parser verwirft Unbekannte). Wenn UI das spaeter zeigen soll → Frontend-Record erweitern. Aktuell harmlos.
- `PacingConfig` (pacing_schemas.py ↔ ApiClient.cs:465): TriggerSettings hat im Backend `ClipLengthVariation`, `MaxCutInterval`, `BeatTriggerMode` — Frontend sendet defaults (1.0=0, 10.0, "all"). OK weil Defaults konvergieren, aber UI hat **keinen** Slider dafuer.
- `RenderRequest` (Backend `start_render_router` — nicht im Audit-Scope; ApiClient.cs:493): Feld `IncludeAudio`/`Encoder` — beim Audit Backend nicht gepruft, Annahme passt.

---

## 6. Zusammenfassung (Statistik)

- **Findings total:** 33 (L-FE-1 .. L-FE-33), davon
  - 4× HIGH (L-FE-1, L-FE-2, L-FE-7, L-FE-15)
  - 9× MED (L-FE-3, L-FE-4, L-FE-9, L-FE-10, L-FE-13, L-FE-14, L-FE-17, L-FE-18, L-FE-24, L-FE-33)
  - 13× LOW (L-FE-5, L-FE-6, L-FE-8, L-FE-11, L-FE-12, L-FE-16, L-FE-19, L-FE-20, L-FE-21, L-FE-22, L-FE-23, L-FE-25)
  - 7× ✅ (verifiziert OK: L-FE-26..L-FE-32)
- **Echte Crash-/Leak-Vektoren:** 2 (L-FE-15, L-FE-7).
- **Spuerbare User-Bugs (UX-Drift):** 3 (L-FE-9 Settings-Refresh-Fehlend, L-FE-13 Stem-Pacing-blind, L-FE-10 Status-Spam).
- **Dead Code:** 6 (L-FE-4, L-FE-5, L-FE-6, L-FE-11, L-FE-22, L-FE-33).
- **Architektur-Drift:** 2 (L-FE-1, L-FE-2).
- **Konvention/Polish:** restliche.

Frontend-Wiring insgesamt **solide**: alle Major-Tabs sind funktional verdrahtet, Cross-VM-Refresh via typed Messenger funktioniert. Hauptrisiken sind Memory-Leaks im Timeline-Render-Loop und im Brain/LearningSession-Lifecycle, beide mit einfachem Fix (~5-30 Minuten).

---

**Audit durchgefuehrt:** 2026-05-11 (read-only, keine Code-Aenderungen).
