using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>TimelineView — DataContext wird via Ioc.Default aufgelöst (kein XAML-Instantiierung).</summary>
public partial class TimelineView : UserControl
{
    public TimelineView()
    {
        InitializeComponent();
        // KORREKTUR: DataContext via DI auflösen, nicht über XAML <vm:TimelineViewModel/>
        // XAML kann keinen Konstruktor mit Parametern aufrufen → Ioc.Default
        DataContext = Ioc.Default.GetRequiredService<TimelineViewModel>();
    }
}
