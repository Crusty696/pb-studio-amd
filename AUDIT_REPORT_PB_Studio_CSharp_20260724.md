# 🔍 Code-Audit Report — PB Studio C#/WPF-UI (`PBStudio.UI`)

**Projekt:** `C:\Users\david\Documents\Pb_studio_AMD_version\PBStudio.UI`
**Fokus:** UI↔API-Verdrahtung (`ApiClient.cs` ↔ Backend-Schema), `SSEClient.cs`, ViewModels, Services, Controls
**Sprache:** C# / .NET 9.0 WPF (CommunityToolkit.Mvvm, System.Text.Json, NSwag-generierte DTOs)
**Datum:** 2026-07-24
**Methode:** Forensische Analyse durch 4 spezialisierte Auditoren + **Kreuz-Verifikation gegen das echte Backend** (backend/routers + schemas im selben Workspace) + manuelle Bestätigung der kritischen Funde
**Status:** **20 Befunde** — 3 kritisch 🔴, 10 mittel 🟡, 7 niedrig 🟢
**⚠️ Es wurde KEIN Code verändert. Dieser Bericht dokumentiert ausschließlich.**

> Ergänzung zum Python-Audit vom selben Tag (`AUDIT_REPORT_PB_Studio_20260724.md`). Nummerierung hier separat mit Präfix **C#** (C#-1 … C#-20).

---

## Umfang

Analysiert wurden **~90 C#-Dateien** (alle `Services/`, alle `ViewModels/`, alle `Models/`, `Controls/`, `Helpers/`, `Converters/`, `App`/`MainWindow`-Code-Behind sowie die generierten `ApiTypes.g.cs`). Reine View-Code-Behinds mit nur `InitializeComponent()` und die `.xaml`-Layouts wurden nicht einzeln als Befund geprüft.

**Wichtigstes positives Ergebnis (ehrlich):** Der **HTTP-Vertrag ist sauber.** Alle 56 von `ApiClient.cs` aufgerufenen Endpunkte wurden gegen die realen Backend-Routen geprüft — Methode + Pfad stimmen durchgängig überein, und jedes DTO-Feld mappt korrekt (entweder über die client-weite `JsonNamingPolicy.SnakeCaseLower` oder explizite `[JsonPropertyName("snake_case")]` auf den generierten Typen). Enum-Stringwerte (`rating`, `quality`, Stem-`model`) sind alle backend-valide. **Keine kritischen Contract-Mismatches.** Die echten Probleme liegen in **Threading (Cross-Thread-UI-Zugriff)** und **I/O-Robustheit**.

---

## Zusammenfassung

