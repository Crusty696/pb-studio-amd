using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Win32;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Audio-Bibliothek.</summary>
public partial class AudioLibraryViewModel : ObservableObject, IDisposable
{
    private bool _disposed;
    private readonly IApiClient _api;
    private readonly AudioLibraryStateService _audioLibraryState;
    private readonly SSEClient _sseClient;
    private readonly IDialogService _dialogService;
    private readonly ProjectService _projectService;

    [ObservableProperty] private AudioClipModel? _selectedClip;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _isAnalyzing;
    [ObservableProperty] private bool _isSeparating;
    [ObservableProperty] private double _analysisProgress;
    [ObservableProperty] private double _bpm;
    [ObservableProperty] private int _beatCount;
    [ObservableProperty] private string _key = "";
    // Beatgrid als Regel (Anker + Tempo), getrennt von der Beat-Zeitmarkenliste.
    // Der Wert stammt aus einer eigenen Schaetzung ohne den 120-BPM-Prior von
    // librosa; an 127 Fenstern gemessen trifft sie das Tempo in 48,8 % der
    // Faelle gegen 37,0 % des bisherigen Pfads, und das Raster sitzt in 100 %
    // der Fenster besser. Sie ERSETZT die BPM-Anzeige bewusst nicht - dafuer
    // ist die Trefferquote noch zu niedrig -, sondern steht daneben.
    [ObservableProperty] private string _beatGridText = "";
    [ObservableProperty] private string _beatGridStatus = "";
    [ObservableProperty] private double _durationSeconds;
    [ObservableProperty] private bool _isDeleting;
    [ObservableProperty] private string _currentStep = "";
    [ObservableProperty] private bool _isImporting;
    [ObservableProperty] private double _importProgress;
    private int _currentImportFileIdx;
    private int _totalImportFiles;
    private int? _activeAnalysisClipId;
    private int? _activeStemClipId;

    public ObservableCollection<AudioClipModel> AudioClips { get; } = [];
    public ObservableCollection<AudioClipModel> SelectedClips { get; } = [];

