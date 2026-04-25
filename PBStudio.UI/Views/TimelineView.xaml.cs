using System;
using System.ComponentModel;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

using System.Windows.Shapes;
using System.Windows.Media;
using System.Windows.Input;
using PBStudio.UI.Models;

namespace PBStudio.UI.Views;

/// <summary>TimelineView mit interaktiver Power-Timeline (Option C).</summary>
public partial class TimelineView : UserControl
{
    private readonly DispatcherTimer _playbackTimer;
    private readonly DispatcherTimer _syncTimer;
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

        _syncTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromSeconds(1)
        };
        _syncTimer.Tick += SyncTimer_OnTick;

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;

        // C1/POWER: High-frequency render loop for smooth playhead tracking
        CompositionTarget.Rendering += OnCompositionTargetRendering;
    }

    private double _lastScrollX = 0;
    private void OnCompositionTargetRendering(object? sender, EventArgs e)
    {
        if (_viewModel == null || !_mediaOpened || PreviewPlayer.Position.TotalSeconds <= 0) return;
        if (PreviewPlayer.NaturalDuration.HasTimeSpan && PreviewPlayer.Position >= PreviewPlayer.NaturalDuration.TimeSpan) return;

        // Auto-Scroll Logic
        var playheadX = _viewModel.SelectedTimelinePosition * _viewModel.PixelsPerSecond;
        var scrollViewer = GetScrollViewer(TimelineItemsControl);
        if (scrollViewer == null) return;

        double viewportWidth = scrollViewer.ActualWidth;
        double currentOffset = scrollViewer.HorizontalOffset;

        // Follow Playhead mode: center playhead if it moves too far
        if (playheadX > currentOffset + (viewportWidth * 0.8))
        {
            double targetOffset = playheadX - (viewportWidth * 0.2);
            // Cubic Ease Out approximation
            double delta = (targetOffset - currentOffset);
            double step = delta * 0.05; // 5% per frame for smooth follow

            if (Math.Abs(step) > 0.5)
            {
                scrollViewer.ScrollToHorizontalOffset(currentOffset + step);
            }
        }
    }

    private ScrollViewer? GetScrollViewer(DependencyObject depObj)
    {
        if (depObj is ScrollViewer viewer) return viewer;
        for (int i = 0; i < VisualTreeHelper.GetChildrenCount(depObj); i++)
        {
            var child = VisualTreeHelper.GetChild(depObj, i);
            var result = GetScrollViewer(child);
            if (result != null) return result;
        }
        return null;
    }

    private void SyncTimer_OnTick(object? sender, EventArgs e)
    {
        _syncTimer.Stop();
        _viewModel?.SyncTimelineCommand.Execute(null);
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        AttachViewModel(DataContext as TimelineViewModel);
        DataContextChanged += OnDataContextChanged;
        SyncPreviewToSelection(forceReload: true);
        DrawRuler();
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
        DrawRuler();
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

        if (e.PropertyName is nameof(TimelineViewModel.PixelsPerSecond) or nameof(TimelineViewModel.TotalDuration))
        {
            Dispatcher.Invoke(DrawRuler);
        }

        if (e.PropertyName == nameof(TimelineViewModel.SongSegments))
        {
            Dispatcher.Invoke(DrawRuler);
        }
    }

    private void DrawRuler()
    {
        if (_viewModel == null || _viewModel.TotalDuration <= 0) return;

        RulerCanvas.Children.Clear();
        double pps = _viewModel.PixelsPerSecond;
        double totalWidth = _viewModel.TotalDuration * pps;
        RulerCanvas.Width = totalWidth;

        // 1. Render Song Structure Background
        if (_viewModel.SongSegments != null)
        {
            foreach (var seg in _viewModel.SongSegments)
            {
                double x = seg.StartTime * pps;
                double w = seg.Duration * pps;

                var color = seg.Label.ToLower() switch
                {
                    "chorus" => (Brush)FindResource("AbletonAccent"),
                    "intro" or "outro" => (Brush)FindResource("AbletonTextDim"),
                    "verse" => (Brush)FindResource("AbletonBlue"),
                    _ => (Brush)FindResource("AbletonBorder")
                };

                var rect = new Border
                {
                    Width = w,
                    Height = 25,
                    Background = color,
                    Opacity = 0.15,
                    ToolTip = new ToolTip { Content = $"Song-Sektion: {seg.Label}\nZeit: {TimeSpan.FromSeconds(seg.StartTime):mm\\:ss} - {TimeSpan.FromSeconds(seg.EndTime):mm\\:ss}\nDauer: {seg.Duration:F1}s" }
                };
                Canvas.SetLeft(rect, x);
                RulerCanvas.Children.Add(rect);
            }
        }

        // 2. Render Ruler Marks
        double interval = 10.0;
        if (pps > 100) interval = 1.0;
        else if (pps > 50) interval = 5.0;
        else if (pps < 20) interval = 30.0;

        for (double t = 0; t <= _viewModel.TotalDuration; t += interval)
        {
            double x = t * pps;

            // Langer Strich + Text
            Line line = new Line
            {
                X1 = x,
                Y1 = 0,
                X2 = x,
                Y2 = 15,
                Stroke = (Brush)FindResource("AbletonTextDim"),
                StrokeThickness = 1
            };
            RulerCanvas.Children.Add(line);

            TextBlock txt = new TextBlock
            {
                Text = TimeSpan.FromSeconds(t).ToString(@"mm\:ss"),
                FontSize = 9,
                Foreground = (Brush)FindResource("AbletonTextDim"),
                Margin = new Thickness(x + 2, 10, 0, 0)
            };
            RulerCanvas.Children.Add(txt);

            // Kurze Zwischenstriche (Halbe Intervalle)
            if (interval > 1.0)
            {
                double halfX = (t + interval / 2.0) * pps;
                if (halfX <= totalWidth)
                {
                    Line subLine = new Line
                    {
                        X1 = halfX,
                        Y1 = 0,
                        X2 = halfX,
                        Y2 = 6,
                        Stroke = (Brush)FindResource("AbletonBorder"),
                        StrokeThickness = 0.5
                    };
                    RulerCanvas.Children.Add(subLine);
                }
            }
        }
    }

    // ══ Interactive Timeline Logic ══

    private bool _isDragging;
    private bool _isTrimmingLeft;
    private bool _isTrimmingRight;
    private Point _lastMousePosition;
    private TimelineEntryModel? _draggedEntry;

    private void Clip_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is TimelineEntryModel entry)
        {
            _draggedEntry = entry;
            _viewModel!.SelectedEntry = entry;
            _lastMousePosition = e.GetPosition(this);

            var hitPosition = e.GetPosition(element).X;
            if (hitPosition < 10) _isTrimmingLeft = true;
            else if (hitPosition > element.ActualWidth - 10) _isTrimmingRight = true;
            else _isDragging = true;

            element.CaptureMouse();
            e.Handled = true;
        }
    }

    private void Clip_MouseMove(object sender, MouseEventArgs e)
    {
        if ((_isDragging || _isTrimmingLeft || _isTrimmingRight) && _draggedEntry != null && _viewModel != null)
        {
            var currentPos = e.GetPosition(this);
            var deltaX = currentPos.X - _lastMousePosition.X;
            var deltaTime = deltaX / _viewModel.PixelsPerSecond;

            bool isSnapped = false;
            double snapRadius = 15.0 / _viewModel.PixelsPerSecond;

            if (_isDragging)
            {
                var newStart = _draggedEntry.StartTime + deltaTime;

                // Enhanced Multi-Trigger Snap
                foreach (var snapTime in _viewModel.SnapMarkers)
                {
                    if (Math.Abs(newStart - snapTime) < snapRadius)
                    {
                        newStart = snapTime;
                        isSnapped = true;
                        break;
                    }
                }

                var dur = _draggedEntry.Duration;
                _draggedEntry.StartTime = newStart;
                _draggedEntry.EndTime = newStart + dur;
            }
            else if (_isTrimmingLeft)
            {
                var newStart = _draggedEntry.StartTime + deltaTime;

                foreach (var snapTime in _viewModel.SnapMarkers)
                {
                    if (Math.Abs(newStart - snapTime) < snapRadius)
                    {
                        newStart = snapTime;
                        isSnapped = true;
                        break;
                    }
                }

                if (newStart < _draggedEntry.EndTime - 0.1)
                {
                    var actualDelta = newStart - _draggedEntry.StartTime;
                    _draggedEntry.StartTime = newStart;
                    _draggedEntry.ClipStart += actualDelta;
                }
            }
            else if (_isTrimmingRight)
            {
                var newEnd = _draggedEntry.EndTime + deltaTime;

                foreach (var snapTime in _viewModel.SnapMarkers)
                {
                    if (Math.Abs(newEnd - snapTime) < snapRadius)
                    {
                        newEnd = snapTime;
                        isSnapped = true;
                        break;
                    }
                }

                if (newEnd > _draggedEntry.StartTime + 0.1)
                {
                    _draggedEntry.EndTime = newEnd;
                }
            }

            // Visual Feedback
            if (sender is FrameworkElement fe)
            {
                var border = VisualTreeHelper.GetChild(fe, 0) as FrameworkElement;
                if (border != null)
                {
                    VisualStateManager.GoToElementState(border, isSnapped ? "Snapped" : "Normal", true);
                }
            }

            _draggedEntry.NotifyPositionChanged();
            _lastMousePosition = currentPos;
            _syncTimer.Stop();
            _syncTimer.Start();
            e.Handled = true;
        }
    }

    private void Clip_MouseUp(object sender, MouseButtonEventArgs e)
    {
        if (_draggedEntry != null)
        {
            if (sender is FrameworkElement element) element.ReleaseMouseCapture();
            _isDragging = _isTrimmingLeft = _isTrimmingRight = false;
            _draggedEntry = null;
            _syncTimer.Stop();
            _syncTimer.Start();
            e.Handled = true;

            // Hier könnte man ein Auto-Save oder Backend-Update triggern
            if (_viewModel != null)
            {
                _viewModel.StatusText = "Schnitt angepasst";
            }
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
        PreviewStatusText.Text = $"Bereit: {System.IO.Path.GetFileName(sourcePath)}";

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
        if (!_mediaOpened || _viewModel == null)
            return;

        // Sync ViewModel Playhead position (total timeline time)
        var relativePos = PreviewPlayer.Position.TotalSeconds - _loadedClipStart;
        if (relativePos >= 0)
        {
            _viewModel.SelectedTimelinePosition = _viewModel.SelectedEntry?.StartTime + relativePos ?? 0;
        }

        if (PreviewPlayer.Position.TotalSeconds >= _loadedClipEnd - 0.05)
        {
            PreviewPlayer.Pause();
            _playbackTimer.Stop();
            SeekToClipStart();
            PreviewStatusText.Text = "Preview beendet";
        }
    }

    private void TimelineGrid_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (_viewModel == null) return;

        var pos = e.GetPosition((IInputElement)sender);
        var time = pos.X / _viewModel.PixelsPerSecond;

        _viewModel.SelectedTimelinePosition = time;
        _syncTimer.Stop();
        _syncTimer.Start();

        // Wenn ein Clip an dieser Position existiert, sucht SyncPreviewToSelection 
        // automatisch den Clip und lädt ihn.
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
