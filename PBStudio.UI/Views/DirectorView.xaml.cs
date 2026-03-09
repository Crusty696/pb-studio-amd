using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>DirectorView — DataContext wird via Ioc.Default aufgelöst (kein XAML-Instantiierung).</summary>
public partial class DirectorView : UserControl
{
    public DirectorView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<DirectorViewModel>();
    }

    private void VideoClips_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DataContext is DirectorViewModel vm)
        {
            vm.UpdateSelectedCount();
        }
    }
}
