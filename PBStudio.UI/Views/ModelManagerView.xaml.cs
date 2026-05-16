using System.Windows;
using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>
/// Code-Behind ist bewusst minimal: bezieht das ViewModel aus dem DI-Container und
/// setzt dessen IsActive-Flag per Loaded/Unloaded.
/// </summary>
public partial class ModelManagerView : UserControl
{
    public ModelManagerView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<ModelManagerViewModel>();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is ModelManagerViewModel vm)
            vm.IsActive = true;
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        if (DataContext is ModelManagerViewModel vm)
            vm.IsActive = false;
    }
}
