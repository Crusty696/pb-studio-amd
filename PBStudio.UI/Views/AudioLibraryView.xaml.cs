using System.Windows;
using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>AudioLibraryView — DataContext wird via IServiceScope auflösung gehortet.</summary>
public partial class AudioLibraryView : UserControl
{
    private IServiceScope? _scope;

    public AudioLibraryView()
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
            var vm = _scope.ServiceProvider.GetRequiredService<AudioLibraryViewModel>();
            DataContext = vm;
            if (vm.LoadAudioClipsCommand.CanExecute(null))
            {
                vm.LoadAudioClipsCommand.Execute(null);
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
    private void AudioClipList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DataContext is AudioLibraryViewModel vm && sender is ListBox list)
            vm.UpdateSelectedClips(list.SelectedItems);
    }
}

