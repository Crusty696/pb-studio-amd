using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>AudioLibraryView — DataContext wird via Ioc.Default aufgelöst.</summary>
public partial class AudioLibraryView : UserControl
{
    public AudioLibraryView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<AudioLibraryViewModel>();
    }

    /// <summary>Multi-Select Sync: ListBox.SelectedItems -> VM.SelectedClips.</summary>
    private void AudioClipList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DataContext is AudioLibraryViewModel vm && sender is ListBox list)
            vm.UpdateSelectedClips(list.SelectedItems);
    }
}
