using System.Windows;
using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>DirectorView — DataContext wird via IServiceScope aufgelöst.</summary>
public partial class DirectorView : UserControl
{
    private IServiceScope? _scope;

    public DirectorView()
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
            DataContext = _scope.ServiceProvider.GetRequiredService<DirectorViewModel>();
        }
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        DataContext = null;
        _scope?.Dispose();
        _scope = null;
    }

    private void VideoClips_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DataContext is DirectorViewModel vm)
        {
            vm.UpdateSelectedCount();
        }
    }

    private void VideoClipCheckBox_Changed(object sender, System.Windows.RoutedEventArgs e)
    {
        if (DataContext is DirectorViewModel vm)
        {
            vm.UpdateSelectedCount();
        }
    }
}
