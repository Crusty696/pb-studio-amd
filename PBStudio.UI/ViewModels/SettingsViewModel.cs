using System.Threading;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// ViewModel für die Einstellungen. Verwaltet GPU-Status, VRAM-Cap-Slider,
/// FFmpeg-Pfad-Picker (mit Validation + Version-Probe) und PB_STUDIO_FORCED_VRAM
/// Env-Var. Persistenz via <see cref="ISettingsService"/> nach %APPDATA%\PBStudio\settings.json.
/// </summary>
public partial class SettingsViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly IDialogService _dialogs;
    private readonly ISettingsService _settings;
    private CancellationTokenSource? _probeCts;
    private bool _disposed;

    // ── GPU Status ────────────────────────────────────────────────────────
    [ObservableProperty] private string _gpuName = "Wird geladen...";
    [ObservableProperty] private double _vramTotal;
    [ObservableProperty] private double _vramUsed;
    [ObservableProperty] private double _temperature;
    [ObservableProperty] private string _driverVersion = "";
    [ObservableProperty] private bool _backendOnline;

    // ── VRAM Cap (Slider, persistiert) ────────────────────────────────────
    [ObservableProperty] private int _vramLimitMb = 8192;

    // ── FFmpeg Path Picker ────────────────────────────────────────────────
    [ObservableProperty] private string _ffmpegPath = "";
    [ObservableProperty] private string? _ffmpegPathError;
    [ObservableProperty] private string? _ffmpegVersion;   // null = nicht geprüft (NullToVisibility blendet aus)
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
    [ObservableProperty] private string _settingsFilePath = "";

    public SettingsViewModel(IApiClient api, IDialogService dialogs)
        : this(api, dialogs, new SettingsService())
    {
    }

    /// <summary>Test-Konstruktor: erlaubt Mocken aller Dependencies.</summary>
    public SettingsViewModel(IApiClient api, IDialogService dialogs, ISettingsService settings)
    {
        _api = api;
        _dialogs = dialogs;
        _settings = settings;
        StatusText = "Backend: Startet...";

        SettingsFilePath = _settings.ConfigFilePath;

        // 1. Persistierte Settings laden (vor allen async Calls)
        LoadPersistedSettings();

        // 2. Initiales Laden des Backend-Status
        WeakReferenceMessenger.Default.Register<BackendReadyMessage>(this, (_, _) => _ = RefreshAsync());
        WeakReferenceMessenger.Default.Register<AppShutdownMessage>(this, (_, _) => BackendOnline = false);

        _ = RefreshAsync();

        // 3. Initial-Probe falls FFmpeg-Pfad bereits gesetzt
        if (!string.IsNullOrWhiteSpace(FfmpegPath))
            _ = ProbeFfmpegAsync();
    }

    private void LoadPersistedSettings()
    {
        _settings.Load();
        var s = _settings.Current;

        FfmpegPath = s.FfmpegPath ?? "";
        VramLimitMb = s.VramCapMb > 0 ? s.VramCapMb : 8192;

        // FFmpeg-Pfad sofort als Env-Var setzen, damit Backend beim ERSTEN Start
        // den persistierten Pfad nutzt (analog SetForcedVramEnvVar unten).
        PythonBridgeService.SetFfmpegPathEnvVar(FfmpegPath);

        if (s.ForcedVramMb.HasValue && s.ForcedVramMb.Value > 0)
        {
            ForceVramEnabled = true;
            ForcedVramMb = s.ForcedVramMb.Value;
            // Setze sofort die Env-Var beim App-Start, damit ein
            // Re-Start des Backends den persistierten Wert nutzt.
            PythonBridgeService.SetForcedVramEnvVar(s.ForcedVramMb.Value);
        }
        else
        {
            ForceVramEnabled = false;
            ForcedVramMb = 8192;
            PythonBridgeService.SetForcedVramEnvVar(null);
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
        try
        {
            var rec = await _api.GetModelRecommendationAsync("video_captioning", KiMode).ConfigureAwait(true);
            if (rec == null)
            {
                KiModeAutoSelectionText = "Backend nicht erreichbar.";
                return;
            }
            if (!string.IsNullOrEmpty(rec.Model))
                KiModeAutoSelectionText = $"Aktuell wuerde Auto-Selection: '{rec.Model}' waehlen.";
            else
                KiModeAutoSelectionText = $"Kein Modell verfuegbar fuer {KiMode}: {rec.Reason}";
        }
        catch
        {
            KiModeAutoSelectionText = "Auto-Selection-Preview fehlgeschlagen.";
        }
    }

    // Live-Validation bei jeder Änderung des FFmpeg-Pfads
    partial void OnFfmpegPathChanged(string value)
    {
        _settings.ValidateFFmpegPath(value, out var err);
        FfmpegPathError = err;
        FfmpegVersion = null; // Version invalidieren bis erneut geprüft
    }

    [RelayCommand]
    private void BrowseFfmpeg()
    {
        var initial = !string.IsNullOrWhiteSpace(FfmpegPath) && System.IO.File.Exists(FfmpegPath)
            ? System.IO.Path.GetDirectoryName(FfmpegPath)
            : null;

        var picked = _dialogs.OpenFile(
            title: "FFmpeg-Executable auswählen",
            filter: "FFmpeg Executable (ffmpeg.exe)|ffmpeg.exe|Alle Dateien (*.*)|*.*",
            initialDirectory: initial);

        if (string.IsNullOrEmpty(picked))
            return;

        FfmpegPath = picked;
        _ = ProbeFfmpegAsync();
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

        // Cancel laufende Probe
        _probeCts?.Cancel();
        _probeCts = new CancellationTokenSource();
        var ct = _probeCts.Token;

        IsProbingFfmpeg = true;
        try
        {
            var version = await _settings.ProbeFFmpegVersionAsync(FfmpegPath, ct).ConfigureAwait(true);
            if (ct.IsCancellationRequested) return;

            if (!string.IsNullOrEmpty(version))
            {
                FfmpegVersion = version;
                FfmpegPathError = null;
            }
            else
            {
                FfmpegVersion = null;
                FfmpegPathError = "Version konnte nicht ermittelt werden.";
            }
        }
        catch (OperationCanceledException)
        {
            // Erwartet bei Re-Probe / Dispose
        }
        catch (Exception ex)
        {
            FfmpegPathError = "Probe fehlgeschlagen: " + ex.Message;
            FfmpegVersion = null;
        }
        finally
        {
            IsProbingFfmpeg = false;
        }
    }

    [RelayCommand]
    private async Task SaveSettingsAsync()
    {
        if (IsSaving) return;
        IsSaving = true;
        StatusText = "Speichere Einstellungen...";

        try
        {
            // 1. Validierung FFmpeg-Pfad - kein hard-stop, nur Hinweis
            if (!_settings.ValidateFFmpegPath(FfmpegPath, out var ffErr))
            {
                FfmpegPathError = ffErr;
                StatusText = "Warnung: FFmpeg-Pfad ungültig - andere Settings wurden gespeichert.";
            }

            // 2. In-Memory-Settings updaten und persistieren
            _settings.Current.FfmpegPath = FfmpegPath ?? "";
            _settings.Current.VramCapMb = VramLimitMb;
            _settings.Current.ForcedVramMb = ForceVramEnabled && ForcedVramMb > 0
                ? ForcedVramMb
                : null;
            _settings.Current.KiMode = KiMode;
            _settings.Save();

            // 3. Env-Vars aktualisieren (für nächsten Backend-Start)
            PythonBridgeService.SetForcedVramEnvVar(_settings.Current.ForcedVramMb);
            PythonBridgeService.SetFfmpegPathEnvVar(_settings.Current.FfmpegPath);

            // 4. Subtle UI-feedback
            await Task.Delay(150).ConfigureAwait(true);
            if (string.IsNullOrEmpty(FfmpegPathError))
                StatusText = "Einstellungen gespeichert: " + _settings.ConfigFilePath;
        }
        catch (Exception ex)
        {
            StatusText = "Fehler beim Speichern: " + ex.Message;
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
            GpuName = gpu.Name;
            VramTotal = gpu.VramTotalMb;
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
        StatusText = "VRAM aufräumen...";
        await _api.CleanupGpuAsync();
        StatusText = "VRAM aufgeräumt";
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        try { _probeCts?.Cancel(); } catch { /* ignore */ }
        _probeCts?.Dispose();
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }
}
