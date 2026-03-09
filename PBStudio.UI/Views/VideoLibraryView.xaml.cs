using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

/// <summary>VideoLibraryView — DataContext wird via Ioc.Default aufgelöst (kein XAML-Instantiierung).</summary>
public partial class VideoLibraryView : UserControl
{
    public VideoLibraryView()
    {
        InitializeComponent();
        // KORREKTUR: DataContext via DI auflösen, nicht über XAML <vm:VideoLibraryViewModel/>
        // XAML kann keinen Konstruktor mit Parametern aufrufen → Ioc.Default
        DataContext = Ioc.Default.GetRequiredService<VideoLibraryViewModel>();
    }
}
