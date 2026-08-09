using System.Collections.Specialized;
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
    private VideoLibraryViewModel? _viewModel;
    private bool _syncingSelection;

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
            _viewModel = vm;
            vm.SelectedClips.CollectionChanged += OnSelectedClipsChanged;
            DataContext = vm;
            if (vm.LoadClipsCommand.CanExecute(null))
            {
                vm.LoadClipsCommand.Execute(null);
            }
        }
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        if (_viewModel != null)
            _viewModel.SelectedClips.CollectionChanged -= OnSelectedClipsChanged;
        _viewModel = null;
        DataContext = null;
        _scope?.Dispose();
        _scope = null;
    }

    /// <summary>Multi-Select Sync: ListBox.SelectedItems -> VM.SelectedClips.</summary>
    private void VideoClipList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_syncingSelection)
            return;

        if (DataContext is VideoLibraryViewModel vm && sender is ListBox list)
        {
            _syncingSelection = true;
            try
            {
                vm.UpdateSelectedClips(list.SelectedItems);
            }
            finally
            {
                _syncingSelection = false;
            }
        }
    }

    private void OnSelectedClipsChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        if (_syncingSelection || _viewModel == null)
            return;

        _syncingSelection = true;
        try
        {
            var selectedIds = _viewModel.SelectedClips.Select(clip => clip.Id).ToHashSet();
            for (var index = VideoClipList.SelectedItems.Count - 1; index >= 0; index--)
            {
                if (VideoClipList.SelectedItems[index] is not PBStudio.UI.Models.VideoClipModel clip
                    || !selectedIds.Contains(clip.Id))
                {
                    VideoClipList.SelectedItems.RemoveAt(index);
                }
            }

            foreach (var clip in _viewModel.SelectedClips)
            {
                if (!VideoClipList.SelectedItems.Contains(clip))
                    VideoClipList.SelectedItems.Add(clip);
            }
        }
        finally
        {
            _syncingSelection = false;
        }
    }
}

