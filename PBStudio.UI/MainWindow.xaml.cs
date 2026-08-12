using System.ComponentModel;
using System.Windows;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI;

/// <summary>
/// MainWindow Code-Behind. Minimal — Logik ist im MainViewModel.
/// </summary>
public partial class MainWindow : Window
{
    private readonly ILogger<MainWindow> _logger;
    private readonly MainWindowCloseGate _closeGate;

    // AP3.1: IApiClient-Parameter entfernt — wurde nur noch für das (entfernte)
    // verfrühte BeginShutdown() in OnClosing gebraucht.
    public MainWindow(
        MainViewModel viewModel,
        MainWindowCloseGate closeGate,
        ILogger<MainWindow> logger)
    {
        _logger = logger;
        _closeGate = closeGate;
        InitializeComponent();
        DataContext = viewModel;
        Closing += OnClosing;
        _logger.LogInformation("MainWindow initialisiert.");
    }

    private async void OnClosing(object? sender, CancelEventArgs e)
    {
        if (_closeGate.IsAuthorized)
            return;

        if (Application.Current is App app && app.IsFatalShutdownStarted)
        {
            _closeGate.AuthorizeWithoutSave();
            WeakReferenceMessenger.Default.Send(new AppShutdownMessage());
            return;
        }

        e.Cancel = true;
        var result = await _closeGate.TryAuthorizeAsync();
        if (result.InProgress)
            return;
        if (!result.Authorized)
        {
            _logger.LogError("Speichern vor dem Schließen fehlgeschlagen: {Reason}", result.ErrorMessage);
            MessageBox.Show(
                "PB Studio bleibt geöffnet: " + (result.ErrorMessage ?? "Speichern fehlgeschlagen."),
                "Speichern fehlgeschlagen",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
            return;
        }

        WeakReferenceMessenger.Default.Send(new AppShutdownMessage());
        Close();
    }
}
