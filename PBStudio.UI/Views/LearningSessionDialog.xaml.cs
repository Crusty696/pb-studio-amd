using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

public partial class LearningSessionDialog : Window
{
    private readonly LearningSessionViewModel _vm;
    private readonly DispatcherTimer _cutTimer;
    private double _cutStartSeconds;
    private double _cutEndSeconds;

    public LearningSessionDialog(LearningSessionViewModel vm)
    {
        InitializeComponent();
        DataContext = vm;
        _vm = vm;
        _cutTimer = new DispatcherTimer(DispatcherPriority.Background)
        {
            Interval = TimeSpan.FromMilliseconds(50),
        };
        _cutTimer.Tick += OnCutTimerTick;

        // L-FE-7: Benannte Handler statt Lambdas + OnClosed-Unsubscribe.
        // Lambdas capturen `this` (Dialog) -> Dialog kann nicht GCd werden,
        // weil VM die Lambda-Closures haelt.
        _vm.RequestClose += OnRequestClose;
        _vm.PlayRequested += OnPlay;
        _vm.PauseRequested += OnPause;
        _vm.RestartRequested += OnRestart;
        Closed += OnDialogClosed;
    }

    private void OnRequestClose() => Close();

    private void OnPlay(double startSeconds, double endSeconds)
    {
        StartPlayback(startSeconds, endSeconds);
    }

    private void OnPause()
    {
        _cutTimer.Stop();
        try { VideoPlayer.Pause(); AudioPlayer.Pause(); } catch { }
    }

    private void OnRestart(double startSeconds, double endSeconds)
    {
        StartPlayback(startSeconds, endSeconds);
    }

    private void StartPlayback(double startSeconds, double endSeconds)
    {
        if (endSeconds <= startSeconds)
        {
            _vm.Status = "Ungültiger Vorschauzeitraum.";
            _vm.NotifyPlaybackCompleted();
            return;
        }

        _cutStartSeconds = Math.Max(0, startSeconds);
        _cutEndSeconds = endSeconds;
        var start = TimeSpan.FromSeconds(_cutStartSeconds);
        try
        {
            VideoPlayer.Position = start;
            AudioPlayer.Position = start;
            VideoPlayer.Play();
            AudioPlayer.Play();
            _cutTimer.Start();
        }
        catch (Exception ex)
        {
            _cutTimer.Stop();
            _vm.NotifyPlaybackCompleted();
            _vm.Status = $"Vorschau konnte nicht gestartet werden: {ex.Message}";
        }
    }

    private void OnMediaOpened(object sender, RoutedEventArgs e)
    {
        if (!_vm.IsPlaying || sender is not MediaElement player)
            return;

        try
        {
            player.Position = TimeSpan.FromSeconds(_cutStartSeconds);
            player.Play();
        }
        catch (Exception ex)
        {
            _cutTimer.Stop();
            _vm.NotifyPlaybackCompleted();
            _vm.Status = $"Vorschau konnte nicht fortgesetzt werden: {ex.Message}";
        }
    }

    private void OnMediaEnded(object sender, RoutedEventArgs e) =>
        StopPlaybackAtCutEnd();

    private void OnCutTimerTick(object? sender, EventArgs e)
    {
        if (!_vm.IsPlaying)
        {
            _cutTimer.Stop();
            return;
        }

        var end = TimeSpan.FromSeconds(_cutEndSeconds);
        if ((AudioPlayer.Source != null && AudioPlayer.Position >= end)
            || (VideoPlayer.Source != null && VideoPlayer.Position >= end))
        {
            StopPlaybackAtCutEnd();
        }
    }

    private void StopPlaybackAtCutEnd()
    {
        _cutTimer.Stop();
        var end = TimeSpan.FromSeconds(_cutEndSeconds);
        Exception? playbackError = null;
        try
        {
            VideoPlayer.Pause();
            AudioPlayer.Pause();
            VideoPlayer.Position = end;
            AudioPlayer.Position = end;
        }
        catch (Exception ex)
        {
            playbackError = ex;
        }
        _vm.NotifyPlaybackCompleted();
        if (playbackError != null)
            _vm.Status = $"Vorschau konnte nicht beendet werden: {playbackError.Message}";
    }

    private void OnDialogClosed(object? sender, EventArgs e)
    {
        _cutTimer.Stop();
        _cutTimer.Tick -= OnCutTimerTick;
        try { VideoPlayer.Stop(); AudioPlayer.Stop(); } catch { }
        _vm.RequestClose -= OnRequestClose;
        _vm.PlayRequested -= OnPlay;
        _vm.PauseRequested -= OnPause;
        _vm.RestartRequested -= OnRestart;
        _vm.Dispose();
        Closed -= OnDialogClosed;
    }
}
