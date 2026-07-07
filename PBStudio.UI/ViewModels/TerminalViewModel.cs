using System;
using System.Text;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Services;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.ViewModels;

public partial class TerminalViewModel : ObservableObject, IDisposable
{
    private readonly SSEClient _sse;
    private readonly StringBuilder _logBuilder = new();
    private const int MaxLogLength = 100000; // Schutz vor Memory-Bloat (max 100k Zeichen)

    [ObservableProperty]
    private string _logContent = "";

    public TerminalViewModel(SSEClient sse)
    {
        _sse = sse;
        _sse.LogReceived += OnLogReceived;
        
        WeakReferenceMessenger.Default.Register<WpfLogMessage>(this, (r, m) =>
        {
            AppendLog(m.Level, m.Message);
        });

        // Initial-Meldung im Terminal
        AppendLog("SYSTEM", "Terminal initialisiert. Warte auf Logs...");
    }

    private void OnLogReceived(object? sender, LogEventArgs e)
    {
        AppendLog(e.Level, e.Message);
    }

    private void AppendLog(string level, string message)
    {
        _ = App.Current.Dispatcher.InvokeAsync(() =>
        {
            var timestamp = DateTime.Now.ToString("HH:mm:ss");
            var line = $"[{timestamp}] [{level.ToUpper()}] {message}\n";

            // Schutz vor Überlauf
            if (_logBuilder.Length + line.Length > MaxLogLength)
            {
                // Die ältere Hälfte des Logs abschneiden
                var current = _logBuilder.ToString();
                _logBuilder.Clear();
                _logBuilder.Append(current.Substring(current.Length / 2));
            }

            _logBuilder.Append(line);
            LogContent = _logBuilder.ToString();
        });
    }

    [RelayCommand]
    private void Clear()
    {
        _logBuilder.Clear();
        LogContent = "";
        AppendLog("SYSTEM", "Terminal-Inhalt geleert.");
    }

    public void Dispose()
    {
        _sse.LogReceived -= OnLogReceived;
        WeakReferenceMessenger.Default.Unregister<WpfLogMessage>(this);
    }
}
