using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>VideoLibraryView — DataContext wird via Ioc.Default aufgelöst.</summary>
public partial class VideoLibraryView : UserControl
{
    public VideoLibraryView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<VideoLibraryViewModel>();
    }

    /// <summary>Multi-Select Sync: ListBox.SelectedItems -> VM.SelectedClips.</summary>
    private void VideoClipList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DataContext is VideoLibraryViewModel vm && sender is ListBox list)
            vm.UpdateSelectedClips(list.SelectedItems);
    }
}
