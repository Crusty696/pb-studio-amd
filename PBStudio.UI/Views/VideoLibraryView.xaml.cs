using System.Windows;
using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>VideoLibraryView — DataContext wird via IServiceScope auflösung gehortet.</summary>
public partial class VideoLibraryView : UserControl
{
    private IServiceScope? _scope;

    public VideoLibraryView()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (_scope == null)
        {
            _scope = Ioc.Default.GetRequiredService<IServiceScopeFactory>().CreateScope();
            var vm = _scope.ServiceProvider.GetRequiredService<VideoLibraryViewModel>();
            DataContext = vm;
            if (vm.LoadClipsCommand.CanExecute(null))
            {
                vm.LoadClipsCommand.Execute(null);
            }
        }
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        DataContext = null;
        _scope?.Dispose();
        _scope = null;
    }

    /// <summary>Multi-Select Sync: ListBox.SelectedItems -> VM.SelectedClips.</summary>
    private void VideoClipList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DataContext is VideoLibraryViewModel vm && sender is ListBox list)
            vm.UpdateSelectedClips(list.SelectedItems);
    }
}

