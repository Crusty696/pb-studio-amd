using System;
using System.ComponentModel;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>TimelineView mit minimaler echter Clip-Preview für selektierte Timeline-Cuts.</summary>
public partial class TimelineView : UserControl
{
    private readonly DispatcherTimer _playbackTimer;
    private TimelineViewModel? _viewModel;
    private string? _loadedSourcePath;
    private double _loadedClipStart;
    private double _loadedClipEnd;
    private bool _mediaOpened;
    private bool _pendingSeek;

    public TimelineView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<TimelineViewModel>();

        _playbackTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(120)
        };
        _playbackTimer.Tick += PlaybackTimer_OnTick;

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        AttachViewModel(DataContext as TimelineViewModel);
        DataContextChanged += OnDataContextChanged;
        SyncPreviewToSelection(forceReload: true);
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        DataContextChanged -= OnDataContextChanged;
        AttachViewModel(null);
        _playbackTimer.Stop();
        PreviewPlayer.Stop();
        PreviewPlayer.Source = null;
    }

    private void OnDataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        AttachViewModel(e.NewValue as TimelineViewModel);
        SyncPreviewToSelection(forceReload: true);
    }

    private void AttachViewModel(TimelineViewModel? next)
    {
        if (ReferenceEquals(_viewModel, next))
            return;

        if (_viewModel != null)
            _viewModel.PropertyChanged -= ViewModel_OnPropertyChanged;

        _viewModel = next;

        if (_viewModel != null)
            _viewModel.PropertyChanged += ViewModel_OnPropertyChanged;
    }

    private void ViewModel_OnPropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName is nameof(TimelineViewModel.SelectedEntry)
            or nameof(TimelineViewModel.SelectedTimelinePosition)
            or nameof(TimelineViewModel.CanPreviewSelectedClip))
        {
            Dispatcher.Invoke(() => SyncPreviewToSelection(forceReload: e.PropertyName == nameof(TimelineViewModel.SelectedEntry)));
        }
    }

    private void SyncPreviewToSelection(bool forceReload)
    {
        var entry = _viewModel?.SelectedEntry;
        if (entry == null || !_viewModel!.CanPreviewSelectedClip)
        {
            ResetPreview("Kein Preview geladen");
            return;
        }

        var sourcePath = entry.FilePath;
        var clipStart = Math.Max(0, entry.ClipStart);
        var clipEnd = Math.Max(clipStart, entry.ClipStart + entry.Duration);
        var needsReload = forceReload
            || !string.Equals(_loadedSourcePath, sourcePath, StringComparison.OrdinalIgnoreCase)
            || Math.Abs(_loadedClipStart - clipStart) > 0.01
            || Math.Abs(_loadedClipEnd - clipEnd) > 0.01;

        _loadedSourcePath = sourcePath;
        _loadedClipStart = clipStart;
        _loadedClipEnd = clipEnd;
        PreviewEmptyText.Visibility = Visibility.Collapsed;
        PreviewStatusText.Text = $"Bereit: {Path.GetFileName(sourcePath)}";

        if (needsReload)
        {
            _mediaOpened = false;
            _pendingSeek = true;
            _playbackTimer.Stop();
            PreviewPlayer.Stop();
            PreviewPlayer.Source = new Uri(sourcePath, UriKind.Absolute);
            return;
        }

        if (_mediaOpened)
        {
            SeekToClipStart();
        }
    }

    private void ResetPreview(string status)
    {
        _loadedSourcePath = null;
        _loadedClipStart = 0;
        _loadedClipEnd = 0;
        _mediaOpened = false;
        _pendingSeek = false;
        _playbackTimer.Stop();
        PreviewPlayer.Stop();
        PreviewPlayer.Source = null;
        PreviewEmptyText.Visibility = Visibility.Visible;
        PreviewStatusText.Text = status;
    }

    private void SeekToClipStart()
    {
        if (!_mediaOpened)
        {
            _pendingSeek = true;
            return;
        }

        try
        {
            var target = TimeSpan.FromSeconds(_loadedClipStart);
            var delta = (PreviewPlayer.Position - target).Duration();
            if (delta > TimeSpan.FromMilliseconds(200))
                PreviewPlayer.Position = target;

            _pendingSeek = false;
        }
        catch (NotSupportedException)
        {
            _pendingSeek = false;
            PreviewStatusText.Text = "Medienquelle unterstützt kein Seeking";
        }
    }

    private void PlaybackTimer_OnTick(object? sender, EventArgs e)
    {
        if (!_mediaOpened)
            return;

        if (PreviewPlayer.Position.TotalSeconds >= _loadedClipEnd - 0.05)
        {
            PreviewPlayer.Pause();
            _playbackTimer.Stop();
            SeekToClipStart();
            PreviewStatusText.Text = "Preview beendet";
        }
    }

    private void PreviewPlayer_OnMediaOpened(object sender, RoutedEventArgs e)
    {
        _mediaOpened = true;
        PreviewEmptyText.Visibility = Visibility.Collapsed;
        PreviewStatusText.Text = $"Ready @ {TimeSpan.FromSeconds(_loadedClipStart):mm\\:ss}";
        if (_pendingSeek)
            SeekToClipStart();
    }

    private void PreviewPlayer_OnMediaEnded(object sender, RoutedEventArgs e)
    {
        _playbackTimer.Stop();
        SeekToClipStart();
        PreviewStatusText.Text = "Preview beendet";
    }

    private void PreviewPlayer_OnMediaFailed(object sender, ExceptionRoutedEventArgs e)
    {
        ResetPreview($"Preview-Fehler: {e.ErrorException.Message}");
    }

    private void PlayPreview_Click(object sender, RoutedEventArgs e)
    {
        if (_viewModel?.CanPreviewSelectedClip != true)
            return;

        if (!_mediaOpened)
        {
            SyncPreviewToSelection(forceReload: true);
            return;
        }

        if (PreviewPlayer.Position.TotalSeconds < _loadedClipStart || PreviewPlayer.Position.TotalSeconds >= _loadedClipEnd)
            SeekToClipStart();

        PreviewPlayer.Play();
        _playbackTimer.Start();
        PreviewStatusText.Text = "Preview läuft";
    }

    private void PausePreview_Click(object sender, RoutedEventArgs e)
    {
        if (!_mediaOpened)
            return;

        PreviewPlayer.Pause();
        _playbackTimer.Stop();
        PreviewStatusText.Text = "Preview pausiert";
    }

    private void StopPreview_Click(object sender, RoutedEventArgs e)
    {
        if (!_mediaOpened)
            return;

        PreviewPlayer.Stop();
        _playbackTimer.Stop();
        SeekToClipStart();
        PreviewStatusText.Text = "Preview gestoppt";
    }
}
