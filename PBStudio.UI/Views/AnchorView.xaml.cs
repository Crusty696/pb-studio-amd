using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>AnchorView — DataContext wird via Ioc.Default aufgelöst (kein XAML-Instantiierung).</summary>
public partial class AnchorView : UserControl
{
    public AnchorView()
    {
        InitializeComponent();
        // KORREKTUR: DataContext via DI auflösen, nicht über XAML <vm:AnchorViewModel/>
        // XAML kann keinen Konstruktor mit Parametern aufrufen → Ioc.Default
        DataContext = Ioc.Default.GetRequiredService<AnchorViewModel>();
    }
}
