using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>AudioLibraryView — DataContext wird via Ioc.Default aufgelöst (kein XAML-Instantiierung).</summary>
public partial class AudioLibraryView : UserControl
{
    public AudioLibraryView()
    {
        InitializeComponent();
        // KORREKTUR: DataContext via DI auflösen, nicht über XAML <vm:AudioLibraryViewModel/>
        // XAML kann keinen Konstruktor mit Parametern aufrufen → Ioc.Default
        DataContext = Ioc.Default.GetRequiredService<AudioLibraryViewModel>();
    }
}
