using System.Windows;
using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>
/// Code-behind ist bewusst minimal: bezieht das ViewModel aus einem dedizierten
/// IServiceScope und verwaltet dessen Lebenszyklus sowie den Auto-Refresh-Timer.
/// </summary>
public partial class VramTelemetryView : UserControl
{
    private IServiceScope? _scope;

    public VramTelemetryView()
    {
        InitializeComponent();
        IsVisibleChanged += OnIsVisibleChanged;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (_scope == null)
        {
            _scope = Ioc.Default.GetRequiredService<IServiceScopeFactory>().CreateScope();
            DataContext = _scope.ServiceProvider.GetRequiredService<VramTelemetryViewModel>();
        }

        if (DataContext is VramTelemetryViewModel vm)
            vm.IsActive = IsVisible;
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is VramTelemetryViewModel vm)
        {
            vm.IsActive = false;
        }

        DataContext = null;
        _scope?.Dispose();
        _scope = null;
    }

    private void OnIsVisibleChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if (DataContext is VramTelemetryViewModel vm)
        {
            vm.IsActive = IsVisible;
        }
    }
}
