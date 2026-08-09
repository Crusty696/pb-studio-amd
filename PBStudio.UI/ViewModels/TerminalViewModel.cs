using System;
using System.Collections.Concurrent;
using System.Text;
using System.Threading;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

public partial class TerminalViewModel : ObservableObject, IDisposable
{
    private readonly TerminalLogBuffer _buffer;
    private readonly StringBuilder _logBuilder = new();
    private readonly ConcurrentQueue<TerminalLogEntry> _pendingEntries = new();
    private const int MaxLogLength = 100_000;
    private int _flushScheduled;
    private int _disposed;

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
        if (Volatile.Read(ref _disposed) != 0)
            return;
        _pendingEntries.Enqueue(entry);
        ScheduleFlush();
    }

    private void ScheduleFlush()
    {
        if (Volatile.Read(ref _disposed) != 0
            || Interlocked.Exchange(ref _flushScheduled, 1) != 0)
            return;
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher != null)
            _ = dispatcher.InvokeAsync(FlushPendingEntries);
        else
            FlushPendingEntries();
    }

    private void FlushPendingEntries()
    {
        if (Volatile.Read(ref _disposed) != 0)
        {
            while (_pendingEntries.TryDequeue(out _)) { }
            Interlocked.Exchange(ref _flushScheduled, 0);
            return;
        }
        while (_pendingEntries.TryDequeue(out var entry))
            AppendEntry(entry);
        Interlocked.Exchange(ref _flushScheduled, 0);
        if (!_pendingEntries.IsEmpty)
            ScheduleFlush();
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
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
            return;
        _buffer.Unsubscribe(OnEntryAdded);
        while (_pendingEntries.TryDequeue(out _)) { }
    }
}
