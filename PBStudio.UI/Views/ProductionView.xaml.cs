using System.Windows;
using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>ProductionView — DataContext wird via IServiceScope aufgelöst.</summary>
public partial class ProductionView : UserControl
{
    private IServiceScope? _scope;

    public ProductionView()
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
            DataContext = _scope.ServiceProvider.GetRequiredService<ProductionViewModel>();
        }
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        DataContext = null;
        _scope?.Dispose();
        _scope = null;
    }
}
