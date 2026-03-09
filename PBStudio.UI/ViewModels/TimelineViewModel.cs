using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Timeline-Vorschau.</summary>
public partial class TimelineViewModel : ObservableObject
{
    private readonly IApiClient _api;

    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private double _totalDuration;
    [ObservableProperty] private string? _audioPath;
    [ObservableProperty] private bool _isLoading;

    public ObservableCollection<TimelineEntryModel> TimelineEntries { get; } = [];

    public TimelineViewModel(IApiClient api)
    {
        _api = api;
    }

    [RelayCommand]
    private async Task RefreshTimelineAsync()
    {
        IsLoading = true;
        StatusText = "Timeline wird geladen...";

        var timeline = await _api.GetTimelineAsync();
        if (timeline == null)
        {
            StatusText = "Timeline laden fehlgeschlagen";
            IsLoading = false;
            return;
        }

        TimelineEntries.Clear();
        foreach (var entry in timeline.Entries)
        {
            TimelineEntries.Add(new TimelineEntryModel
            {
                ClipId = entry.ClipId,
                ClipName = entry.ClipName,
                FilePath = entry.FilePath,
                StartTime = entry.StartTime,
                EndTime = entry.EndTime,
                ClipStart = entry.ClipStart,
                TriggerType = entry.TriggerType,
                TriggerStrength = entry.TriggerStrength,
            });
        }

        TotalDuration = timeline.TotalDuration;
        AudioPath = timeline.AudioPath;
        StatusText = $"Timeline: {TimelineEntries.Count} Clips, {TotalDuration:F1}s";
        IsLoading = false;
    }
}
