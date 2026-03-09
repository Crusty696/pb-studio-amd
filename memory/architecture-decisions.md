# Architektur-Entscheidungen — PB Studio AMD Edition
**Letzte Aktualisierung:** 2026-03-04

## ADR-001: AppState Singleton (2026-03-04)
**Problem:** 4 FastAPI Router nutzten module-level Dictionaries + Cross-Router Imports
**Entscheidung:** `backend/app_state.py` mit `AppState` Dataclass als prozessweiter Singleton
**Upgrade-Pfad:** Künftig durch `DatabaseManager`/SQLite ersetzt (ADR-003 Phase 2)
**Dateien:** `backend/app_state.py`, `backend/dependencies.py` (re-export)

## ADR-002: Pacing Router Snapshot-Pattern (2026-03-04)
**Problem:** `pacing_router.py` importierte `_audio_clips` direkt aus `audio_router`
**Entscheidung:** Beim `generate_cut_list`-Aufruf werden Snapshots aus AppState extrahiert:
  ```python
  audio_clips_snapshot = dict(state.audio_clips)
  video_clips_snapshot = dict(state.video_clips)
  cuts = await asyncio.to_thread(_run_pacing_generation, config, audio_clips_snapshot, video_clips_snapshot)
  ```
**Vorteil:** Kein Circular Import, Thread-safe Read, einfach testbar

## ADR-007: Full-Stack Audit Findings (2026-03-04)
**Status:** Bekannte Bugs dokumentiert in `FULLSTACK_AUDIT_PBStudio_AMD_2026-03-04.md`

### KRITISCH (Build-Blocker):
- **BUG-001** `App.xaml StartupUri` entfernen → WPF instanziiert vor DI → NullRef
- **BUG-002** `Resources/app.ico` fehlt → `dotnet build` schlägt fehl
- **BUG-003** `requirements.txt` fehlen `fastapi`, `uvicorn`, `pydantic-settings`

### HOCH (Funktions-Blocker):
- **BUG-004** `AudioAnalysisResult.EnergyProfile: string?` ← sollte `List<float>? EnergyCurve`
- **BUG-005** `/events/log` SSE-Queue nie befüllt (totes Feature)
- **BUG-006** `RenderRequest` C# sendet `fps`, Python-Schema hat kein `fps`-Feld
- **BUG-007** `PythonBridgeService.PythonExe` hardcoded auf `C:\Users\david\...`

### MITTEL:
- **BUG-008** `SettingsViewModel.CleanupGpuAsync()` ruft `/health` statt `/gpu/cleanup` auf
- **BUG-009** `AudioLibraryViewModel.AudioClips` nie aus Backend geladen (kein LoadAsync)
- **BUG-010** `DirectorViewModel.SelectedVideoClipIds` nie über UI befüllbar
- **BUG-011** `project_router.py` nutzt module-level `_current_project` statt AppState
- **BUG-012** `DatabaseCore.shutdown()` setzt `_instance` nicht auf None (kein Reconnect möglich)

### Verkabelung: 17/17 C# Endpoints haben Python-Pendants ✅

## ADR-003: SQLite Persistenz (BACKLOG)
**Status:** Geplant für nach WPF-Migration
**Beschreibung:** AppState wird durch `DatabaseManager` ersetzt (bestehende SQLite-DB nutzen)

## ADR-004: IApiClient Interface (2026-03-04)
**Problem:** Alle 9 ViewModels hatten harte Abhängigkeit auf `ApiClient` konkrete Klasse
**Entscheidung:** `IApiClient` Interface mit 15 Methoden extrahiert
**DI-Registrierung:**
  ```csharp
  services.AddSingleton<ApiClient>();
  services.AddSingleton<IApiClient>(sp => sp.GetRequiredService<ApiClient>());
  ```

## ADR-005: ConfigureAwait(false) Strategie (2026-03-04)
**Regel:** NUR in reinen Service-Klassen (ApiClient, PythonBridgeService, SSEClient)
**NICHT** in ViewModels — WPF braucht SynchronizationContext für ObservableProperty-Updates

## ADR-006: C# WPF Hybrid-Architektur (2026-03-01)
**Frontend:** .NET 9.0 WPF + CommunityToolkit.Mvvm + MaterialDesignThemes
**Backend:** Python FastAPI auf Port 8765 (HTTP/REST + SSE)
**Kommunikation:** HttpClient (ApiClient.cs) + SSEClient.cs
**Core:** pb_studio/core/, audio/, video/, pacing/, database/ UNVERÄNDERLICH
