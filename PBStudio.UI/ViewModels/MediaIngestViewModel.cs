using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using Microsoft.Win32;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für den Media-Import Tab.</summary>
public partial class MediaIngestViewModel : ObservableObject
{
    private readonly IApiClient _api;

    [ObservableProperty] private string _statusText = "Bereit für Import";
    [ObservableProperty] private double _importProgress;
    [ObservableProperty] private bool _isImporting;

    public ObservableCollection<AudioClipModel> ImportedAudio { get; } = [];
    public ObservableCollection<VideoClipModel> ImportedVideo { get; } = [];

    public MediaIngestViewModel(IApiClient api)
    {
        _api = api;
    }

    [RelayCommand]
    private async Task ImportAudioAsync()
    {
        var dialog = new OpenFileDialog
        {
            Filter = "Audio-Dateien|*.mp3;*.wav;*.flac;*.ogg;*.m4a;*.aac|Alle Dateien|*.*",
            Multiselect = true,
            Title = "Audio-Dateien importieren",
        };

        if (dialog.ShowDialog() != true) return;

        IsImporting = true;
        StatusText = $"Importiere {dialog.FileNames.Length} Audio-Dateien...";

        var importedCount = 0;

        for (int i = 0; i < dialog.FileNames.Length; i++)
        {
            var result = await _api.ImportAudioAsync(dialog.FileNames[i]);
            if (result != null)
            {
                importedCount++;
                ImportedAudio.Add(new AudioClipModel
                {
                    Id = result.Id,
                    Name = result.Name,
                    Path = result.Path,
                    DurationSeconds = result.DurationSeconds,
                    SampleRate = result.SampleRate,
                    Format = result.Format,
                });
            }
            ImportProgress = (i + 1.0) / dialog.FileNames.Length * 100;
        }

        if (importedCount > 0)
        {
            WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("audio-imported"));
            WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("media-library-refresh"));
        }

        IsImporting = false;
        StatusText = $"{importedCount}/{dialog.FileNames.Length} Audio-Dateien importiert";
    }

    [RelayCommand]
    private async Task ImportVideoAsync()
    {
        var dialog = new OpenFileDialog
        {
            Filter = "Video-Dateien|*.mp4;*.avi;*.mkv;*.mov;*.webm;*.wmv|Alle Dateien|*.*",
            Multiselect = true,
            Title = "Video-Dateien importieren",
        };

        if (dialog.ShowDialog() != true) return;

        IsImporting = true;
        StatusText = $"Importiere {dialog.FileNames.Length} Video-Dateien...";

        var results = await _api.ImportVideosAsync(dialog.FileNames.ToList());
        if (results != null)
        {
            foreach (var r in results)
            {
                ImportedVideo.Add(new VideoClipModel
                {
                    Id = r.Id,
                    Name = r.Name,
                    Path = r.Path,
                    DurationSeconds = r.DurationSeconds,
                    Width = r.Width,
                    Height = r.Height,
                    Fps = r.Fps,
                    Codec = r.Codec,
                    Tags = r.Tags,
                });
            }

            if (results.Count > 0)
            {
                WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("video-imported"));
                WeakReferenceMessenger.Default.Send(new ValueChangedMessage<string>("media-library-refresh"));
            }
        }

        IsImporting = false;
        StatusText = $"{results?.Count ?? 0}/{dialog.FileNames.Length} Video-Dateien importiert";
    }
}
