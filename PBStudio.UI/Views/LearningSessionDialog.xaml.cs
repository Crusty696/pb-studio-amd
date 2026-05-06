using System.Windows;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

public partial class LearningSessionDialog : Window
{
    public LearningSessionDialog(LearningSessionViewModel vm)
    {
        InitializeComponent();
        DataContext = vm;
        vm.RequestClose += () => Close();
        vm.PlayRequested += () => { try { VideoPlayer.Play(); AudioPlayer.Play(); } catch { } };
        vm.PauseRequested += () => { try { VideoPlayer.Pause(); AudioPlayer.Pause(); } catch { } };
        vm.RestartRequested += () =>
        {
            try
            {
                VideoPlayer.Position = System.TimeSpan.Zero;
                AudioPlayer.Position = System.TimeSpan.FromSeconds(vm.CurrentStartTime);
                VideoPlayer.Play(); AudioPlayer.Play();
            }
            catch { }
        };
    }
}
