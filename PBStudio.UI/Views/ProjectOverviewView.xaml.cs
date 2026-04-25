using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>Code-behind für das neue Projekt-Dashboard.</summary>
public partial class ProjectOverviewView : UserControl
{
    public ProjectOverviewView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<ProjectOverviewViewModel>();
    }
}
