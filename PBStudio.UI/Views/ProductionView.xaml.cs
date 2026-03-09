using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>ProductionView — DataContext wird via Ioc.Default aufgelöst (kein XAML-Instantiierung).</summary>
public partial class ProductionView : UserControl
{
    public ProductionView()
    {
        InitializeComponent();
        // KORREKTUR: DataContext via DI auflösen, nicht über XAML <vm:ProductionViewModel/>
        // XAML kann keinen Konstruktor mit Parametern aufrufen → Ioc.Default
        DataContext = Ioc.Default.GetRequiredService<ProductionViewModel>();
    }
}
