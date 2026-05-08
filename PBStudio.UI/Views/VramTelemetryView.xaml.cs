using System.Windows;
using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>
/// Code-behind ist bewusst minimal: bezieht das ViewModel aus dem DI-Container und
/// schaltet dessen Auto-Refresh-Timer per IsActive-Flag, sobald das Control sichtbar
/// bzw. unsichtbar wird.
/// </summary>
public partial class VramTelemetryView : UserControl
{
    public VramTelemetryView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<VramTelemetryViewModel>();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is VramTelemetryViewModel vm)
            vm.IsActive = true;
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is VramTelemetryViewModel vm)
            vm.IsActive = false;
    }
}
