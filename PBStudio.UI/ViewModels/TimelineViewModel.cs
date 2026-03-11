using System.Collections.ObjectModel;
using System.Linq;
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
    [ObservableProperty] private double _selectedTimelinePosition;

    private bool _isSyncingSelection;

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
    public string SelectedTimelinePositionText => SelectedEntry == null
        ? "–"
        : $"{TimeSpan.FromSeconds(SelectedEntry.StartTime):mm\\:ss} / {TimeSpan.FromSeconds(TotalDuration):mm\\:ss}";
    public string SelectionIndexText
    {
        get
        {
            if (SelectedEntry == null)
                return "Kein Cut selektiert";

            var index = TimelineEntries.IndexOf(SelectedEntry);
            return index < 0 ? "Kein Cut selektiert" : $"Cut {index + 1} / {TimelineEntries.Count}";
        }
    }

    partial void OnSelectedEntryChanged(TimelineEntryModel? value)
    {
        if (!_isSyncingSelection)
        {
            _isSyncingSelection = true;
            SelectedTimelinePosition = value?.StartTime ?? 0;
            _isSyncingSelection = false;
        }

        OnPropertyChanged(nameof(SelectedClipName));
        OnPropertyChanged(nameof(SelectedTrigger));
        OnPropertyChanged(nameof(SelectedClipStart));
        OnPropertyChanged(nameof(SelectedTimeRange));
        OnPropertyChanged(nameof(SelectedFilePath));
        OnPropertyChanged(nameof(SelectedTimelinePositionText));
        OnPropertyChanged(nameof(SelectionIndexText));
        PreviousCutCommand.NotifyCanExecuteChanged();
        NextCutCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedTimelinePositionChanged(double value)
    {
        if (_isSyncingSelection || TimelineEntries.Count == 0)
            return;

        var nearestEntry = TimelineEntries
            .OrderBy(entry => value >= entry.StartTime && value <= entry.EndTime ? 0 : 1)
            .ThenBy(entry => Math.Abs(entry.StartTime - value))
            .FirstOrDefault();

        if (nearestEntry == null || ReferenceEquals(nearestEntry, SelectedEntry))
            return;

        _isSyncingSelection = true;
        SelectedEntry = nearestEntry;
        _isSyncingSelection = false;
    }

    private bool CanSelectPreviousCut() =>
        SelectedEntry != null && TimelineEntries.IndexOf(SelectedEntry) > 0;

    private bool CanSelectNextCut() =>
        SelectedEntry != null && TimelineEntries.IndexOf(SelectedEntry) >= 0 && TimelineEntries.IndexOf(SelectedEntry) < TimelineEntries.Count - 1;

    [RelayCommand(CanExecute = nameof(CanSelectPreviousCut))]
    private void PreviousCut()
    {
        if (SelectedEntry == null)
            return;

        var index = TimelineEntries.IndexOf(SelectedEntry);
        if (index > 0)
            SelectedEntry = TimelineEntries[index - 1];
    }

    [RelayCommand(CanExecute = nameof(CanSelectNextCut))]
    private void NextCut()
    {
        if (SelectedEntry == null)
            return;

        var index = TimelineEntries.IndexOf(SelectedEntry);
        if (index >= 0 && index < TimelineEntries.Count - 1)
            SelectedEntry = TimelineEntries[index + 1];
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
        SelectedEntry = TimelineEntries.FirstOrDefault();
        SelectedTimelinePosition = SelectedEntry?.StartTime ?? 0;
        StatusText = TimelineEntries.Count == 0
            ? "Timeline ist leer"
            : $"Timeline: {TimelineEntries.Count} Clips, {TotalDuration:F1}s";
        OnPropertyChanged(nameof(HasTimeline));
        OnPropertyChanged(nameof(SelectedTimelinePositionText));
        OnPropertyChanged(nameof(SelectionIndexText));
        PreviousCutCommand.NotifyCanExecuteChanged();
        NextCutCommand.NotifyCanExecuteChanged();
        IsLoading = false;
    }
}
