using System.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// ViewModel für die Einstellungen. Verwaltet GPU-Status, VRAM-Cap-Slider,
/// kanonische FFmpeg-Runtime-Provenienz und PB_STUDIO_FORCED_VRAM
/// Env-Var. Persistenz via <see cref="ISettingsService"/> nach %APPDATA%\PBStudio\settings.json.
/// </summary>
public partial class SettingsViewModel : ObservableObject, IDisposable
{
    private const string RecommendationTask = "video_captioning";

    private readonly IApiClient _api;
    private readonly ISettingsService _settings;
    private readonly ProjectService? _projects;
    private CancellationTokenSource? _probeCts;
    private CancellationTokenSource? _vramDebounceCts;
    private CancellationTokenSource? _recommendationCts;
    private long _recommendationGeneration;
    private long _recommendationProjectGeneration;
    private bool _disposed;

    // ── GPU Status ────────────────────────────────────────────────────────
    [ObservableProperty] private string _gpuName = "Wird geladen...";
    [ObservableProperty] private double _vramTotal;
    [ObservableProperty] private double _vramUsed;
    [ObservableProperty] private double _temperature;
    [ObservableProperty] private string _driverVersion = "";
    [ObservableProperty] private string _gpuAdapterIndex = "–";
    [ObservableProperty] private string _gpuAdapterLuid = "–";
    [ObservableProperty] private string _gpuSelectionPolicy = "–";
    [ObservableProperty] private string _directmlStatus = "Wird geladen...";
    [ObservableProperty] private string _monitoringStatus = "Wird geladen...";
    [ObservableProperty] private string? _monitoringError;
    [ObservableProperty] private bool _backendOnline;

    // ── VRAM Cap (Slider, persistiert) ────────────────────────────────────
    [ObservableProperty] private int _vramLimitMb = 8192;

    // ── FFmpeg Path Picker ────────────────────────────────────────────────
    [ObservableProperty] private string _ffmpegPath = "";
    [ObservableProperty] private string? _ffmpegPathError;
    [ObservableProperty] private string? _ffmpegVersion;   // null = nicht geprüft (NullToVisibility blendet aus)
    [ObservableProperty] private string? _ffmpegProvenance;
    [ObservableProperty] private bool _isProbingFfmpeg;

    // ── Forced VRAM (Env-Var für nächsten Backend-Start) ──────────────────
    [ObservableProperty] private bool _forceVramEnabled;
    [ObservableProperty] private int _forcedVramMb = 8192;

    // ── KI-Modus (Auto-Selection-Bias fuer Vision-Modelle) ────────────────
    // Slider mit 3 Stufen: 0 = Speed, 1 = Balance, 2 = Quality. Persistiert
    // als String in settings.json::ki_mode. Default Balance.
    [ObservableProperty] private int _kiModeIndex = 1;
    [ObservableProperty] private string _kiModeLabel = "Balance";
    [ObservableProperty] private string _kiModeDescription = "Mittlere Modellgroesse - guter Kompromiss zwischen Speed und Qualitaet.";
    [ObservableProperty] private string _kiModeAutoSelectionText = "Wird beim naechsten Captioning ermittelt.";

    private static readonly string[] KiModes = { "speed", "balance", "quality" };
    public string KiMode => KiModes[Math.Clamp(KiModeIndex, 0, KiModes.Length - 1)];

    // ── UI State ──────────────────────────────────────────────────────────
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _isSaving;
    [ObservableProperty] private bool _isCleaningGpu;
    [ObservableProperty] private string _settingsFilePath = "";
    [ObservableProperty] private string? _settingsPersistenceError;

    public SettingsViewModel(IApiClient api, IDialogService dialogs)
        : this(api, dialogs, new SettingsService())
    {
    }

