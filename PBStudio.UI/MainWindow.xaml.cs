using System.Windows;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI;

/// <summary>
/// MainWindow Code-Behind. Minimal — Logik ist im MainViewModel.
/// </summary>
public partial class MainWindow : Window
{
    public MainWindow(MainViewModel viewModel)
    {
        InitializeComponent();
        DataContext = viewModel;
    }
}
