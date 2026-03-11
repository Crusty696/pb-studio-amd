using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Audio-Bibliothek.</summary>
public partial class AudioLibraryViewModel : ObservableObject
{
    private readonly IApiClient _api;

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

    public AudioLibraryViewModel(IApiClient api)
    {
        _api = api;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "backend-ready" or "audio-imported" or "audio-library-refresh" or "media-library-refresh")
                _ = LoadAudioClipsAsync();
        });
    }

    partial void OnSelectedClipChanged(AudioClipModel? value)
    {
        if (value == null) return;
        Bpm = value.Bpm;
        BeatCount = value.BeatCount;
        Key = value.Key;
        DurationSeconds = value.DurationSeconds;
    }

    [RelayCommand]
    private async Task LoadAudioClipsAsync()
    {
        var clips = await _api.GetAudioClipsAsync();
        if (clips != null)
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
            StatusText = $"{clips.Count} Audio-Clips geladen";
        }
        else
        {
            StatusText = "Audio-Clips laden fehlgeschlagen";
        }
    }

    [RelayCommand]
    private void SelectAll()
    {
        // ListBox doesn't support multi-select binding easily, so just select first
        if (AudioClips.Count > 0)
            SelectedClip = AudioClips[0];
        StatusText = $"{AudioClips.Count} Clips verfügbar";
    }

    [RelayCommand]
    private void DeselectAll()
    {
        SelectedClip = null;
    }

    [RelayCommand]
    private async Task AnalyzeAllAsync()
    {
        if (AudioClips.Count == 0) return;

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

    [RelayCommand]
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
}