    /// <summary>Test-Konstruktor: erlaubt Mocken aller Dependencies.</summary>
    public SettingsViewModel(
        IApiClient api,
        IDialogService dialogs,
        ISettingsService settings,
        ProjectService? projects = null)
    {
        _api = api;
        _ = dialogs;
        _settings = settings;
        _projects = projects;
        StatusText = "Backend: Startet...";

        SettingsFilePath = _settings.ConfigFilePath;

        // 1. Persistierte Settings laden (vor allen async Calls)
        LoadPersistedSettings();

        // 2. Initiales Laden des Backend-Status
        WeakReferenceMessenger.Default.Register<BackendReadyMessage>(this, (_, _) => _ = RefreshAsync());
        WeakReferenceMessenger.Default.Register<AppShutdownMessage>(this, (_, _) => BackendOnline = false);
        WeakReferenceMessenger.Default.Register<ProjectClosingMessage>(
            this,
            (_, _) => InvalidateRecommendationForProjectChange(refresh: false));
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(
            this,
            (_, _) => InvalidateRecommendationForProjectChange(refresh: true));
        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(
            this,
            (_, _) => InvalidateRecommendationForProjectChange(refresh: true));

        _ = RefreshAsync();

        // 3. Initial-Probe falls FFmpeg-Pfad bereits gesetzt
        if (!string.IsNullOrWhiteSpace(FfmpegPath))
            _ = ProbeFfmpegAsync();
    }

    private void LoadPersistedSettings()
    {
        var loadResult = _settings.Load();
        SettingsPersistenceError = loadResult.ErrorMessage;
        var s = _settings.Current;

        PythonBridgeService.ApplyRuntimeEnvironment(s);
        FfmpegPath = s.FfmpegPath ?? "";
        VramLimitMb = s.VramCapMb > 0 ? s.VramCapMb : 8192;

        if (s.ForcedVramMb.HasValue && s.ForcedVramMb.Value > 0)
        {
            ForceVramEnabled = true;
            ForcedVramMb = s.ForcedVramMb.Value;
        }
        else
        {
            ForceVramEnabled = false;
            ForcedVramMb = 8192;
        }
        // KI-Modus: String -> Slider-Index (speed=0, balance=1, quality=2). Default balance.
        KiModeIndex = (s.KiMode ?? "balance").ToLowerInvariant() switch
        {
            "speed" => 0,
            "quality" => 2,
            _ => 1,
        };
        UpdateKiModeLabels();

        // Initiale Pfad-Validation (ohne async Probe)
        _settings.ValidateFFmpegPath(FfmpegPath, out var err);
        FfmpegPathError = err;
    }

    // Slider-Reaktion: Label + Beschreibung aktualisieren, Auto-Selection-Preview neu holen.
    partial void OnKiModeIndexChanged(int value)
    {
        UpdateKiModeLabels();
        _ = RefreshKiAutoSelectionAsync();
    }

    // T2.2: Live-VRAM-Slider Debounce (500ms) und API-Call
    partial void OnVramLimitMbChanged(int value)
    {
        var previous = _vramDebounceCts;
        var current = new CancellationTokenSource();
        _vramDebounceCts = current;
        previous?.Cancel();
        previous?.Dispose();
        _ = UpdateVramLimitAfterDelayAsync(value, current.Token);
    }

    private async Task UpdateVramLimitAfterDelayAsync(int value, CancellationToken ct)
    {
        try
        {
            await Task.Delay(500, ct);
            if (_disposed || ct.IsCancellationRequested)
                return;

            StatusText = "Aktualisiere VRAM-Limit...";
            var res = await _api.UpdateVramLimitAsync(value, ct);
            if (_disposed || ct.IsCancellationRequested)
                return;

            if (res != null)
            {
                StatusText = $"VRAM-Limit live gedrosselt auf {value} MB.";
            }
            else
            {
                StatusText = "Warnung: Live-Drosselung fehlgeschlagen. Wert liegt evtl. unter dem aktiven VRAM-Bedarf.";
            }
        }
        catch (OperationCanceledException)
        {
            // Erwartet bei schnellem Schieben oder Dispose
        }
        catch (Exception ex)
        {
            if (!_disposed && !ct.IsCancellationRequested)
                StatusText = $"Fehler beim Live-Drosseln: {ex.Message}";
        }
    }

    private void UpdateKiModeLabels()
    {
        switch (Math.Clamp(KiModeIndex, 0, 2))
        {
            case 0:
                KiModeLabel = "Speed";
                KiModeDescription = "Schnellste verfuegbare Modelle (z.B. moondream, minicpm-v). Niedrigste VRAM-Auslastung, basale Tags.";
                break;
            case 2:
                KiModeLabel = "Quality";
                KiModeDescription = "Groesstes verfuegbares Modell (z.B. llava:34b, qwen2-vl:7b). Detailreichste Captions, hoechster VRAM-Bedarf.";
                break;
            default:
                KiModeLabel = "Balance";
                KiModeDescription = "Mittlere Modellgroesse (z.B. gemma4:latest). Guter Kompromiss zwischen Speed und Qualitaet.";
                break;
        }
    }

