using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using CommunityToolkit.Mvvm.Messaging.Messages;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Timeline-Vorschau.</summary>
public partial class TimelineViewModel : ObservableObject, IDisposable
{
    private readonly TimelineStateService _timelineState;
    private readonly SemaphoreSlim _loadGate = new(1, 1);
    private int _loadVersion;
    private volatile bool _reloadQueued;
    private bool _disposed;

    [ObservableProperty] private string _statusText = "";
    [ObservableProperty] private double _totalDuration;
    [ObservableProperty] private string? _audioPath;
    [ObservableProperty] private bool _isLoading;
    [ObservableProperty] private TimelineEntryModel? _selectedEntry;
    [ObservableProperty] private double _selectedTimelinePosition;

    private bool _isSyncingSelection;

    public ObservableCollection<TimelineEntryModel> TimelineEntries { get; } = [];

    public TimelineViewModel(TimelineStateService timelineState)
    {
        _timelineState = timelineState;

        WeakReferenceMessenger.Default.Register<ValueChangedMessage<string>>(this, (_, message) =>
        {
            if (message.Value is "timeline-refresh" or "project-opened")
                _ = RequestTimelineRefreshAsync();
            else if (message.Value == "project-closed")
            {
                _timelineState.Clear();
                ResetTimelineState();
            }
        });
    }

    public bool HasTimeline => TimelineEntries.Count > 0;
    public string SelectedClipName => SelectedEntry?.ClipName ?? "Kein Clip ausgewählt";
    public string SelectedTrigger => SelectedEntry == null ? "–" : $"{SelectedEntry.TriggerType} ({SelectedEntry.TriggerStrength:F2})";
    public string SelectedClipStart => SelectedEntry == null ? "–" : $"{SelectedEntry.ClipStart:F2}s";
    public string SelectedTimeRange => SelectedEntry?.TimeRangeText ?? "–";
    public string SelectedFilePath => SelectedEntry?.FilePath ?? "–";
    public bool CanPreviewSelectedClip => SelectedEntry != null && File.Exists(SelectedEntry.FilePath);
    public string SelectedPreviewRange => SelectedEntry == null
        ? "–"
        : $"Clip {TimeSpan.FromSeconds(SelectedEntry.ClipStart):mm\\:ss} - {TimeSpan.FromSeconds(SelectedEntry.ClipStart + SelectedEntry.Duration):mm\\:ss}";
    public string SelectedTimelinePositionText => !HasTimeline
        ? "–"
        : $"{TimeSpan.FromSeconds(SelectedTimelinePosition):mm\\:ss} / {TimeSpan.FromSeconds(TotalDuration):mm\\:ss}";
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
        OnPropertyChanged(nameof(CanPreviewSelectedClip));
        OnPropertyChanged(nameof(SelectedPreviewRange));
        OnPropertyChanged(nameof(SelectedTimelinePositionText));
        OnPropertyChanged(nameof(SelectionIndexText));
        PreviousCutCommand.NotifyCanExecuteChanged();
        NextCutCommand.NotifyCanExecuteChanged();
    }

    partial void OnSelectedTimelinePositionChanged(double value)
    {
        OnPropertyChanged(nameof(SelectedTimelinePositionText));

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
        _reloadQueued = false;
        var version = Interlocked.Increment(ref _loadVersion);

        if (!await _loadGate.WaitAsync(0))
        {
            _reloadQueued = true;
            return;
        }

        try
        {
            IsLoading = true;
            StatusText = "Timeline wird geladen...";

            var timeline = await _timelineState.RefreshAsync();
            if (timeline == null)
            {
                if (version == _loadVersion)
                    StatusText = "Timeline laden fehlgeschlagen";
                return;
            }

            if (version != _loadVersion)
                return;

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
                    SegmentType = entry.SegmentType,
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
        }
        finally
        {
            IsLoading = false;
            _loadGate.Release();
        }

        if (_reloadQueued)
            await RefreshTimelineAsync();
    }

    private async Task RequestTimelineRefreshAsync()
    {
        _reloadQueued = true;
        await RefreshTimelineAsync();
    }

    private void ResetTimelineState()
    {
        TimelineEntries.Clear();
        TotalDuration = 0;
        AudioPath = null;
        SelectedEntry = null;
        SelectedTimelinePosition = 0;
        IsLoading = false;
        StatusText = "Kein Projekt geöffnet";
        OnPropertyChanged(nameof(HasTimeline));
        OnPropertyChanged(nameof(CanPreviewSelectedClip));
        OnPropertyChanged(nameof(SelectedPreviewRange));
        OnPropertyChanged(nameof(SelectedTimelinePositionText));
        OnPropertyChanged(nameof(SelectionIndexText));
        PreviousCutCommand.NotifyCanExecuteChanged();
        NextCutCommand.NotifyCanExecuteChanged();
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        WeakReferenceMessenger.Default.Unregister<ValueChangedMessage<string>>(this);
        _loadGate.Dispose();
    }
}
