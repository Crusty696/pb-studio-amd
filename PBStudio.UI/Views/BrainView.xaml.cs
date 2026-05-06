using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

public partial class BrainView : UserControl
{
    public BrainView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<BrainViewModel>();
    }
}
