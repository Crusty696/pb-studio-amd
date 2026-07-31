using System;
using System.ComponentModel;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using System.Windows.Media;
using System.Windows.Input;
using CommunityToolkit.Mvvm.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.ViewModels;
using PBStudio.UI.Helpers;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

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
    private bool _wasPlayingBeforeReload;

    private readonly RulerRenderer _rulerRenderer;
    private SnapEngine? _snapEngine;

    private bool _isDragging;
    private bool _isTrimmingLeft;
    private bool _isTrimmingRight;
    private Point _lastMousePosition;
    private TimelineEntryModel? _draggedEntry;

    // L-TI-2: Trim-Origin-Werte zum Zeitpunkt von MouseDown.
    // _dragStartX wird auch fuer Trim als Referenz benoetigt, weil Trim deltaX
    // gegen die Originalposition rechnet (nicht inkrementell wie Drag).
    private double _dragStartX;
    private double _originalStartTime;
    private double _originalEndTime;
    private double _originalClipStart;
    private const double MinClipDuration = 0.1;
    private const double FineKeyboardStepSeconds = 0.1;
    private const double CoarseKeyboardStepSeconds = 1.0;

    private IServiceScope? _scope;

    public TimelineView()
    {
        InitializeComponent();

        _rulerRenderer = new RulerRenderer(RulerCanvas);

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
    }

    // B5-Fix (2026-05-19): _lastScrollX war never-read (CS0414). Entfernt.
    private void OnCompositionTargetRendering(object? sender, EventArgs e)
    {
        if (_viewModel == null || !_mediaOpened || _viewModel.SelectedTimelinePosition <= 0) return;

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
        if (_scope == null)
        {
            _scope = Ioc.Default.GetRequiredService<IServiceScopeFactory>().CreateScope();
            DataContext = _scope.ServiceProvider.GetRequiredService<TimelineViewModel>();
        }

        AttachViewModel(DataContext as TimelineViewModel);
        DataContextChanged += OnDataContextChanged;
        SyncPreviewToSelection(forceReload: true);
        DrawRuler();

        // C1/POWER: High-frequency render loop for smooth playhead tracking (OnLoaded registrieren)
        CompositionTarget.Rendering += OnCompositionTargetRendering;
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        // L-FE-15 (HIGH): 60Hz CompositionTarget.Rendering ist ein STATISCHES
        // WPF-Event - jeder Tab-Wechsel erzeugt eine neue TimelineView-Instanz,
        // deren Lambda im statischen Event verbleibt. Folge: N tote Listener
        // tickern 60x pro Sekunde + halten View+VM gegen GC = CPU-Drain +
        // Memory-Leak (User-Symptom: App-CPU steigt nach Tab-Wechsel).
        CompositionTarget.Rendering -= OnCompositionTargetRendering;
        DataContextChanged -= OnDataContextChanged;
        AttachViewModel(null);
        _playbackTimer.Stop();
        PreviewPlayer.Stop();
        PreviewPlayer.Source = null;

        DataContext = null;
        _scope?.Dispose();
        _scope = null;
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
        {
            _viewModel.PropertyChanged -= ViewModel_OnPropertyChanged;
            _viewModel.PreviewReady -= OnPreviewReady;
        }

        _viewModel = next;

        if (_viewModel != null)
        {
            _viewModel.PropertyChanged += ViewModel_OnPropertyChanged;
            _viewModel.PreviewReady += OnPreviewReady;
        }
    }

    private void OnPreviewReady(string previewPath)
    {
        Dispatcher.Invoke(() =>
        {
            try
            {
                _playbackTimer.Stop();
                PreviewPlayer.Stop();
                PreviewPlayer.Source = new Uri(previewPath, UriKind.Absolute);
                _loadedSourcePath = previewPath;
                _loadedClipStart = 0.0;
                _loadedClipEnd = 0.0;
                _mediaOpened = false;
                PreviewEmptyText.Visibility = Visibility.Collapsed;
                PreviewPlayer.Play();
            }
            catch (Exception ex)
            {
                PreviewStatusText.Text = "Preview-Load fehlgeschlagen: " + ex.Message;
            }
        });
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

        // 1. Render Song Structure Background (Keep existing behavior for segments)
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

        // 2. Use RulerRenderer for marks (Procedural/Optimized)
        // For simplicity in this brownfield context, we still add to Canvas but use the Renderer logic
        var textBrush = (Brush)FindResource("AbletonTextDim");
        var lineBrush = (Brush)FindResource("AbletonBorder");
        
        // We'll use a DrawingVisual for the marks to improve performance
        var visual = new DrawingVisual();
        using (var dc = visual.RenderOpen())
        {
            _rulerRenderer.Render(dc, _viewModel.TotalDuration, pps, totalWidth, textBrush, lineBrush);
        }
        
        // Host the visual in a simple element
        var host = new VisualHost(visual);
        RulerCanvas.Children.Add(host);
    }

    // Helper to host DrawingVisual in Canvas
    public class VisualHost : FrameworkElement
    {
        private readonly Visual _visual;
        public VisualHost(Visual visual) => _visual = visual;
        protected override int VisualChildrenCount => 1;
        protected override Visual GetVisualChild(int index) => _visual;
    }

    private void Clip_MouseDown(object sender, MouseButtonEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is TimelineEntryModel entry)
        {
            element.Focus();
            _draggedEntry = entry;
            _viewModel!.SelectedEntry = entry;
            _lastMousePosition = e.GetPosition(this);

            var hitPosition = e.GetPosition(element).X;
            if (hitPosition < 10) _isTrimmingLeft = true;
            else if (hitPosition > element.ActualWidth - 10) _isTrimmingRight = true;
            else _isDragging = true;

            // L-TI-2: Trim-Origin festhalten (deltaX gegen Original, nicht inkrementell)
            if (_isTrimmingLeft || _isTrimmingRight)
            {
                _dragStartX = _lastMousePosition.X;
                _originalStartTime = entry.StartTime;
                _originalEndTime = entry.EndTime;
                _originalClipStart = entry.ClipStart;
            }

            element.CaptureMouse();
            e.Handled = true;
        }
    }

    private void Clip_GotKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (sender is FrameworkElement element
            && element.DataContext is TimelineEntryModel entry
            && _viewModel != null)
        {
            _viewModel.SelectedEntry = entry;
            VisualStateManager.GoToElementState(element, "Selected", true);
        }
    }

    private static void Clip_LostKeyboardFocus(object sender, KeyboardFocusChangedEventArgs e)
    {
        if (sender is FrameworkElement element)
            VisualStateManager.GoToElementState(element, "Normal", true);
    }

    private void Clip_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key is not (Key.Enter or Key.Space)
            || sender is not FrameworkElement element
            || element.DataContext is not TimelineEntryModel entry
            || _viewModel == null)
        {
            return;
        }

        _viewModel.SelectedEntry = entry;
        e.Handled = true;
    }

    private void TimelineView_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (_viewModel == null
            || e.OriginalSource is TextBox or Slider
            || !IsTimelineKeyboardTarget(e.OriginalSource as DependencyObject))
            return;

        var key = e.Key == Key.System ? e.SystemKey : e.Key;

        if (key == Key.Delete)
        {
            _viewModel.RejectUnsafeTimelineRemoval();
            e.Handled = true;
            return;
        }

        if (key is Key.Up or Key.Down)
        {
            var command = key == Key.Up
                ? _viewModel.PreviousCutCommand
                : _viewModel.NextCutCommand;
            if (command.CanExecute(null))
            {
                command.Execute(null);
                QueueFocusSelectedEntry();
                e.Handled = true;
            }
            return;
        }

        if (key is Key.Home or Key.End)
        {
            e.Handled = key == Key.Home
                ? _viewModel.SelectFirstCut()
                : _viewModel.SelectLastCut();
            if (e.Handled)
                QueueFocusSelectedEntry();
            return;
        }

        if (key is not (Key.Left or Key.Right))
            return;

        var modifiers = Keyboard.Modifiers;
        var step = modifiers.HasFlag(ModifierKeys.Shift)
            ? CoarseKeyboardStepSeconds
            : FineKeyboardStepSeconds;
        var delta = key == Key.Left ? -step : step;
        var control = modifiers.HasFlag(ModifierKeys.Control);
        var alt = modifiers.HasFlag(ModifierKeys.Alt);
        bool changed;

        if (control && alt)
        {
            changed = _viewModel.TrimSelectedCutEndBy(delta);
        }
        else if (alt)
        {
            changed = _viewModel.TrimSelectedCutStartBy(delta);
        }
        else if (control)
        {
            changed = _viewModel.NudgeSelectedCutBy(delta);
        }
        else
        {
            changed = _viewModel.ScrubTimelineBy(delta);
        }

        if (changed && (control || alt))
        {
            _syncTimer.Stop();
            _syncTimer.Start();
        }
        e.Handled = true;
    }

    private bool IsTimelineKeyboardTarget(DependencyObject? source)
    {
        if (ReferenceEquals(source, this))
            return true;

        var current = source;
        while (current != null && !ReferenceEquals(current, this))
        {
            if (ReferenceEquals(current, TimelineSummaryList)
                || ReferenceEquals(current, LanesScrollViewer))
            {
                return true;
            }
            current = VisualTreeHelper.GetParent(current);
        }
        return false;
    }

    private void QueueFocusSelectedEntry()
    {
        Dispatcher.BeginInvoke(DispatcherPriority.Input, new Action(() =>
        {
            var selected = _viewModel?.SelectedEntry;
            if (selected == null)
                return;

            if (TimelineSummaryList.IsKeyboardFocusWithin)
            {
                TimelineSummaryList.ScrollIntoView(selected);
                TimelineSummaryList.UpdateLayout();
                if (TimelineSummaryList.ItemContainerGenerator.ContainerFromItem(selected)
                    is ListViewItem item)
                {
                    item.Focus();
                }
                return;
            }

            if (LanesScrollViewer.IsKeyboardFocusWithin)
                FocusClipElement(TimelineItemsControl, selected);
        }));
    }

    private static bool FocusClipElement(
        DependencyObject root,
        TimelineEntryModel selected)
    {
        for (var index = 0; index < VisualTreeHelper.GetChildrenCount(root); index++)
        {
            var child = VisualTreeHelper.GetChild(root, index);
            if (child is FrameworkElement
                {
                    Name: "ClipBorder",
                    DataContext: TimelineEntryModel entry
                } element
                && ReferenceEquals(entry, selected))
            {
                element.BringIntoView();
                element.Focus();
                return true;
            }

            if (FocusClipElement(child, selected))
                return true;
        }
        return false;
    }

    private void Clip_MouseMove(object sender, MouseEventArgs e)
    {
        if ((_isDragging || _isTrimmingLeft || _isTrimmingRight) && _draggedEntry != null && _viewModel != null)
        {
            var currentPos = e.GetPosition(this);
            var deltaX = currentPos.X - _lastMousePosition.X;
            var deltaTime = deltaX / _viewModel.PixelsPerSecond;

            bool isSnapped = false;
            double snapTime = 0;

            // Initialize SnapEngine on demand
            _snapEngine ??= new SnapEngine(8.0, _viewModel.PixelsPerSecond);

            if (_isDragging)
            {
                var newStart = _draggedEntry.StartTime + deltaTime;

                // Check for SHIFT override
                if (Keyboard.Modifiers != ModifierKeys.Shift)
                {
                    var allSnapPoints = GetAvailableSnapPoints();
                    var snapped = _snapEngine.FindSnapPoint(newStart, allSnapPoints);
                    if (snapped != null)
                    {
                        newStart = snapped.Time;
                        snapTime = snapped.Time;
                        isSnapped = true;
                    }
                }

                var dur = _draggedEntry.Duration;
                // NEW: clamp against neighbour edges so we can't overlap (V1 lane).
                newStart = ClampStartToNeighbours(_draggedEntry, newStart, dur);

                _draggedEntry.StartTime = newStart;
                _draggedEntry.EndTime = newStart + dur;
            }
            // L-TI-2: Trim-Left — bewegt die linke Kante. EndTime bleibt fix,
            // StartTime + ClipStart (source-offset) shiften synchron um deltaSec.
            // Damit zeigt der Clip nicht ploetzlich neues Source-Material — er
            // wird nur gekuerzt/verlaengert vom Start-Ende.
            else if (_isTrimmingLeft)
            {
                var totalDeltaX = currentPos.X - _dragStartX;
                var deltaSec = totalDeltaX / _viewModel.PixelsPerSecond;

                var newStart = _originalStartTime + deltaSec;
                var newClipStart = _originalClipStart + deltaSec;

                // SHIFT deaktiviert Snap (gleiche Konvention wie Drag)
                if (Keyboard.Modifiers != ModifierKeys.Shift)
                {
                    var allSnapPoints = GetAvailableSnapPoints();
                    var snapped = _snapEngine.FindSnapPoint(newStart, allSnapPoints);
                    if (snapped != null)
                    {
                        var snapDelta = snapped.Time - newStart;
                        newStart = snapped.Time;
                        newClipStart += snapDelta;
                        snapTime = snapped.Time;
                        isSnapped = true;
                    }
                }

                // Constraints: StartTime >= 0, min Dauer, Nachbar-Grenzen
                if (newStart < 0)
                {
                    newStart = 0;
                }
                if (_originalEndTime - newStart < MinClipDuration)
                {
                    newStart = _originalEndTime - MinClipDuration;
                }

                // Nachbar-Clamping vornehmen
                newStart = Math.Max(ClampStartToNeighbours(_draggedEntry, newStart, _originalEndTime - newStart), newStart);

                // ClipStart-Limitierung: darf nicht kleiner als 0 werden (sonst wuerden wir vor den Videoanfang trimmen)
                var actualDelta = newStart - _originalStartTime;
                var finalClipStart = _originalClipStart + actualDelta;
                if (finalClipStart < 0)
                {
                    finalClipStart = 0;
                    newStart = _originalStartTime - _originalClipStart;
                }

                _draggedEntry.StartTime = newStart;
                _draggedEntry.EndTime = _originalEndTime;
                _draggedEntry.ClipStart = finalClipStart;
            }
            // L-TI-2: Trim-Right — bewegt die rechte Kante. StartTime + ClipStart
            // bleiben fix, nur EndTime aendert sich (= Duration aendert sich).
            else if (_isTrimmingRight)
            {
                var totalDeltaX = currentPos.X - _dragStartX;
                var deltaSec = totalDeltaX / _viewModel.PixelsPerSecond;

                var newEnd = _originalEndTime + deltaSec;

                if (Keyboard.Modifiers != ModifierKeys.Shift)
                {
                    var allSnapPoints = GetAvailableSnapPoints();
                    var snapped = _snapEngine.FindSnapPoint(newEnd, allSnapPoints);
                    if (snapped != null)
                    {
                        newEnd = snapped.Time;
                        snapTime = snapped.Time;
                        isSnapped = true;
                    }
                }

                // Min-Dauer enforce: EndTime - StartTime >= MIN
                if (newEnd - _originalStartTime < MinClipDuration)
                    newEnd = _originalStartTime + MinClipDuration;

                // Clamp end so we don't overlap the next clip.
                if (_viewModel != null)
                {
                    double maxEnd = double.PositiveInfinity;
                    foreach (var other in _viewModel.TimelineEntries)
                    {
                        if (ReferenceEquals(other, _draggedEntry)) continue;
                        if (other.StartTime >= _draggedEntry.StartTime + 0.0001 && other.StartTime < maxEnd)
                            maxEnd = other.StartTime;
                    }
                    if (newEnd > maxEnd) newEnd = maxEnd;
                }
                _draggedEntry.EndTime = newEnd;
            }

            // Visual Feedback: Snap Line
            // B5-Fix (2026-05-19): CS8602 Nullable deref von _viewModel.PixelsPerSecond — null-check ergaenzt.
            if (isSnapped && _viewModel != null)
            {
                SnapLine.Visibility = Visibility.Visible;
                SnapLineTransform.X = snapTime * _viewModel.PixelsPerSecond;
            }
            else
            {
                SnapLine.Visibility = Visibility.Collapsed;
            }

            // Visual Feedback: Clip State
            if (sender is FrameworkElement fe)
            {
                var border = fe.DataContext is TimelineEntryModel ? fe : VisualTreeHelper.GetChild(fe, 0) as FrameworkElement;
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

    private IEnumerable<SnapPoint> GetAvailableSnapPoints()
    {
        if (_viewModel == null) yield break;

        // 1. Beats & Onsets
        if (_viewModel.BeatMarkers != null)
            foreach (var b in _viewModel.BeatMarkers) yield return new SnapPoint(b, SnapPointType.Beat);

        if (_viewModel.SnapMarkers != null)
            foreach (var s in _viewModel.SnapMarkers) yield return new SnapPoint(s, SnapPointType.Onset);

        // 2. Playhead
        yield return new SnapPoint(_viewModel.SelectedTimelinePosition, SnapPointType.Playhead);

        // 3. Other Clip Edges
        foreach (var entry in _viewModel.TimelineEntries)
        {
            if (entry == _draggedEntry) continue;
            yield return new SnapPoint(entry.StartTime, SnapPointType.ClipEdge);
            yield return new SnapPoint(entry.EndTime, SnapPointType.ClipEdge);
        }
    }

    /// <summary>
    /// Clamps `desiredStart` so the dragged clip doesn't overlap the immediate
    /// predecessor or successor in the chronological order. Returns the clamped
    /// start time. Successor.EndTime is unchanged by drag (we only move whole clip).
    /// </summary>
    private double ClampStartToNeighbours(TimelineEntryModel dragged, double desiredStart, double duration)
    {
        if (_viewModel == null) return desiredStart;

        TimelineEntryModel? prev = null, next = null;
        foreach (var e in _viewModel.TimelineEntries)
        {
            if (ReferenceEquals(e, dragged)) continue;
            if (e.EndTime <= dragged.StartTime + 0.0001)
            {
                if (prev == null || e.EndTime > prev.EndTime) prev = e;
            }
            else if (e.StartTime >= dragged.EndTime - 0.0001)
            {
                if (next == null || e.StartTime < next.StartTime) next = e;
            }
        }

        double minStart = prev?.EndTime ?? 0.0;
        double maxStart = next != null ? next.StartTime - duration : double.PositiveInfinity;
        return Math.Max(minStart, Math.Min(maxStart, desiredStart));
    }

    /// <summary>
    /// Contiguous mode: after a drag, snap each clip's StartTime so it touches the
    /// predecessor's EndTime (cut[i].StartTime == cut[i-1].EndTime), preserving
    /// each clip's Duration. Idempotent.
    /// </summary>
    private void CloseGapsInContiguousMode()
    {
        if (_viewModel == null || _viewModel.TimelineEntries.Count < 2) return;

        for (int i = 1; i < _viewModel.TimelineEntries.Count; i++)
        {
            var prev = _viewModel.TimelineEntries[i - 1];
            var curr = _viewModel.TimelineEntries[i];
            double dur = curr.Duration;
            if (Math.Abs(curr.StartTime - prev.EndTime) > 0.001)
            {
                curr.StartTime = prev.EndTime;
                curr.EndTime = prev.EndTime + dur;
                curr.NotifyPositionChanged();
            }
        }
    }

    private void Clip_MouseUp(object sender, MouseButtonEventArgs e)
    {
        if (_draggedEntry != null)
        {
            if (sender is FrameworkElement element) element.ReleaseMouseCapture();
            bool wasDragging = _isDragging;
            _isDragging = _isTrimmingLeft = _isTrimmingRight = false;
            _draggedEntry = null;
            _syncTimer.Stop();
            _syncTimer.Start();
            e.Handled = true;

            // Hier könnte man ein Auto-Save oder Backend-Update triggern
            if (_viewModel != null)
            {
                _viewModel.StatusText = "Schnitt angepasst";

                // Audit L-TI-4: nach Drag-Commit Collection-Index = Zeit-Reihenfolge wiederherstellen
                // (sonst NextCut/PreviousCut + Render chronologisch verworren).
                if (wasDragging)
                {
                    _viewModel.SortEntriesByTime();
                    CloseGapsInContiguousMode();
                }
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
        if (!LocalMediaPathPolicy.TryCreateFileUri(sourcePath, out var sourceUri))
        {
            ResetPreview("Preview-Pfad ist keine freigegebene lokale Datei");
            return;
        }
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
            PreviewPlayer.Source = sourceUri;
            return;
        }

        // B5-Fix/Playback: Während der aktive Playback-Timer läuft, treibt der Player den Playhead.
        // Ein automatischer SeekToClipStart() währenddessen würde zum Zurückspringen & Stottern führen.
        if (_mediaOpened && !_playbackTimer.IsEnabled)
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
            TimelineEntryModel? nextEntry = null;
            if (_viewModel.SelectedEntry != null)
            {
                var sorted = new System.Collections.Generic.List<TimelineEntryModel>(_viewModel.TimelineEntries);
                sorted.Sort((a, b) => a.StartTime.CompareTo(b.StartTime));
                
                int index = sorted.IndexOf(_viewModel.SelectedEntry);
                if (index >= 0 && index < sorted.Count - 1)
                {
                    nextEntry = sorted[index + 1];
                }
            }

            if (nextEntry != null)
            {
                _wasPlayingBeforeReload = true;
                _viewModel.SelectedEntry = nextEntry;
                PreviewStatusText.Text = "Lade nächsten Clip...";
            }
            else
            {
                PreviewPlayer.Pause();
                _playbackTimer.Stop();
                SeekToClipStart();
                PreviewStatusText.Text = "Preview beendet";
            }
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

        if (_wasPlayingBeforeReload)
        {
            _wasPlayingBeforeReload = false;
            PreviewPlayer.Play();
            _playbackTimer.Start();
            PreviewStatusText.Text = "Preview läuft";
        }
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

        _wasPlayingBeforeReload = false;
        PreviewPlayer.Pause();
        _playbackTimer.Stop();
        PreviewStatusText.Text = "Preview pausiert";
    }

    private void StopPreview_Click(object sender, RoutedEventArgs e)
    {
        if (!_mediaOpened)
            return;

        _wasPlayingBeforeReload = false;
        PreviewPlayer.Stop();
        _playbackTimer.Stop();
        SeekToClipStart();
        PreviewStatusText.Text = "Preview gestoppt";
    }

    /// <summary>
    /// R-Brain-09: Lazy-Load des /brain/explain Tooltips beim Hover ueber den
    /// Confidence-Balken. Dieser Code-Behind-Handler ruft nur die VM-Methode auf —
    /// die eigentliche Logik (HTTP-Call, Cache, Format) lebt im TimelineViewModel.
    /// </summary>
    private void ConfidenceBar_ToolTipOpening(object sender, ToolTipEventArgs e)
    {
        if (sender is FrameworkElement fe
            && fe.DataContext is TimelineEntryModel entry
            && _viewModel != null)
        {
            // Fire-and-forget: das Binding {Binding BrainExplainTooltip} aktualisiert
            // sich von selbst, sobald die VM die Property gesetzt hat.
            _ = _viewModel.LoadBrainExplainAsync(entry);
        }
    }
}
