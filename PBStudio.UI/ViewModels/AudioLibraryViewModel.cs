using System.Collections.ObjectModel;
using System.IO;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using Microsoft.Win32;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Audio-Bibliothek.</summary>
public partial class AudioLibraryViewModel : ObservableObject, IDisposable
{
    private bool _disposed;
    private readonly IApiClient _api;
    private readonly AudioLibraryStateService _audioLibraryState;
    private readonly SSEClient _sseClient;
    private readonly IDialogService _dialogService;

    [ObservableProperty] private AudioClipModel? _selectedClip;
    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private bool _isAnalyzing;
    [ObservableProperty] private bool _isSeparating;
    [ObservableProperty] private double _analysisProgress;
    [ObservableProperty] private double _bpm;
    [ObservableProperty] private int _beatCount;
    [ObservableProperty] private string _key = "";
    [ObservableProperty] private double _durationSeconds;

    public ObservableCollection<AudioClipModel> AudioClips { get; } = [];

    public AudioLibraryViewModel(IApiClient api, AudioLibraryStateService audioLibraryState, SSEClient sseClient, IDialogService dialogService)
    {
        _api = api;
        _audioLibraryState = audioLibraryState;
        _sseClient = sseClient;
        _dialogService = dialogService;

        _sseClient.ProgressReceived += OnSseProgressReceived;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "project-opened" or "audio-imported" or "audio-library-refresh" or "media-library-refresh")
                _ = LoadAudioClipsAsync();
            else if (message.Value is "project-closed")
                ResetProjectState();
        });
    }

    private void OnSseProgressReceived(object? sender, ProgressEventArgs e)
    {
        if (e.EventType == "analysis_progress" && IsAnalyzing)
        {
            Application.Current.Dispatcher.Invoke(() =>
            {
                StatusText = e.Message;
            });
        }
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
            "Audio-Dateien|*.mp3;*.wav;*.flac;*.ogg;*.m4a;*.aac|Alle Dateien|*.*"
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
            ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"
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
        IsAnalyzing = true;
        StatusText = $"Importiere {files.Count} Dateien...";

        var imported = 0;
        try
        {
            foreach (var file in files)
            {
                var result = await _api.ImportAudioAsync(file);
                if (result != null) imported++;
            }

            if (imported > 0)
            {
                StatusText = $"{imported} Audio-Dateien erfolgreich importiert";
                WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("audio-imported"));
                await LoadAudioClipsAsync();
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
            IsAnalyzing = false;
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
        if (AudioClips.Count > 0)
            SelectedClip = AudioClips[0];
        StatusText = $"{AudioClips.Count} Clips verfügbar";
    }

    [RelayCommand]
    private void DeselectAll()
    {
        SelectedClip = null;
    }

    private bool CanAnalyzeAll() => AudioClips.Count > 0 && !IsAnalyzing;

    [RelayCommand(CanExecute = nameof(CanAnalyzeAll))]
    private async Task AnalyzeAllAsync()
    {
        IsAnalyzing = true;
        var total = AudioClips.Count;
        var done = 0;

        try
        {
            foreach (var clip in AudioClips.ToList())
            {
                if (clip.IsAnalyzed) { done++; continue; }

                StatusText = $"Analysiere {done + 1}/{total}: {clip.Name}...";
                AnalysisProgress = (double)done / total * 100;

                var result = await _api.AnalyzeAudioAsync(clip.Id);
                if (result != null)
                {
                    clip.Bpm = result.Bpm;
                    clip.BeatCount = result.BeatCount;
                    clip.Key = result.Key ?? "";
                    clip.IsAnalyzed = true;
                }
                done++;
            }

            AnalysisProgress = 100;
            StatusText = $"Alle {total} Clips analysiert";
            WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("audio-library-refresh"));
        }
        catch (Exception ex)
        {
            StatusText = $"Analysefehler: {ex.Message}";
        }
        finally
        {
            IsAnalyzing = false;
        }

        if (SelectedClip != null) OnSelectedClipChanged(SelectedClip);
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

        IsAnalyzing = true;
        StatusText = $"Analysiere: {SelectedClip.Name}...";

        try
        {
            var result = await _api.AnalyzeAudioAsync(SelectedClip.Id);
            if (result != null)
            {
                SelectedClip.Bpm = result.Bpm;
                SelectedClip.BeatCount = result.BeatCount;
                SelectedClip.Key = result.Key ?? "";
                SelectedClip.IsAnalyzed = true;
                Bpm = result.Bpm;
                BeatCount = result.BeatCount;
                Key = result.Key ?? "";
                StatusText = $"Analyse fertig: {result.Bpm:F1} BPM | {result.BeatCount} Beats | Tonart: {result.Key ?? "–"}";
                WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("audio-library-refresh"));
            }
            else
            {
                StatusText = "Analyse fehlgeschlagen";
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Analysefehler: {ex.Message}";
        }
        finally
        {
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

        IsSeparating = true;
        StatusText = $"Stem-Separation läuft: {SelectedClip.Name}...";

        try
        {
            var result = await _api.SeparateStemsAsync(SelectedClip.Id);
            StatusText = result != null
                ? $"Stems getrennt: {result.ModelUsed}"
                : "Stem-Separation fehlgeschlagen oder Timeout/Backend-Fehler";
        }
        catch (Exception ex)
        {
            StatusText = $"Stem-Fehler: {ex.Message}";
        }
        finally
        {
            IsSeparating = false;
        }
    }

    private void ResetProjectState()
    {
        AudioClips.Clear();
        SelectedClip = null;
        StatusText = "Kein Projekt geöffnet";
        IsAnalyzing = false;
        IsSeparating = false;
        AnalysisProgress = 0;
        Bpm = 0;
        BeatCount = 0;
        Key = string.Empty;
        DurationSeconds = 0;
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _sseClient.ProgressReceived -= OnSseProgressReceived;
        WeakReferenceMessenger.Default.Unregister<ValueChangedMessage<string>>(this);
    }
}