    public AudioLibraryViewModel(
        IApiClient api,
        AudioLibraryStateService audioLibraryState,
        SSEClient sseClient,
        IDialogService dialogService,
        ProjectService projectService)
    {
        _api = api;
        _audioLibraryState = audioLibraryState;
        _sseClient = sseClient;
        _dialogService = dialogService;
        _projectService = projectService;

        _sseClient.ProgressReceived += OnSseProgressReceived;
        _projectService.ProjectTransitionStarted += OnProjectTransitionStarted;

        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) => _ = LoadAudioClipsAsync());
        WeakReferenceMessenger.Default.Register<AudioImportedMessage>(this, (_, _) => _ = LoadAudioClipsAsync());
        WeakReferenceMessenger.Default.Register<AudioLibraryRefreshMessage>(this, (_, _) => _ = LoadAudioClipsAsync());
        WeakReferenceMessenger.Default.Register<MediaLibraryRefreshMessage>(this, (_, _) => _ = LoadAudioClipsAsync());
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) =>
            System.Windows.Application.Current.Dispatcher.Invoke(ResetProjectState));
    }

    private void OnSseProgressReceived(object? sender, ProgressEventArgs e)
    {
        var isActiveAnalysis = e.EventType == "analysis_progress"
            && IsAnalyzing
            && IsEventForClip(e, _activeAnalysisClipId);
        var isActiveStem = e.EventType == "stem_progress"
            && IsSeparating
            && IsEventForClip(e, _activeStemClipId);
        if (isActiveAnalysis || isActiveStem)
        {
            Application.Current.Dispatcher.Invoke(() =>
            {
                StatusText = e.Message;
                if (e.Percent >= 0)
                    AnalysisProgress = e.Percent;
                if (!string.IsNullOrEmpty(e.Step))
                    CurrentStep = e.Step;
            });
        }
        else if (e.EventType == "import_progress" && IsImporting)
        {
            // Backend liefert 0..100 fuer aktuelles File. VM mappt auf overall:
            // overall = ((file_idx-1) + per_file/100) / total * 100
            Application.Current.Dispatcher.Invoke(() =>
            {
                StatusText = e.Message;
                if (e.Percent >= 0 && _totalImportFiles > 0)
                {
                    var basePct = (_currentImportFileIdx - 1) * 100.0 / _totalImportFiles;
                    var perFileFraction = e.Percent / 100.0;
                    ImportProgress = basePct + perFileFraction * (100.0 / _totalImportFiles);
                }
            });
        }
    }

    private static bool IsEventForClip(ProgressEventArgs e, int? activeClipId)
    {
        if (!activeClipId.HasValue)
            return false;
        if (e.ClipId > 0)
            return e.ClipId == activeClipId.Value;
        return int.TryParse(e.TaskId, out var taskClipId)
            && taskClipId == activeClipId.Value;
    }

    [RelayCommand]
    private async Task DeleteSelectedAsync()
    {
        if (SelectedClips.Count == 0 || IsDeleting) return;
        var clips = SelectedClips.ToList();
        var confirmationMessage = clips.Count == 1
            ? $"Audio-Clip \"{clips[0].Name}\" (ID {clips[0].Id}) dauerhaft löschen?"
            : $"{clips.Count} ausgewählte Audio-Clips dauerhaft löschen?";
        if (!_dialogService.ConfirmDestructiveAction("Audio-Clips löschen", confirmationMessage))
            return;

        ProjectOperationContext projectContext;
        try
        {
            projectContext = _projectService.CaptureOperationContext();
        }
        catch (InvalidOperationException)
        {
            StatusText = "Löschen nicht gestartet: kein stabiler Projektkontext.";
            return;
        }

        IsDeleting = true;
        try
        {
            var ids = clips.Select(c => c.Id).ToList();
            StatusText = $"Loesche {ids.Count} Audio-Clips...";
            var resp = ids.Count == 1
                ? await _api.DeleteAudioClipAsync(ids[0], projectContext.CancellationToken)
                : await _api.DeleteAudioClipsBatchAsync(ids, projectContext.CancellationToken);
            if (!_projectService.IsCurrent(projectContext))
                return;
            if (resp != null)
            {
                StatusText = $"{resp.DeletedCount} Audio-Clips geloescht.";
                WeakReferenceMessenger.Default.Send(new AudioLibraryRefreshMessage());
                WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
            }
            else StatusText = "Delete fehlgeschlagen.";
        }
        catch (Exception ex)
        {
            if (_projectService.IsCurrent(projectContext))
                StatusText = $"Löschen fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            if (_projectService.IsCurrent(projectContext))
                IsDeleting = false;
        }
    }

    [RelayCommand]
    private async Task DeleteAllAsync()
    {
        if (AudioClips.Count == 0 || IsDeleting) return;
        var clips = AudioClips.ToList();
        if (!_dialogService.ConfirmDestructiveAction(
                "Alle Audio-Clips löschen",
                $"ALLE {clips.Count} Audio-Clips dauerhaft löschen?"))
        {
            return;
        }

        ProjectOperationContext projectContext;
        try
        {
            projectContext = _projectService.CaptureOperationContext();
        }
        catch (InvalidOperationException)
        {
            StatusText = "Löschen nicht gestartet: kein stabiler Projektkontext.";
            return;
        }

        IsDeleting = true;
        try
        {
            var ids = clips.Select(c => c.Id).ToList();
            StatusText = $"Loesche ALLE {ids.Count} Audio-Clips...";
            var resp = await _api.DeleteAudioClipsBatchAsync(
                ids,
                projectContext.CancellationToken);
            if (!_projectService.IsCurrent(projectContext))
                return;
            if (resp != null)
            {
                StatusText = $"{resp.DeletedCount} Audio-Clips geloescht.";
                WeakReferenceMessenger.Default.Send(new AudioLibraryRefreshMessage());
                WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
            }
            else StatusText = "Delete-All fehlgeschlagen.";
        }
        catch (Exception ex)
        {
            if (_projectService.IsCurrent(projectContext))
                StatusText = $"Löschen fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            if (_projectService.IsCurrent(projectContext))
                IsDeleting = false;
        }
    }


    /// <summary>Wird vom View aufgerufen wenn ListBox-Selection aendert (CanExecute fuer Delete).</summary>
    public void UpdateSelectedClips(System.Collections.IList selectedItems)
    {
        SelectedClips.Clear();
        foreach (var o in selectedItems)
            if (o is AudioClipModel m) SelectedClips.Add(m);
        DeleteSelectedCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedClipChanged(AudioClipModel? value)
    {
        if (value == null) return;
        Bpm = value.Bpm;
        BeatCount = value.BeatCount;
        Key = value.Key;
        DurationSeconds = value.DurationSeconds;
        AnalyzeSelectedCommand.NotifyCanExecuteChanged();
    }

    partial void OnIsAnalyzingChanged(bool value)
    {
        AnalyzeSelectedCommand.NotifyCanExecuteChanged();
        AnalyzeAllCommand.NotifyCanExecuteChanged();
    }

    [RelayCommand]
    private async Task ImportAudioAsync()
    {
        var files = _dialogService.OpenFiles(
            "Audio-Dateien zur Bibliothek hinzufügen",
            "Audio-Dateien|*.mp3;*.wav;*.flac;*.ogg;*.m4a;*.aac;*.aiff;*.aif|Alle Dateien|*.*"
        );

        if (files.Count == 0) return;

        await ProcessAudioImportAsync(files);
    }

    [RelayCommand]
    private async Task ImportFolderAsync()
    {
        var folder = _dialogService.OpenFolder("Audio-Ordner importieren");
        if (string.IsNullOrEmpty(folder)) return;

        StatusText = $"Scanne Ordner: {folder}...";
        var supported = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".aiff", ".aif"
        };

        try
        {
            var files = Directory.GetFiles(folder, "*.*", SearchOption.AllDirectories)
                .Where(f => supported.Contains(Path.GetExtension(f)))
                .ToList();

            if (files.Count == 0)
            {
                StatusText = "Keine unterstützten Audio-Dateien im Ordner gefunden.";
                return;
            }

            await ProcessAudioImportAsync(files);
        }
        catch (Exception ex)
        {
            StatusText = "Fehler beim Scannen des Ordners: " + ex.Message;
        }
    }

    private async Task ProcessAudioImportAsync(List<string> files)
    {
        IsImporting = true;
        // Wichtig: NICHT IsAnalyzing setzen waehrend Import - sonst beide Bars sichtbar.
        ImportProgress = 0.01;  // sichtbarer Start
        CurrentStep = "";
        StatusText = $"Importiere {files.Count} Dateien...";
        await Task.Delay(120).ConfigureAwait(true);  // UI render bevor Schleife

        var imported = 0;
        var total = files.Count;
        _totalImportFiles = total;
        try
        {
            for (int i = 0; i < total; i++)
            {
                var file = files[i];
                _currentImportFileIdx = i + 1;
                StatusText = $"Importiere {i + 1}/{total}: {System.IO.Path.GetFileName(file)}";
                // Backend emittiert per-byte hash-progress 0..100 fuer dieses File.
                // OnSseProgressReceived mappt auf overall ((idx-1)+pct/100)/total*100.
                ImportProgress = i * 100.0 / total;  // base position
                var result = await _api.ImportAudioAsync(file);
                if (result != null) imported++;
                ImportProgress = (i + 1) * 100.0 / total;
            }
            ImportProgress = 100.0;
            await Task.Delay(450).ConfigureAwait(true);

            if (imported > 0)
            {
                StatusText = $"{imported} Audio-Dateien erfolgreich importiert";
                await LoadAudioClipsAsync();
                // Cross-VM refresh: Director, MediaIngest, ProjectOverview hoeren auf diese Records
                WeakReferenceMessenger.Default.Send(new AudioImportedMessage());
                WeakReferenceMessenger.Default.Send(new AudioLibraryRefreshMessage());
                WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
            }
            else
            {
                StatusText = "Keine Dateien importiert.";
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Fehler beim Import: {ex.Message}";
        }
        finally
        {
            IsImporting = false;
        }
    }

    [RelayCommand]
    private async Task LoadAudioClipsAsync()
    {
        var previousId = SelectedClip?.Id;
        var clips = await _audioLibraryState.RefreshAsync();
        if (clips != null)
        {
            await Application.Current.Dispatcher.InvokeAsync(() =>
            {
                AudioClips.Clear();
                foreach (var clipInfo in clips)
                {
                    AudioClips.Add(new AudioClipModel
                    {
                        Id = clipInfo.Id,
                        Name = clipInfo.Name,
                        Path = clipInfo.Path,
                        DurationSeconds = clipInfo.DurationSeconds,
                        SampleRate = clipInfo.SampleRate,
                        Channels = clipInfo.Channels,
                        Format = clipInfo.Format,
                        Bpm = clipInfo.Bpm,
                        Key = clipInfo.Key ?? "",
                        BeatCount = clipInfo.BeatCount,
                        IsAnalyzed = clipInfo.IsAnalyzed,
                        AnalysisStatus = clipInfo.AnalysisStatus,
                        StageErrors = clipInfo.StageErrors,
                        // L-N2: Content-Hash fuer CACHED-Badge auf der Card.
                        AudioHash = clipInfo.AudioHash,
                        // L-N4: Stem-Paths fuer STEMS-Badge + Open-Folder-Button.
                        StemsPaths = clipInfo.StemsPaths,
                    });
                }
                if (previousId.HasValue)
                    SelectedClip = AudioClips.FirstOrDefault(c => c.Id == previousId.Value);
                StatusText = $"{clips.Count} Audio-Clips geladen";
                AnalyzeAllCommand.NotifyCanExecuteChanged();
            });
        }
        else
        {
            StatusText = "Audio-Clips laden fehlgeschlagen";
        }
    }

    [RelayCommand]
    private void SelectAll()
    {
        // Markiert ALLE Clips fuer Multi-Operation (Delete-Selected etc.).
        // Befuellt SelectedClips-Collection, View pickt das via behavior auf.
        SelectedClips.Clear();
        foreach (var c in AudioClips) SelectedClips.Add(c);
        if (AudioClips.Count > 0) SelectedClip = AudioClips[0];
        StatusText = $"{AudioClips.Count} Clips markiert";
        DeleteSelectedCommand.NotifyCanExecuteChanged();
    }

    [RelayCommand]
    private void DeselectAll()
    {
        SelectedClips.Clear();
        SelectedClip = null;
        DeleteSelectedCommand.NotifyCanExecuteChanged();
    }

    private bool CanAnalyzeAll() => AudioClips.Count > 0 && !IsAnalyzing;

    [RelayCommand(CanExecute = nameof(CanAnalyzeAll))]
    private async Task AnalyzeAllAsync()
    {
        var operation = _projectService.CaptureOperationContext();
        IsAnalyzing = true;
        AnalysisProgress = 0.01;  // sichtbarer Start
        CurrentStep = "init";
        var total = AudioClips.Count;
        var done = 0;
        var partial = 0;
        var failed = 0;
        var failures = new List<string>();

        try
        {
            foreach (var clip in AudioClips.ToList())
            {
                if (clip.IsAnalyzed) { done++; continue; }

                _activeAnalysisClipId = clip.Id;
                StatusText = $"Analysiere {done + 1}/{total}: {clip.Name}...";
                AnalysisProgress = (double)done / total * 100;

                try
                {
                    var result = await _api.AnalyzeAudioAsync(clip.Id, operation.CancellationToken);
                    if (!_projectService.IsCurrent(operation))
                        return;
                    if (result == null)
                    {
                        failed++;
                        failures.Add($"{clip.Name}: leere Backend-Antwort");
                    }
                    else
                    {
                        clip.Bpm = result.Bpm;
                        clip.BeatCount = result.BeatCount;
                        clip.Key = result.Key ?? "";
                        clip.AnalysisStatus = result.AnalysisStatus;
                        clip.StageErrors = result.StageErrors;
                        clip.IsAnalyzed = result.AnalysisStatus == "completed";
                        if (result.AnalysisStatus == "partial")
                            partial++;
                        else if (result.AnalysisStatus != "completed")
                        {
                            failed++;
                            failures.Add($"{clip.Name}: {FormatStageErrors(result.StageErrors)}");
                        }
                    }
                }
                catch (OperationCanceledException) when (operation.CancellationToken.IsCancellationRequested)
                {
                    throw;
                }
                catch (Exception ex)
                {
                    failed++;
                    failures.Add($"{clip.Name}: {ex.Message}");
                }
                finally
                {
                    _activeAnalysisClipId = null;
                }
                done++;
            }

            AnalysisProgress = 100;
            var completed = total - partial - failed;
            StatusText = $"Analyse beendet: {completed} vollständig, {partial} partiell, {failed} fehlgeschlagen"
                + (failures.Count > 0 ? $". Fehler: {string.Join(" | ", failures.Take(3))}" : "");
            if (_projectService.IsCurrent(operation))
                WeakReferenceMessenger.Default.Send(new AudioLibraryRefreshMessage());
        }
        catch (Exception ex)
        {
            if (_projectService.IsCurrent(operation))
                StatusText = $"Analysefehler: {ex.Message}";
        }
        finally
        {
            if (_projectService.IsCurrent(operation))
                IsAnalyzing = false;
        }

        if (_projectService.IsCurrent(operation) && SelectedClip != null)
            OnSelectedClipChanged(SelectedClip);
    }

    private bool CanAnalyzeSelected() => SelectedClip != null && !IsAnalyzing;

    [RelayCommand(CanExecute = nameof(CanAnalyzeSelected))]
    private async Task AnalyzeSelectedAsync()
    {
        if (SelectedClip == null)
        {
            StatusText = "Kein Audio-Clip ausgewählt";
            return;
        }

        var operation = _projectService.CaptureOperationContext();
        var clip = SelectedClip;
        _activeAnalysisClipId = clip.Id;
        IsAnalyzing = true;
        AnalysisProgress = 0.01;  // sichtbarer Start (0.00% Label)
        CurrentStep = "init";
        StatusText = $"Analysiere: {SelectedClip.Name}...";

        try
        {
            var result = await _api.AnalyzeAudioAsync(clip.Id, operation.CancellationToken);
            if (!_projectService.IsCurrent(operation))
                return;
            if (result != null)
            {
                clip.Bpm = result.Bpm;
                clip.BeatCount = result.BeatCount;
                clip.Key = result.Key ?? "";
                clip.AnalysisStatus = result.AnalysisStatus;
                clip.StageErrors = result.StageErrors;
                clip.IsAnalyzed = result.AnalysisStatus == "completed";
                Bpm = result.Bpm;
                BeatCount = result.BeatCount;
                Key = result.Key ?? "";
                ApplyBeatGrid(result.BeatGrid);
                StatusText = result.AnalysisStatus == "partial"
                    ? $"Analyse partiell: {FormatStageErrors(result.StageErrors)}"
                    : $"Analyse vollständig: {result.Bpm:F1} BPM | {result.BeatCount} Beats | Tonart: {result.Key ?? "–"}";
                WeakReferenceMessenger.Default.Send(new AudioLibraryRefreshMessage());
            }
            else
            {
                StatusText = "Analyse fehlgeschlagen";
            }
        }
        catch (Exception ex)
        {
            if (_projectService.IsCurrent(operation))
                StatusText = $"Analysefehler: {ex.Message}";
        }
        finally
        {
            _activeAnalysisClipId = null;
            if (_projectService.IsCurrent(operation))
                IsAnalyzing = false;
        }
    }

    [RelayCommand]
    private async Task SeparateStemsAsync()
    {
        if (SelectedClip == null)
        {
            StatusText = "Kein Audio-Clip ausgewählt";
            return;
        }

        var operation = _projectService.CaptureOperationContext();
        var clip = SelectedClip;
        _activeStemClipId = clip.Id;
        IsSeparating = true;
        StatusText = $"Stem-Separation läuft: {SelectedClip.Name}...";

        try
        {
            var result = await _api.SeparateStemsAsync(
                clip.Id,
                "htdemucs.yaml",
                operation.CancellationToken);
            if (!_projectService.IsCurrent(operation))
                return;

            if (result != null)
            {
                // L-N4: stems_paths sofort auf dem Model setzen damit STEMS-Badge
                // + Open-Folder-Button ohne Reload sichtbar werden.
                var stems = new Dictionary<string, string>();
                if (!string.IsNullOrEmpty(result.VocalsPath)) stems["vocals"] = result.VocalsPath!;
                if (!string.IsNullOrEmpty(result.InstrumentalPath)) stems["instrumental"] = result.InstrumentalPath!;
                if (!string.IsNullOrEmpty(result.DrumsPath)) stems["drums"] = result.DrumsPath!;
                if (!string.IsNullOrEmpty(result.BassPath)) stems["bass"] = result.BassPath!;
                if (!string.IsNullOrEmpty(result.OtherPath)) stems["other"] = result.OtherPath!;
                if (stems.Count > 0) clip.StemsPaths = stems;
                StatusText = $"Stems getrennt: {result.ModelUsed}";
            }
            else
            {
                StatusText = "Stem-Separation fehlgeschlagen oder Timeout/Backend-Fehler";
            }
        }
        catch (Exception ex)
        {
            if (_projectService.IsCurrent(operation))
                StatusText = $"Stem-Fehler: {ex.Message}";
        }
        finally
        {
            _activeStemClipId = null;
            if (_projectService.IsCurrent(operation))
                IsSeparating = false;
        }
    }

    [RelayCommand]
    private void OpenStemsFolder(AudioClipModel? clip)
    {
        // L-N4: Stems-Ordner im Windows Explorer oeffnen.
        // Akzeptiert clip-Parameter (vom Button gebunden) oder fallback auf SelectedClip.
        var target = clip ?? SelectedClip;
        if (target?.StemsFolderPath is { } path)
        {
            var cleanPath = path.Replace('/', '\\');
            if (Directory.Exists(cleanPath))
            {
                try
                {
                    Process.Start(new ProcessStartInfo("explorer.exe", $"\"{cleanPath}\"")
                    {
                        UseShellExecute = true,
                    });
                }
                catch (Exception ex)
                {
                    StatusText = $"Stems-Ordner kann nicht geoeffnet werden: {ex.Message}";
                }
            }
            else
            {
                StatusText = $"Stems-Ordner existiert nicht: {cleanPath}";
            }
        }
        else
        {
            StatusText = "Stems-Ordner existiert nicht oder kein Clip ausgewaehlt.";
        }
    }

    private void ResetProjectState()
    {
        _audioLibraryState.Clear();
        AudioClips.Clear();
        SelectedClip = null;
        StatusText = "Kein Projekt geöffnet";
        IsAnalyzing = false;
        IsSeparating = false;
        _activeAnalysisClipId = null;
        _activeStemClipId = null;
        AnalysisProgress = 0;
        Bpm = 0;
        BeatCount = 0;
        Key = string.Empty;
        DurationSeconds = 0;
    }

    private static string FormatStageErrors(Dictionary<string, string>? errors)
    {
        if (errors == null || errors.Count == 0)
            return "unvollständige Chunk-/Stage-Evidenz";
        return string.Join("; ", errors.Select(pair => $"{pair.Key}: {pair.Value}"));
    }

    private void OnProjectTransitionStarted(object? sender, EventArgs e)
    {
        IsAnalyzing = false;
        IsSeparating = false;
        _activeAnalysisClipId = null;
        _activeStemClipId = null;
        AnalysisProgress = 0;
        CurrentStep = string.Empty;
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _sseClient.ProgressReceived -= OnSseProgressReceived;
        _projectService.ProjectTransitionStarted -= OnProjectTransitionStarted;
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }

    /// <summary>
    /// Uebernimmt das Beatgrid aus der Analyse in die Anzeige.
    /// </summary>
    /// <remarks>
    /// Das Grid ist eine Regel (Anker + Tempo), keine Zeitmarkenliste. Ein
    /// leeres oder fehlendes Feld wird als solches gezeigt und nicht still
    /// verschwiegen - der Streaming-Pfad liefert bewusst kein Grid.
    /// </remarks>
    private void ApplyBeatGrid(Dictionary<string, JsonElement>? grid)
    {
        if (grid is null || grid.Count == 0)
        {
            BeatGridText = "";
            BeatGridStatus = "";
            return;
        }

        static double? Number(Dictionary<string, JsonElement> source, string name)
            => source.TryGetValue(name, out var value)
               && value.ValueKind == JsonValueKind.Number
               && value.TryGetDouble(out var number)
                ? number
                : null;

        static string Text(Dictionary<string, JsonElement> source, string name)
            => source.TryGetValue(name, out var value)
               && value.ValueKind == JsonValueKind.String
                ? value.GetString() ?? ""
                : "";

        var status = Text(grid, "status");
        BeatGridStatus = status;

        var bpm = Number(grid, "bpm");
        if (status is "unavailable" or "" || bpm is null or <= 0)
        {
            var method = Text(grid, "method");
            BeatGridText = method.Length > 0
                ? $"Beatgrid: nicht verfügbar ({method})"
                : "Beatgrid: nicht verfügbar";
            return;
        }

        var anchor = Number(grid, "anchor_s") ?? 0.0;
        var contrast = Number(grid, "contrast") ?? 0.0;
        var parts = new List<string>
        {
            $"Beatgrid: {bpm.Value:F2} BPM",
            $"Anker {anchor:F3} s",
            $"Güte {contrast:F2}",
        };

        var recall = Number(grid, "kick_recall");
        var precision = Number(grid, "kick_precision");
        if (recall is not null && precision is not null)
            parts.Add($"Kick {recall.Value:P0}/{precision.Value:P0}");

        if (status == "suspect")
            parts.Add("— unsicher");

        BeatGridText = string.Join(" · ", parts);
    }
}
