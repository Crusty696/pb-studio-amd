using System.ComponentModel;
using System.Windows;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI;

/// <summary>
/// MainWindow Code-Behind. Minimal — Logik ist im MainViewModel.
/// </summary>
public partial class MainWindow : Window
{
    private readonly IApiClient _api;
    private bool _shutdownStarted;

    public MainWindow(MainViewModel viewModel, IApiClient api)
    {
        _api = api;
        InitializeComponent();
        DataContext = viewModel;
        Closing += OnClosing;
    }

    private void OnClosing(object? sender, CancelEventArgs e)
    {
        if (_shutdownStarted)
            return;

        _shutdownStarted = true;
        WeakReferenceMessenger.Default.Send(new AppShutdownMessage());
        _api.BeginShutdown();
    }
}
