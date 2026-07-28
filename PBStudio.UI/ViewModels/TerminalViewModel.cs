using System;
using System.Text;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

public partial class TerminalViewModel : ObservableObject, IDisposable
{
    private readonly TerminalLogBuffer _buffer;
    private readonly StringBuilder _logBuilder = new();
    private const int MaxLogLength = 100_000;

    [ObservableProperty]
    private string _logContent = "";

    public TerminalViewModel(TerminalLogBuffer buffer)
    {
        _buffer = buffer;
        var history = _buffer.Subscribe(OnEntryAdded);
        foreach (var entry in history)
        {
            AppendEntry(entry);
        }

        if (history.Length == 0)
            _buffer.Append("SYSTEM", "Terminal initialisiert. Warte auf Logs...");
    }

    private void OnEntryAdded(TerminalLogEntry entry)
    {
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher != null)
            _ = dispatcher.InvokeAsync(() => AppendEntry(entry));
    }

    private void AppendEntry(TerminalLogEntry entry)
    {
        var line = $"[{entry.Timestamp:HH:mm:ss}] [{entry.Level}] {entry.Message}\n";
        if (_logBuilder.Length + line.Length > MaxLogLength)
        {
            var current = _logBuilder.ToString();
            _logBuilder.Clear();
            _logBuilder.Append(current[(current.Length / 2)..]);
        }
        _logBuilder.Append(line);
        LogContent = _logBuilder.ToString();
    }

    [RelayCommand]
    private void Clear()
    {
        _buffer.Clear();
        _logBuilder.Clear();
        LogContent = "";
        _buffer.Append("SYSTEM", "Terminal-Inhalt geleert.");
    }

    public void Dispose()
    {
        _buffer.Unsubscribe(OnEntryAdded);
    }
}
