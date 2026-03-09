using System.IO;
using Microsoft.Extensions.Logging;

namespace PBStudio.UI;

/// <summary>Einfacher File-Logger für Debugging — schreibt alle Logs in eine Datei.</summary>
public class FileLoggerProvider : ILoggerProvider
{
    private readonly string _filePath;
    private readonly object _lock = new();

    public FileLoggerProvider(string filePath)
    {
        _filePath = filePath;
        // Log-Datei bei jedem Start leeren
        File.WriteAllText(_filePath, $"=== PB Studio WPF Log — {DateTime.Now:yyyy-MM-dd HH:mm:ss} ==={Environment.NewLine}");
    }

    public ILogger CreateLogger(string categoryName) => new FileLogger(_filePath, categoryName, _lock);
    public void Dispose() { }
}

internal class FileLogger : ILogger
{
    private readonly string _filePath;
    private readonly string _category;
    private readonly object _lock;

    public FileLogger(string filePath, string category, object lockObj)
    {
        _filePath = filePath;
        _category = category;
        _lock = lockObj;
    }

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
    public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Debug;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        if (!IsEnabled(logLevel)) return;

        var line = $"{DateTime.Now:HH:mm:ss.fff} [{logLevel}] {_category}: {formatter(state, exception)}";
        if (exception != null)
            line += Environment.NewLine + exception.ToString();

        lock (_lock)
        {
            try { File.AppendAllText(_filePath, line + Environment.NewLine); } catch { }
        }
    }
}
