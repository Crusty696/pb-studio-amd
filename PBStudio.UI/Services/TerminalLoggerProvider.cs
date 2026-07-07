using System;
using Microsoft.Extensions.Logging;
using CommunityToolkit.Mvvm.Messaging;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.Services;

/// <summary>
/// LoggerProvider, der alle WPF Log-Nachrichten abfängt und an das Terminal streamt.
/// </summary>
public class TerminalLoggerProvider : ILoggerProvider
{
    public ILogger CreateLogger(string categoryName) => new TerminalLogger(categoryName);
    public void Dispose() { }
}

internal class TerminalLogger : ILogger
{
    private readonly string _category;

    public TerminalLogger(string category)
    {
        _category = category;
    }

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
    
    public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Information;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        if (!IsEnabled(logLevel)) return;

        var message = formatter(state, exception);
        if (exception != null)
            message += " - Exception: " + exception.ToString();

        var levelStr = logLevel switch
        {
            LogLevel.Critical => "CRITICAL",
            LogLevel.Error => "ERROR",
            LogLevel.Warning => "WARN",
            _ => "INFO"
        };

        // Über WeakReferenceMessenger an TerminalViewModel senden.
        var categoryShort = GetShortCategory(_category);
        WeakReferenceMessenger.Default.Send(new WpfLogMessage(levelStr, $"{categoryShort}: {message}"));
    }

    private static string GetShortCategory(string category)
    {
        if (string.IsNullOrEmpty(category)) return "WPF";
        var idx = category.LastIndexOf('.');
        return idx >= 0 ? category[(idx + 1)..] : category;
    }
}