    /// <summary>
    /// Frueh-Preview: holt vom Backend, welches Modell die Auto-Selection fuer den
    /// aktuellen KiMode aktuell waehlen wuerde. Bei Offline: leaves placeholder text.
    /// </summary>
    private async Task RefreshKiAutoSelectionAsync()
    {
        if (_disposed)
            return;

        var requestedMode = KiMode;
        var requestedProjectPath = _projects?.CurrentProjectPath;
        var requestedProjectGeneration =
            Volatile.Read(ref _recommendationProjectGeneration);
        ProjectOperationContext? projectContext = null;
        if (_projects?.HasProject == true)
        {
            try
            {
                projectContext = _projects.CaptureOperationContext();
            }
            catch (InvalidOperationException)
            {
                KiModeAutoSelectionText = "Projektwechsel läuft; Vorschau wird neu geladen.";
                return;
            }
        }

        var generation = Interlocked.Increment(ref _recommendationGeneration);
        var previous = _recommendationCts;
        var current = projectContext.HasValue
            ? CancellationTokenSource.CreateLinkedTokenSource(
                projectContext.Value.CancellationToken)
            : new CancellationTokenSource();
        _recommendationCts = current;
        previous?.Cancel();

        try
        {
            var rec = await _api.GetModelRecommendationAsync(
                RecommendationTask,
                requestedMode,
                current.Token).ConfigureAwait(true);
            if (!IsCurrentRecommendation(
                    current,
                    generation,
                    requestedMode,
                    requestedProjectPath,
                    requestedProjectGeneration,
                    projectContext))
            {
                return;
            }

            if (rec == null)
            {
                KiModeAutoSelectionText = "Backend nicht erreichbar.";
                return;
            }

            if (!string.Equals(rec.Task, RecommendationTask, StringComparison.Ordinal)
                || !string.Equals(rec.Mode, requestedMode, StringComparison.OrdinalIgnoreCase))
            {
                KiModeAutoSelectionText = "Auto-Selection-Antwort passt nicht zur Anfrage.";
                return;
            }

            if (!string.IsNullOrEmpty(rec.Model))
            {
                var provider = string.IsNullOrWhiteSpace(rec.Provider)
                    ? "Provider unbekannt"
                    : rec.Provider;
                var capabilities = rec.VerifiedCapabilities is { Count: > 0 }
                    ? string.Join(", ", rec.VerifiedCapabilities)
                    : "keine verifizierten Capabilities";
                var source = string.IsNullOrWhiteSpace(rec.SelectionSource)
                    ? "Quelle unbekannt"
                    : rec.SelectionSource;
                KiModeAutoSelectionText =
                    $"Auto-Selection: {provider}:{rec.Model} | {source} | {capabilities}.";
            }
            else
                KiModeAutoSelectionText = $"Kein Modell verfuegbar fuer {requestedMode}: {rec.Reason}";
        }
        catch (OperationCanceledException)
        {
            // Erwartet bei Modus-/Projektwechsel oder Dispose.
        }
        catch
        {
            if (IsCurrentRecommendation(
                    current,
                    generation,
                    requestedMode,
                    requestedProjectPath,
                    requestedProjectGeneration,
                    projectContext))
            {
                KiModeAutoSelectionText = "Auto-Selection-Preview fehlgeschlagen.";
            }
        }
        finally
        {
            if (ReferenceEquals(_recommendationCts, current))
                _recommendationCts = null;
            current.Dispose();
        }
    }

