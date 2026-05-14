using System;
using System.Windows;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

public partial class LearningSessionDialog : Window
{
    private readonly LearningSessionViewModel _vm;

    public LearningSessionDialog(LearningSessionViewModel vm)
    {
        InitializeComponent();
        DataContext = vm;
        _vm = vm;

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

    private void OnPlay()
    {
        try { VideoPlayer.Play(); AudioPlayer.Play(); } catch { }
    }

    private void OnPause()
    {
        try { VideoPlayer.Pause(); AudioPlayer.Pause(); } catch { }
    }

    private void OnRestart()
    {
        try
        {
            VideoPlayer.Position = TimeSpan.Zero;
            AudioPlayer.Position = TimeSpan.FromSeconds(_vm.CurrentStartTime);
            VideoPlayer.Play();
            AudioPlayer.Play();
        }
        catch { }
    }

    private void OnDialogClosed(object? sender, EventArgs e)
    {
        _vm.RequestClose -= OnRequestClose;
        _vm.PlayRequested -= OnPlay;
        _vm.PauseRequested -= OnPause;
        _vm.RestartRequested -= OnRestart;
        _vm.Dispose();
        Closed -= OnDialogClosed;
    }
}
