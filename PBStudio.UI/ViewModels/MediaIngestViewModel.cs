using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Models;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für den Media-Import Tab.</summary>
public partial class MediaIngestViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly IDialogService _dialogService;
    private bool _disposed;

    [ObservableProperty] private string _statusText = "Bereit für Import";
    [ObservableProperty] private double _importProgress;
    [ObservableProperty] private bool _isImporting;
    [ObservableProperty] private string _videoImportPath = string.Empty;

    public ObservableCollection<AudioClipModel> ImportedAudio { get; } = [];
    public ObservableCollection<VideoClipModel> ImportedVideo { get; } = [];

    public MediaIngestViewModel(IApiClient api, IDialogService dialogService)
    {
        _api = api;
        _dialogService = dialogService;

        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) =>
            System.Windows.Application.Current.Dispatcher.Invoke(ResetProjectState));
        WeakReferenceMessenger.Default.Register<ProjectClosingMessage>(this, (_, _) =>
            System.Windows.Application.Current.Dispatcher.Invoke(ResetProjectState));
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
        var files = _dialogService.OpenFiles(
            "Audio-Dateien importieren",
            "Audio-Dateien|*.mp3;*.wav;*.flac;*.ogg;*.m4a;*.aac;*.aiff;*.aif|Alle Dateien|*.*"
        );

        if (files.Count == 0) return;

        ImportProgress = 0;
        IsImporting = true;

        var validFiles = new List<string>();
        var failedPrecheck = 0;

        foreach (var file in files)
        {
            try
            {
                using var fs = File.OpenRead(file);
                validFiles.Add(file);
            }
            catch (Exception)
            {
                failedPrecheck++;
            }
        }

        if (validFiles.Count == 0)
        {
            StatusText = $"Import fehlgeschlagen: Alle {files.Count} Dateien konnten nicht gelesen werden (Berechtigung oder Dateisperre).";
            IsImporting = false;
            return;
        }

        StatusText = $"Importiere {validFiles.Count} Audio-Dateien...";
        var importedCount = 0;
        var failedImport = 0;

        try
        {
            for (int i = 0; i < validFiles.Count; i++)
            {
                try
                {
                    var result = await _api.ImportAudioAsync(validFiles[i]);
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
                }
                catch (Exception ex)
                {
                    failedImport++;
                    StatusText = $"Fehler bei {Path.GetFileName(validFiles[i])}: {ex.Message}";
                }
                ImportProgress = (i + 1.0) / validFiles.Count * 100;
            }

            if (importedCount > 0)
            {
                WeakReferenceMessenger.Default.Send(new AudioImportedMessage());
                WeakReferenceMessenger.Default.Send(new AudioLibraryRefreshMessage());
                WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
            }

            var totalFailed = failedPrecheck + failedImport;
            StatusText = totalFailed > 0
                ? $"{importedCount} importiert, {totalFailed} fehlgeschlagen (Format/Zugriff)"
                : $"{importedCount} Audio-Dateien erfolgreich importiert";
        }
        catch (Exception ex)
        {
            StatusText = $"Kritischer Audio-Import-Fehler: {ex.Message}";
        }
        finally
        {
            IsImporting = false;
        }
    }

    [RelayCommand]
    private async Task ImportVideoAsync()
    {
        var files = _dialogService.OpenFiles(
            "Video-Dateien importieren",
            "Video-Dateien|*.mp4;*.avi;*.mkv;*.mov;*.webm;*.wmv|Alle Dateien|*.*"
        );

        if (files.Count == 0) return;

        await ImportVideosFromPathsAsync(files);
    }

    [RelayCommand]
    private void BrowseVideoPath()
    {
        var files = _dialogService.OpenFiles(
            "Video-Pfad für In-App-Import auswählen",
            "Video-Dateien|*.mp4;*.avi;*.mkv;*.mov;*.webm;*.wmv;*.flv|Alle Dateien|*.*"
        );

        if (files.Count == 0)
            return;

        VideoImportPath = string.Join("; ", files.Select(QuoteIfNeeded));
        StatusText = $"{files.Count} Video-Pfad/Pfade bereit für In-App-Import";
    }

    [RelayCommand]
    private async Task ImportFolderAsync()
    {
        var folder = _dialogService.OpenFolder("Video-Ordner importieren");
        if (string.IsNullOrEmpty(folder)) return;

        StatusText = $"Scanne Ordner: {folder}...";
        var supported = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv",
        };

        try
        {
            var files = Directory.GetFiles(folder, "*.*", SearchOption.TopDirectoryOnly)
                .Where(f => supported.Contains(Path.GetExtension(f)))
                .ToList();

            if (files.Count == 0)
            {
                StatusText = "Keine unterstützten Video-Dateien im Ordner gefunden.";
                return;
            }

            await ImportVideosFromPathsAsync(files);
        }
        catch (Exception ex)
        {
            StatusText = "Fehler beim Scannen des Ordners: " + ex.Message;
        }
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

        var validPaths = new List<string>();
        var failedPrecheck = 0;

        foreach (var path in paths)
        {
            try
            {
                using var fs = File.OpenRead(path);
                validPaths.Add(path);
            }
            catch (Exception)
            {
                failedPrecheck++;
            }
        }

        if (validPaths.Count == 0)
        {
            StatusText = $"Import fehlgeschlagen: Alle {paths.Count} Dateien konnten nicht gelesen werden (Berechtigung oder Dateisperre).";
            IsImporting = false;
            return;
        }

        StatusText = $"Importiere {validPaths.Count} Video-Datei(en)...";

        try
        {
            var results = await _api.ImportVideosAsync(validPaths);
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
                    WeakReferenceMessenger.Default.Send(new VideoImportedMessage());
                    WeakReferenceMessenger.Default.Send(new VideoLibraryRefreshMessage());
                    WeakReferenceMessenger.Default.Send(new MediaLibraryRefreshMessage());
                    VideoImportPath = string.Empty;
                }

                var totalFailed = failedPrecheck + (validPaths.Count - results.Count);
                StatusText = totalFailed > 0
                    ? $"{results.Count} importiert, {totalFailed} fehlgeschlagen (Format/Zugriff)"
                    : $"{results.Count} Video-Datei(en) erfolgreich importiert";
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

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        WeakReferenceMessenger.Default.UnregisterAll(this);
    }
}
