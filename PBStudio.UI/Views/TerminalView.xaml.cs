using System.Windows.Controls;
using CommunityToolkit.Mvvm.DependencyInjection;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Views;

public partial class TerminalView : UserControl
{
    public TerminalView()
    {
        InitializeComponent();
        DataContext = Ioc.Default.GetRequiredService<TerminalViewModel>();
    }

    private void TxtLog_TextChanged(object sender, TextChangedEventArgs e)
    {
        TxtLog.ScrollToEnd();
    }
}