| Typ | Anzahl |
|-----|--------|
| 🔴 Kritisch (Startup-Crash / Cross-Thread-Crash / Hot-Path-I/O) | 3 |
| 🟡 Mittel (falsches Verhalten / Race / Leak / Contract-Lücke) | 10 |
| 🟢 Niedrig (Robustheit / kosmetisch / Perf) | 7 |
| **Gesamt** | **20** |
| Contract-Mismatches (Pfad/Verb/Feld) | **0 kritisch** (1 latent, siehe C#-4) |

---

## 🔴 Kritische Befunde

### ❌ FINDING C#-1 — `BrainViewModel` mutiert gebundene `ObservableCollection`s auf einem Fremd-Thread → App-Crash
**Datei:** `PBStudio.UI/ViewModels/BrainViewModel.cs:51-52` (Wirkung: 61-64, 77-93, 139-142)
**Schweregrad:** 🔴 Kritisch

```csharp
WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) => _ = RefreshStatsAsync());   // 51
WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) => ResetForProjectClose());     // 52
...
// RefreshStatsAsync: nach await OHNE erfasstem Kontext →
TopPositive.Clear(); TopPositive.Add(b);   // 86-93 auf Threadpool-Thread
```

**Problem:** `ProjectOpenedMessage`/`ProjectClosedMessage` werden ausweislich des Codes teils vom Hintergrund-Thread gesendet (vgl. Kommentar in `DirectorViewModel.cs:96` „Send() kann von Background-Thread (ProjectService)"; `MainViewModel.cs:192` sendet nach `await Task.Delay`). `RefreshStatsAsync` führt nach `await _api.BrainStatsAsync()` mangels erfasstem `SynchronizationContext` die `TopPositive.Clear()/Add()`-Aufrufe (86-93) auf dem Threadpool-Thread aus — d.h. an die HIRN-Tab-ItemsControls **gebundene** Collections werden von einem Nicht-Dispatcher-Thread verändert → `NotSupportedException` („…SourceCollection from a thread different from the Dispatcher thread"). Gleiches gilt für `ResetForProjectClose()` (61-64, gar keine Marshalling) und `LoadLearningSessionAsync` (139-142). **`BrainViewModel` ist der einzige Ausreißer** — alle anderen VMs marshallen ihre Collection-Writes über `Application.Current.Dispatcher.Invoke/InvokeAsync`.

---

### ❌ FINDING C#-2 — `FileLoggerProvider`-Konstruktor: ungeschütztes `File.WriteAllText` reißt den Start ab
**Datei:** `PBStudio.UI/Services/FileLoggerProvider.cs:16` (konstruiert in `App.xaml.cs:91`)
**Schweregrad:** 🔴 Kritisch — **von mir manuell bestätigt** (Vorbedingung: Log-Datei gesperrt/nicht schreibbar)

```csharp
public FileLoggerProvider(string filePath) {
    _filePath = filePath;
    File.WriteAllText(_filePath, $"=== PB Studio WPF Log — {DateTime.Now:...} ===...");   // Zeile 16, KEIN try/catch
}
```

**Problem:** Der Provider wird in `ConfigureServices` (App.xaml.cs:91) **synchron in `OnStartup`** erzeugt — noch bevor ein Fenster oder ein greifender `DispatcherUnhandledException`-Handler existiert. Ist `wpf_app.log` gesperrt oder der Pfad `..\..\..\..\logs` nicht schreibbar (zweite App-Instanz, Virenscanner, Read-only, Datei im Editor offen), wirft `File.WriteAllText` `IOException`/`UnauthorizedAccessException`, die aus `OnStartup` propagiert → **Prozess stirbt vor jedem Fenster**. Anders als `SettingsService.Load/Save` und `FileLogger.Log` (die try/catch nutzen) hat der Ctor keinerlei Absicherung. Ein Best-Effort-Logger darf den Start nie kippen können.

---

### ❌ FINDING C#-3 — `MainWindow` schreibt bei JEDEM Mausklick synchron in eine nie rotierte Log-Datei
**Datei:** `PBStudio.UI/MainWindow.xaml.cs:105` (Handler ab 33, registriert 29)
**Schweregrad:** 🔴 Kritisch — **von mir manuell bestätigt**

```csharp
PreviewMouseLeftButtonDown += OnPreviewMouseLeftButtonDown;   // 29
...
System.IO.File.AppendAllText(resolvedPath, fileLogLine + Environment.NewLine, Encoding.UTF8);   // 105
```

**Problem:** `OnPreviewMouseLeftButtonDown` feuert bei **jedem** Linksklick irgendwo im Fenster und schreibt jedes Mal synchron auf dem **UI-Thread** in `click_manual_wpf.log` (plus Visual-Tree-Walk + zusätzlicher `_logger`-Write). Bei schnellem Klicken oder auf langsamem/Netz-Laufwerk bzw. bei kurzzeitig gesperrter Datei blockiert der UI-Thread auf der Platte → sichtbares Ruckeln/Hänger. Zusätzlich wird `click_manual_wpf.log` — anders als `wpf_app.log` (bei Start geleert) — **nie geleert oder rotiert** und wächst über alle Sessions unbegrenzt.

---

## 🟡 Mittlere Befunde

### ⚠️ FINDING C#-4 — `/health/vram?model_id=X` wird in den Multi-Modell-DTO deserialisiert (Typ-Mismatch)
**Datei:** `ApiClient.cs:315-322` vs. `backend/routers/health_router.py:31` / `health_schemas.py:692-736`
**Schweregrad:** 🟡 Mittel (aktuell latent)

`GetVramTelemetryAsync` deserialisiert immer nach `VramHealthResponse` (`Telemetry = VramTelemetryMulti{models, summary}`). Mit `model_id`-Query liefert das Backend aber `VramHealthSingleResponse` (`telemetry` = einzelner Entry ohne `models`/`summary`). Ein Aufruf mit `modelId != null` liefert damit `Telemetry.Models/Summary == null` → `NullReferenceException` beim Dereferenzieren. **Latent**, weil der einzige heutige Aufrufer `modelId == null` nutzt (Kommentar ApiClient.cs:320) — aber die öffentliche Signatur bietet den Parameter fälschlich an.

### ⚠️ FINDING C#-5 — `VideoLibraryViewModel`: `AnalyzeSelected`/`AnalyzeAll` ohne Re-Entrancy-Guard → parallele Analyseläufe
**Datei:** `VideoLibraryViewModel.cs:567 / 614`
**Schweregrad:** 🟡 Mittel

Beide Commands setzen `IsAnalyzing=true`, prüfen es aber nie, und haben kein `CanExecute`. Da es zwei **separate** `AsyncRelayCommand` sind, greift die per-Command-Sperre nicht: „Analyze All" läuft, Klick auf „Analyze Selected" startet einen zweiten Lauf → doppelte Backend-Requests für dieselben Clips; der zuerst fertige Lauf setzt im `finally` `IsAnalyzing=false`, während der andere noch läuft (Busy-State/Progress bricht mittendrin ab). Das Schwester-Command `AnalyzeMarkedAsync` (293) guardet korrekt mit `|| IsAnalyzing`; die AudioLibrary cross-guardet alle drei — VideoLibrary bei zwei nicht.

### ⚠️ FINDING C#-6 — `TimelineViewModel.UpdateSpectralPoints` indiziert `Times`, prüft aber nur `Centroids`
**Datei:** `TimelineViewModel.cs:78 (Guard) / 98,118 (Zugriff)`
**Schweregrad:** 🟡 Mittel

Der Guard (78) prüft nur `Centroids != null && Count > 0`, die Schleife greift aber mit demselben Index auf `Times[i]` zu (98/118), Schleifenlänge = `Centroids.Count`. Liefert `/audio/spectral/{id}` `times: null` (System.Text.Json überschreibt den `= new()`-Initializer) oder eine kürzere `Times`-Liste, folgt `NullReferenceException`/`ArgumentOutOfRangeException` — und zwar innerhalb `Dispatcher.Invoke` auf dem UI-Thread → App-Crash. Feuert auch bei jedem Zoom (`OnPixelsPerSecondChanged`), nicht nur beim Laden.

### ⚠️ FINDING C#-7 — Chat-`text`-Event ersetzt den Puffer und verwirft Vor-Tool-Narration
**Datei:** `ChatViewModel.cs:121-123` vs. `chat_agent.py:618/685`
**Schweregrad:** 🟡 Mittel

Das Backend sendet `text` als **vollständige** Turn-Nachricht — einmal VOR den Tool-Calls (618) und erneut als `final_text` danach (685). Der C#-Handler ruft bei jedem `text`-Event `textBuilder.Clear()`, verwirft also die erste Nachricht („Ich schaue mal in deine Clips…") → der Nutzer sieht die Vorüberlegung nie. Reale Content-Loss bei jedem Modell, das vor einem Tool-Call narriert.

### ⚠️ FINDING C#-8 — SSE-Throttle-Dictionary `_lastProgressUpdate` wächst unbegrenzt
**Datei:** `SSEClient.cs:307/312`
**Schweregrad:** 🟡 Mittel

Keyed nach `task_id` (uuid pro Job), Einträge werden **nie** entfernt — auch nicht bei `completed`/`failed` (finale Events umgehen den Throttle-Pfad). Über eine lange Session mit vielen Render-/Analyse-Jobs wächst das Dictionary für die Prozesslebensdauer (langsames, aber echtes Memory-Leak).

### ⚠️ FINDING C#-9 — `DispatcherUnhandledException` schluckt ALLE UI-Ausnahmen und läuft in kaputtem Zustand weiter
**Datei:** `App.xaml.cs:31`
**Schweregrad:** 🟡 Mittel

`args.Handled = true;` für *jede* unbehandelte UI-Thread-Ausnahme (kein kuratiertes Allowlist). Ein NRE im Command-Handler, ein werfender Converter oder ein Cross-Thread-Zugriff wird geloggt und verschluckt — die App läuft mit halb-mutiertem State weiter, ohne Nutzerhinweis. Verstößt gegen IRON RULE 10 (keine stille kaputte Zustandsfortführung).

### ⚠️ FINDING C#-10 — State-Services feuern Change-Events auf dem Hintergrund-Thread; Cross-Thread-Crash wird verschluckt
**Datei:** `VideoLibraryStateService.cs:73` (identisch `AudioLibraryStateService.cs:73`, `TimelineStateService.cs:51`, `ProjectService.cs:36/49/62/71/84`)
**Schweregrad:** 🟡 Mittel

`RefreshCoreAsync` nutzt `...GetVideoClipsAsync().ConfigureAwait(false)`, die Continuation (71-73) läuft auf dem Threadpool und ruft `VideoClipsChanged?.Invoke(...)` off-UI-Thread. Subscriber, die eine gebundene `ObservableCollection` direkt ändern, werfen `InvalidOperationException` — die aber im umgebenden `try` (catch 80) als bloße Warnung gefangen wird und `RefreshCoreAsync` `null` zurückgibt: der Refresh meldet still Fehlschlag, obwohl `CurrentVideoClips` bereits befüllt war → Bibliothek erscheint leer/fehlerhaft.

### ⚠️ FINDING C#-11 — `WaveformRenderer`/`DepthRenderer`: CollectionChanged-Abo leakt das Control
**Datei:** `Controls/WaveformRenderer.cs:57` (identisch `DepthRenderer.cs:59`)
**Schweregrad:** 🟡 Mittel

`newCol.CollectionChanged += renderer.OnBarsCollectionChanged;` — die gebundene Collection gehört meist einem langlebigen (tab-gecachten) ViewModel. Wird die View aus dem Baum entfernt (Tab/Fenster zu), ändert sich der DP-Wert nicht, der `-=`-Pfad läuft nie → die Collection hält eine starke Referenz auf den Renderer, der (samt Visual-Subtree) nie GC'd wird. Klassischer WPF-Managed-Leak über Open/Close-Zyklen.

### ⚠️ FINDING C#-12 — `CachedTabControl`: erneutes `OnApplyTemplate` verwaist gecachten Inhalt → leere Tabs
**Datei:** `Controls/CachedTabControl.cs:44` (Cleanup-Lücke 129/150)
**Schweregrad:** 🟡 Mittel

Bei Laufzeit-Template/Theme-Wechsel ruft WPF `OnApplyTemplate` erneut; Zeile 44 legt ein frisches leeres `Grid` an, aber `_cachedPresenters` verweist noch auf die alten Presenter im detachten Grid. `EnsureAllTabsCached` überspringt bereits gecachte Tabs (129) und hat `tabItem.Content=null` (150) gesetzt → alle Tabs rendern danach leer. Zusätzlich: entfernte Tabs werden nie aus `_cachedPresenters`/Grid bereinigt (Leak bei dynamischen Tab-Sets). Annahme „`OnApplyTemplate` genau einmal, `Items` schrumpft nie" ist nicht erzwungen.

### ⚠️ FINDING C#-13 — `SnapEngine`: Division durch `_pixelsPerSecond == 0` ergibt unendliche Snap-Schwelle
**Datei:** `Helpers/SnapEngine.cs:34`
**Schweregrad:** 🟡 Mittel

`double timeThreshold = _pixelThreshold / _pixelsPerSecond;` — bei `_pixelsPerSecond == 0` (Timeline noch nicht gelayoutet / Zoom uninitialisiert) → `PositiveInfinity`. Dann erfüllt **jeder** Snap-Punkt `Distance <= timeThreshold`, das Dragging snappt wahllos zum nächstgelegenen aller Punkte statt deaktiviert zu sein. Kein Guard gegen 0/negativ.

---

## 🟢 Niedrige Befunde

### FINDING C#-14 — `llm_status`-Status `unavailable`/`idle` fallen auf grünes „Bereit" durch
`ViewModels/MainViewModel.cs:249-268` behandelt nur `loading/active/failed`; das Backend emittiert zusätzlich `unavailable` (video_router.py:1060) und `idle` (1117/1135). Fehlt Moondream-ONNX → Widget zeigt fälschlich „Bereit" (grau) statt „nicht verfügbar". Kosmetische Contract-Lücke. 🟢

### FINDING C#-15 — `gpu_error` wird als normales Progress-Event behandelt
`backend/dependencies.py:110` sendet `gpu_error` mit `message`/`task` (kein `error`/`status`/`percent`). `SSEClient.cs:281-336` ordnet es der Progress-Gruppe zu, `Error` bleibt leer → ein GPU-Task-Timeout erscheint nur als flüchtige Statuszeile, nie als Fehlerzustand. 🟢

### FINDING C#-16 — 20-Minuten-`HttpClient.Timeout` begrenzt auch die SSE-Streams
`ApiClient.cs:30` — der geteilte Client (Timeout 20 min) wird auch für `SendChatMessageAsync`/`PullModelAsync` (Streaming, `ResponseHeadersRead`) genutzt; ein Stream > 20 min wird mitten im Lesen abgebrochen. Geringes Risiko. 🟢

### FINDING C#-17 — `ApiClient` transient via `AddHttpClient` registriert, dann als Singleton gecached
`App.xaml.cs:99/108` — `AddHttpClient<ApiClient>` (transient) + `AddSingleton<IApiClient>(...)`. Wer den konkreten `ApiClient` (statt `IApiClient`) auflöst, bekommt eine frische Transient-Instanz. Für localhost harmlos (Handler factory-pooled), aber ein Lifetime-Smell. 🟢

### FINDING C#-18 — `SettingsViewModel`: `ConfigureAwait(true)` innerhalb `Task.Run` kehrt nicht zum UI-Thread zurück
`ViewModels/SettingsViewModel.cs:146` — `Task.Run` hat keinen `SynchronizationContext`, daher erfasst `ConfigureAwait(true)` nichts; die Continuation (StatusText-Writes 154-166) läuft auf dem Threadpool. Nur Scalar-Properties → kein Hard-Crash heute, aber latenter Threading-Defekt/Fehlnutzung. 🟢

### FINDING C#-19 — `MainViewModel.OnBackendStatusChanged` mutiert UI-State ohne Dispatcher-Marshalling
`ViewModels/MainViewModel.cs:211` — setzt `BackendStatusText/Color` und startet `InitializeAsync()` direkt aus dem `_bridge.StatusChanged`-Event (kann off-UI-Thread feuern). Nur Scalars → WPF marshallt, kein Crash, aber inkonsistent zum sonstigen Dispatcher-Muster der Klasse. 🟢

### FINDING C#-20 — `RulerRenderer`: pro Tick neues `DrawingVisual` nur zum DPI-Lesen + ungenutztes Feld
`Helpers/RulerRenderer.cs:43` — `VisualTreeHelper.GetDpi(new DrawingVisual()).PixelsPerDip` allokiert pro Ruler-Tick ein Wegwerf-Visual (GC-Churn auf heißem Redraw-Pfad); `_drawingVisual` (12) ist ungenutzt. Kein Korrektheitsfehler. 🟢

---

## Ausführungs-Log

```
4 forensische C#-Auditoren, je ein Cluster:
  1) ApiClient/IApiClient/PythonBridge/ApiTypes.g.cs  ↔  KREUZ-CHECK gegen backend/routers + schemas
       → 56/56 Endpunkte Methode+Pfad korrekt; alle DTO-Felder korrekt gemappt; 0 kritische Mismatches
  2) SSEClient + Event-Consumer          ↔  KREUZ-CHECK gegen events_router / publish_event
       → Line-Parsing/Reconnect/Backoff/Dispatcher korrekt; Event-Namen matchen
  3) 15 ViewModels (Threading/Async/MVVM)
  4) Services + Controls + Helpers + App/MainWindow
Manuelle Verifikation: C#-2 (FileLoggerProvider-Ctor + Aufrufkontext), C#-3 (Klick-Handler)
Keine echten UI-Thread-Deadlocks (.Result/.Wait/.GetAwaiter().GetResult()) gefunden
  — die zwei .Result in TimelineViewModel:277/298 laufen NACH await Task.WhenAll (Tasks fertig) → safe
```

---

## Selbst-Überprüfung

- [x] Alle logik-tragenden C#-Dateien (Services, ViewModels, Models, Controls, Helpers, App/MainWindow, generierte DTOs) analysiert
- [x] **HTTP-/SSE-Vertrag gegen das echte Backend verifiziert** (nicht geraten) — Pfade, Verben, JSON-Feldnamen, Enum-Werte
- [x] Jeder Befund mit exakter Datei- und Zeilenangabe, Code-Zitat und konkretem Fehlerszenario
- [x] Kritische Funde manuell bestätigt (C#-2, C#-3); C#-1/C#-6 durch Muster-Kontrast zu anderen VMs belegt
- [x] Falsch-Positive ausgeschlossen (die zwei `.Result` sind nach `WhenAll` safe; `VramTelemetryViewModel` pollt REST, ist kein SSE-Consumer)
- [x] Bericht ehrlich und vollständig — **kein Code verändert**

**Kritische Reflexion / Grenzen:**

1. **Positiv, nicht kaschiert:** Der API-Contract ist tatsächlich sauber — die häufigste Fehlerquelle in solchen Hybrid-Apps (snake_case↔PascalCase-Mismatch, Pfad-Typos) existiert hier nicht. Die Schwerpunkte sind Threading und I/O-Robustheit.
2. **WPF-Laufzeit nicht ausführbar:** Der Analyse-Container ist Linux ohne WPF/.NET-Desktop-Runtime — die Cross-Thread-Crashes (C#-1, C#-6, C#-10) und der Startup-Crash (C#-2) sind durch Code-Lesen + Kontext belegt, aber nicht dynamisch reproduziert. Ein `dotnet build` + Start auf dem Zielrechner mit einem hintergrund-gesendeten `ProjectOpenedMessage` würde C#-1 sofort zeigen.
3. **Severity-Kontext:** C#-2 crasht nur, wenn die Log-Datei gesperrt/nicht schreibbar ist (zweite Instanz, AV, Read-only) — dann aber hart und vor jedem Fenster. C#-1 crasht, sobald ein Projekt-Event aus einem Hintergrund-Thread kommt (im Code belegter Pfad).
4. **Nicht einzeln geprüft:** reine `*.xaml`-Layouts und triviale `*.xaml.cs`-Code-Behinds (nur `InitializeComponent`). XAML-Binding-Pfad-Tippfehler (die still ins Leere binden) wären ein sinnvoller nächster Schritt, erfordern aber das Gegenlesen jedes `{Binding}` gegen die VM-Properties.

---

*Erstellt durch Code-Auditor (4 forensische Auditoren + Backend-Kreuzverifikation + manuelle Bestätigung). Es wurden keine Dateien verändert.*
