using System.Windows;
using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>
/// Code-Behind ist bewusst minimal: bezieht das ViewModel aus einem IServiceScope und
/// setzt dessen IsActive-Flag per Loaded/Unloaded.
/// </summary>
public partial class ModelManagerView : UserControl
{
    private IServiceScope? _scope;

    public ModelManagerView()
    {
        InitializeComponent();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (_scope == null)
        {
            _scope = Ioc.Default.GetRequiredService<IServiceScopeFactory>().CreateScope();
            DataContext = _scope.ServiceProvider.GetRequiredService<ModelManagerViewModel>();
        }

        if (DataContext is ModelManagerViewModel vm)
            vm.IsActive = true;
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is ModelManagerViewModel vm)
            vm.IsActive = false;

        DataContext = null;
        _scope?.Dispose();
        _scope = null;
    }
}
