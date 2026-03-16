using System.Collections.ObjectModel;
using System.IO;
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
    [ObservableProperty] private string _videoImportPath = string.Empty;

    public ObservableCollection<AudioClipModel> ImportedAudio { get; } = [];
    public ObservableCollection<VideoClipModel> ImportedVideo { get; } = [];

    public MediaIngestViewModel(IApiClient api)
    {
        _api = api;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "project-closed" or "project-closing")
                ResetProjectState();
        });
    }

    private void ResetProjectState()
    {
        ImportedAudio.Clear();
        ImportedVideo.Clear();
        VideoImportPath = string.Empty;
        ImportProgress = 0;
        IsImporting = false;
        StatusText = "Kein Projekt geöffnet";
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

        ImportProgress = 0;
        IsImporting = true;
        StatusText = $"Importiere {dialog.FileNames.Length} Audio-Dateien...";

        var importedCount = 0;

        try
        {
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

            StatusText = $"{importedCount}/{dialog.FileNames.Length} Audio-Dateien importiert";
        }
        catch (Exception ex)
        {
            StatusText = $"Audio-Import fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            IsImporting = false;
        }
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

        await ImportVideosFromPathsAsync(dialog.FileNames.ToList());
    }

    [RelayCommand]
    private void BrowseVideoPath()
    {
        var dialog = new OpenFileDialog
        {
            Filter = "Video-Dateien|*.mp4;*.avi;*.mkv;*.mov;*.webm;*.wmv;*.flv|Alle Dateien|*.*",
            Multiselect = true,
            Title = "Video-Pfad für In-App-Import auswählen",
        };

        if (dialog.ShowDialog() != true)
            return;

        VideoImportPath = string.Join("; ", dialog.FileNames.Select(QuoteIfNeeded));
        StatusText = $"{dialog.FileNames.Length} Video-Pfad/Pfade bereit für In-App-Import";
    }

    [RelayCommand]
    private async Task ImportVideoFromPathAsync()
    {
        var parsedPaths = ParseVideoImportPaths(VideoImportPath);
        if (parsedPaths.Count == 0)
        {
            StatusText = "Kein gültiger Video-Pfad angegeben";
            return;
        }

        await ImportVideosFromPathsAsync(parsedPaths);
    }

    private async Task ImportVideosFromPathsAsync(List<string> paths)
    {
        ImportProgress = 0;
        IsImporting = true;
        StatusText = $"Importiere {paths.Count} Video-Datei(en)...";

        try
        {
            var results = await _api.ImportVideosAsync(paths);
            ImportProgress = 100;

            if (results != null)
            {
                var existingIds = ImportedVideo.Select(v => v.Id).ToHashSet();
                foreach (var r in results)
                {
                    if (!existingIds.Add(r.Id))
                        continue;

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
                    VideoImportPath = string.Empty;
                }

                StatusText = results.Count == paths.Count
                    ? $"{results.Count}/{paths.Count} Video-Datei(en) importiert"
                    : $"{results.Count}/{paths.Count} Video-Datei(en) importiert – prüfe Pfade/Format bei den übrigen";
            }
            else
            {
                StatusText = "Video-Import fehlgeschlagen";
            }
        }
        catch (Exception ex)
        {
            StatusText = $"Video-Import fehlgeschlagen: {ex.Message}";
        }
        finally
        {
            IsImporting = false;
        }
    }

    private static List<string> ParseVideoImportPaths(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw))
            return [];

        var supported = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv",
        };

        return raw
            .Split(['\r', '\n', ';'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(part => part.Trim().Trim('"'))
            .Where(part => !string.IsNullOrWhiteSpace(part))
            .Select(path =>
            {
                try { return Path.GetFullPath(path); }
                catch { return string.Empty; }
            })
            .Where(path => !string.IsNullOrWhiteSpace(path))
            .Where(File.Exists)
            .Where(path => supported.Contains(Path.GetExtension(path)))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static string QuoteIfNeeded(string path)
        => path.Contains(' ') ? $"\"{path}\"" : path;
}