    private bool IsCurrentRecommendation(
        CancellationTokenSource owner,
        long generation,
        string requestedMode,
        string? requestedProjectPath,
        long requestedProjectGeneration,
        ProjectOperationContext? projectContext)
    {
        if (_disposed
            || owner.IsCancellationRequested
            || !ReferenceEquals(_recommendationCts, owner)
            || generation != Volatile.Read(ref _recommendationGeneration)
            || requestedProjectGeneration != Volatile.Read(ref _recommendationProjectGeneration)
            || !string.Equals(requestedMode, KiMode, StringComparison.Ordinal)
            || !string.Equals(
                requestedProjectPath,
                _projects?.CurrentProjectPath,
                StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        return !projectContext.HasValue
            || (_projects?.IsCurrent(projectContext.Value) == true);
    }

    private void InvalidateRecommendationForProjectChange(bool refresh)
    {
        Interlocked.Increment(ref _recommendationProjectGeneration);
        Interlocked.Increment(ref _recommendationGeneration);
        _recommendationCts?.Cancel();
        if (refresh && !_disposed)
            _ = RefreshKiAutoSelectionAsync();
    }

    // Live-Validation bei jeder Änderung des FFmpeg-Pfads
    partial void OnFfmpegPathChanged(string value)
    {
        _probeCts?.Cancel();
        _settings.ValidateFFmpegPath(value, out var err);
        FfmpegPathError = err;
        FfmpegVersion = null; // Version invalidieren bis erneut geprüft
    }

    [RelayCommand]
    private async Task ProbeFfmpegAsync()
    {
        // Re-validate first
        if (!_settings.ValidateFFmpegPath(FfmpegPath, out var err))
        {
            FfmpegPathError = err;
            FfmpegVersion = null;
            return;
        }

        if (string.IsNullOrWhiteSpace(FfmpegPath))
        {
            FfmpegVersion = null;
            return;
        }

        var previous = _probeCts;
        var current = new CancellationTokenSource();
        _probeCts = current;
        previous?.Cancel();
        var ct = current.Token;

        IsProbingFfmpeg = true;
        try
        {
            var runtime = await _settings.ProbeCanonicalFFmpegRuntimeAsync(ct).ConfigureAwait(true);
            if (ct.IsCancellationRequested) return;

            if (!string.IsNullOrWhiteSpace(runtime.RuntimePath))
                FfmpegPath = runtime.RuntimePath;
            FfmpegVersion = runtime.Version;

            if (runtime.Succeeded)
            {
                FfmpegPathError = null;
                FfmpegProvenance =
                    $"Manifest verifiziert · FFmpeg SHA-256 {runtime.Sha256} · " +
                    $"FFprobe SHA-256 {runtime.FfprobeSha256} · Quelle: {runtime.AssetSource}";
            }
            else
            {
                FfmpegProvenance = null;
                FfmpegPathError = runtime.ErrorMessage;
            }
        }
        catch (OperationCanceledException)
        {
            // Erwartet bei Re-Probe / Dispose
        }
        catch (Exception)
        {
            if (!_disposed && !ct.IsCancellationRequested)
            {
                FfmpegPathError = "Die FFmpeg-Runtime-Prüfung ist fehlgeschlagen.";
                FfmpegVersion = null;
                FfmpegProvenance = null;
            }
        }
        finally
        {
            if (ReferenceEquals(_probeCts, current))
            {
                _probeCts = null;
                if (!_disposed)
                    IsProbingFfmpeg = false;
            }
            current.Dispose();
        }
    }

    [RelayCommand]
    private async Task SaveSettingsAsync()
    {
        if (IsSaving) return;
        IsSaving = true;
        StatusText = "Speichere Einstellungen...";
        var persisted = false;

        try
        {
            FfmpegPath = PythonBridgeService.GetCanonicalFfmpegPath();

            // 1. Validierung des kanonischen FFmpeg-Pfads
            if (!_settings.ValidateFFmpegPath(FfmpegPath, out var ffErr))
            {
                FfmpegPathError = ffErr;
                StatusText = "FFmpeg-Projekt-Runtime ist ungültig.";
                return;
            }

            // 2. In-Memory-Settings updaten und persistieren
            _settings.Current.FfmpegPath = FfmpegPath ?? "";
            _settings.Current.VramCapMb = VramLimitMb;
            _settings.Current.ForcedVramMb = ForceVramEnabled && ForcedVramMb > 0
                ? ForcedVramMb
                : null;
            _settings.Current.KiMode = KiMode;
            var saveResult = _settings.Save();
            if (!saveResult.Succeeded)
            {
                SettingsPersistenceError = saveResult.ErrorMessage;
                StatusText = saveResult.ErrorMessage ?? "Einstellungen konnten nicht gespeichert werden.";
                return;
            }
            SettingsPersistenceError = null;
            persisted = true;

            // 3. Env-Vars aktualisieren (für nächsten Backend-Start)
            PythonBridgeService.ApplyRuntimeEnvironment(_settings.Current);

            // KI-Modus ins Backend synchronisieren
            var modeSyncSuccess = await _api.UpdateKiModeAsync(KiMode).ConfigureAwait(true);
            if (modeSyncSuccess)
            {
                WeakReferenceMessenger.Default.Send<KiModeChangedMessage>();
            }

            // 4. Subtle UI-feedback
            await Task.Delay(150).ConfigureAwait(true);
            if (string.IsNullOrEmpty(FfmpegPathError))
            {
                var syncHint = modeSyncSuccess ? "" : " (Backend-Sync fehlgeschlagen)";
                StatusText = "Einstellungen gespeichert" + syncHint + ": " + _settings.ConfigFilePath;
            }
        }
        catch (Exception)
        {
            StatusText = persisted
                ? "Einstellungen gespeichert, aber nicht vollständig angewendet."
                : "Einstellungen konnten nicht gespeichert werden.";
        }
        finally
        {
            IsSaving = false;
        }
    }

    [RelayCommand]
    private async Task RefreshAsync()
    {
        var health = await _api.GetHealthAsync();
        BackendOnline = health != null;

        var gpu = await _api.GetGpuStatusAsync();
        if (gpu != null)
        {
            GpuName = gpu.AdapterName ?? gpu.Name;
            GpuAdapterIndex = gpu.AdapterIndex?.ToString() ?? "–";
            GpuAdapterLuid = gpu.AdapterLuid ?? "–";
            GpuSelectionPolicy = gpu.SelectionPolicy ?? "–";
            DirectmlStatus = gpu.DirectmlActive
                ? "Aktiv auf ausgewähltem Adapter"
                : "Fehler: DirectML nicht aktiv";
            MonitoringStatus = gpu.MonitoringStatus switch
            {
                "ready" => "Bereit",
                "degraded" => "Eingeschränkt",
                "error" => "Fehler",
                _ => gpu.MonitoringStatus,
            };
            MonitoringError = string.IsNullOrWhiteSpace(gpu.MonitoringError)
                ? null
                : gpu.MonitoringError;
            VramTotal = gpu.DedicatedVramTotalMb > 0
                ? gpu.DedicatedVramTotalMb
                : gpu.VramTotalMb;
            VramUsed = gpu.VramUsedMb;
            Temperature = gpu.TemperatureC;
            DriverVersion = gpu.DriverVersion;

            // Slider-Maximum auf echte VRAM-Größe ziehen, falls bekannt
            if (gpu.VramTotalMb > 0)
            {
                var totalInt = (int)Math.Round(gpu.VramTotalMb);
                if (VramLimitMb > totalInt) VramLimitMb = totalInt;
                if (ForcedVramMb > totalInt) ForcedVramMb = totalInt;
            }
        }
        StatusText = BackendOnline ? "Backend: Online" : "Backend: Offline";

        if (BackendOnline)
            await RefreshKiAutoSelectionAsync().ConfigureAwait(true);
    }

    [RelayCommand]
    private async Task CleanupGpuAsync()
    {
        if (_disposed || IsCleaningGpu)
            return;

        IsCleaningGpu = true;
        StatusText = "VRAM aufräumen...";
        try
        {
            var result = await _api.CleanupGpuAsync().ConfigureAwait(true);
            if (_disposed)
                return;

            StatusText = result switch
            {
                null => "GPU-Cleanup fehlgeschlagen; VRAM-Zustand ist unverändert.",
                { Success: false, Error: not null } =>
                    $"GPU-Cleanup fehlgeschlagen: {result.Error}",
                { Success: false } =>
                    "GPU-Cleanup fehlgeschlagen; das Backend bestätigte keinen Erfolg.",
                { FreedMb: >= 0 } =>
                    $"GPU-Cleanup abgeschlossen ({result.FreedMb} MB gemeldet).",
                _ => "GPU-Cleanup lieferte ein ungültiges Ergebnis.",
            };
        }
        catch
        {
            if (!_disposed)
                StatusText = "GPU-Cleanup fehlgeschlagen; VRAM-Zustand ist unverändert.";
        }
        finally
        {
            if (!_disposed)
                IsCleaningGpu = false;
        }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        try { _probeCts?.Cancel(); } catch { /* ignore */ }
        _probeCts?.Dispose();
        try { _vramDebounceCts?.Cancel(); } catch { /* ignore */ }
        _vramDebounceCts?.Dispose();
        try { _recommendationCts?.Cancel(); } catch { /* ignore */ }
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }
}

