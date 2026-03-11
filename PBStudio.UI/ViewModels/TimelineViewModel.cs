using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
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
    [ObservableProperty] private TimelineEntryModel? _selectedEntry;

    public ObservableCollection<TimelineEntryModel> TimelineEntries { get; } = [];

    public TimelineViewModel(IApiClient api)
    {
        _api = api;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "backend-ready" or "timeline-refresh")
                _ = RefreshTimelineAsync();
        });
    }

    public bool HasTimeline => TimelineEntries.Count > 0;
    public string SelectedClipName => SelectedEntry?.ClipName ?? "Kein Clip ausgewählt";
    public string SelectedTrigger => SelectedEntry == null ? "–" : $"{SelectedEntry.TriggerType} ({SelectedEntry.TriggerStrength:F2})";
    public string SelectedClipStart => SelectedEntry == null ? "–" : $"{SelectedEntry.ClipStart:F2}s";
    public string SelectedTimeRange => SelectedEntry?.TimeRangeText ?? "–";
    public string SelectedFilePath => SelectedEntry?.FilePath ?? "–";

    partial void OnSelectedEntryChanged(TimelineEntryModel? value)
    {
        OnPropertyChanged(nameof(SelectedClipName));
        OnPropertyChanged(nameof(SelectedTrigger));
        OnPropertyChanged(nameof(SelectedClipStart));
        OnPropertyChanged(nameof(SelectedTimeRange));
        OnPropertyChanged(nameof(SelectedFilePath));
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

        SelectedEntry = TimelineEntries.FirstOrDefault();
        TotalDuration = timeline.TotalDuration;
        AudioPath = timeline.AudioPath;
        StatusText = TimelineEntries.Count == 0
            ? "Timeline ist leer"
            : $"Timeline: {TimelineEntries.Count} Clips, {TotalDuration:F1}s";
        OnPropertyChanged(nameof(HasTimeline));
        IsLoading = false;
    }
}
