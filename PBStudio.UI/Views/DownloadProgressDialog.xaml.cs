using System.Windows;

namespace PBStudio.UI.Views;

/// <summary>
/// Code-Behind: minimal. Cancel-Klick laesst das ViewModel-Command laufen
/// (Cancel-Event setzt CancellationToken im Parent-VM), Close beendet den Dialog.
/// </summary>
public partial class DownloadProgressDialog : Window
{
    public DownloadProgressDialog()
    {
        InitializeComponent();
    }

    private void OnCloseClicked(object sender, RoutedEventArgs e)
    {
        DialogResult = true;
        Close();
    }
}
