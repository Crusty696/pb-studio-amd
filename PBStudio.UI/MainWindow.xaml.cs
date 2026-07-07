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
    private bool _shutdownStarted;

    // AP3.1: IApiClient-Parameter entfernt — wurde nur noch für das (entfernte)
    // verfrühte BeginShutdown() in OnClosing gebraucht.
    public MainWindow(MainViewModel viewModel, ILogger<MainWindow> logger)
    {
        _logger = logger;
        InitializeComponent();
        DataContext = viewModel;
        Closing += OnClosing;

        // T7-Fix (2026-05-28): Globales Klick-Protokoll-Logging für manuelle Benutzertests
        PreviewMouseLeftButtonDown += OnPreviewMouseLeftButtonDown;
        _logger.LogInformation("MainWindow Klick-Protokollierer erfolgreich initialisiert.");
    }

    private void OnPreviewMouseLeftButtonDown(object sender, System.Windows.Input.MouseButtonEventArgs e)
    {
        try
        {
            var source = e.OriginalSource as DependencyObject;
            if (source == null) return;

            string elementName = "Unbenannt";
            string elementType = source.GetType().Name;
            string autoId = "None";

            var current = source;
            while (current != null)
            {
                if (current is FrameworkElement fe)
                {
                    if (!string.IsNullOrEmpty(fe.Name))
                    {
                        elementName = fe.Name;
                    }
                    var aid = System.Windows.Automation.AutomationProperties.GetAutomationId(fe);
                    if (!string.IsNullOrEmpty(aid))
                    {
                        autoId = aid;
                    }

                    if (current is System.Windows.Controls.Button btn)
                    {
                        elementType = "Button";
                        elementName = btn.Content?.ToString() ?? elementName;
                        break;
                    }
                    else if (current is System.Windows.Controls.TabItem tab)
                    {
                        elementType = "TabItem";
                        elementName = tab.Header?.ToString() ?? elementName;
                        break;
                    }
                    else if (current is System.Windows.Controls.CheckBox cb)
                    {
                        elementType = "CheckBox";
                        elementName = cb.Content?.ToString() ?? cb.Name ?? elementName;
                        break;
                    }
                    else if (current is System.Windows.Controls.TextBox tb)
                    {
                        elementType = "TextBox";
                        break;
                    }
                }
                current = System.Windows.Media.VisualTreeHelper.GetParent(current);
            }

            var pos = e.GetPosition(this);
            
            // Log in standard wpf_app.log via _logger
            var logLine = $"[CLICK] X:{(int)pos.X}, Y:{(int)pos.Y} | Element: '{elementName}' | Type: {elementType} | AutoId: '{autoId}'";
            _logger.LogInformation(logLine);

            // Log in separate click_manual_wpf.log (korrekter 4-Ebenen-Pfad)
            var logPath = System.IO.Path.Combine(System.AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", "logs", "click_manual_wpf.log");
            var resolvedPath = System.IO.Path.GetFullPath(logPath);
            
            var dir = System.IO.Path.GetDirectoryName(resolvedPath);
            if (dir != null && !System.IO.Directory.Exists(dir))
            {
                System.IO.Directory.CreateDirectory(dir);
            }

            var timestamp = System.DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
            var fileLogLine = $"[{timestamp}] {logLine}";
            
            System.IO.File.AppendAllText(resolvedPath, fileLogLine + System.Environment.NewLine, System.Text.Encoding.UTF8);
        }
        catch (System.Exception ex)
        {
            _logger.LogWarning(ex, "Klick-Protokollierung fehlgeschlagen");
        }
    }

    private void OnClosing(object? sender, CancelEventArgs e)
    {
        if (_shutdownStarted)
            return;

        _shutdownStarted = true;
        WeakReferenceMessenger.Default.Send(new AppShutdownMessage());
        // AP3.1/K7-Nachfix (Audit 2026-06-10): BeginShutdown() hier entfernt —
        // OnClosing feuert VOR App.OnExit; der Cancel des Shutdown-Tokens hätte
        // den SaveProjectAsync-Call in OnExit weiterhin sofort abgebrochen
        // (Save-on-Exit wäre trotz K7-Fix tot geblieben). BeginShutdown läuft
        // jetzt ausschließlich in App.OnExit NACH dem Projekt-Save.
    }
}
