using System.IO;
using System.Threading.Channels;
using Microsoft.Extensions.Logging;

namespace PBStudio.UI;

/// <summary>Einfacher File-Logger für Debugging — schreibt alle Logs in eine Datei.</summary>
public class FileLoggerProvider : ILoggerProvider
{
    private readonly string _filePath;
    private readonly Channel<string> _messages;
    private readonly Task _writerTask;
    private int _disposed;

    public FileLoggerProvider(string filePath)
    {
        _filePath = filePath;
        // AUDIT-FIX C#-2: Best-Effort — ein gesperrtes/nicht schreibbares Log darf den Start
        // (OnStartup, vor jedem Fenster/Exception-Handler) nicht abreissen. Fehler schlucken;
        // FileLogger.Log faengt Schreibfehler ohnehin ab.
        try
        {
            File.WriteAllText(_filePath, $"=== PB Studio WPF Log — {DateTime.Now:yyyy-MM-dd HH:mm:ss} ==={Environment.NewLine}");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"FileLoggerProvider: Log-Init fehlgeschlagen: {ex.Message}");
        }

        _messages = Channel.CreateBounded<string>(new BoundedChannelOptions(4096)
        {
            SingleReader = true,
            SingleWriter = false,
            FullMode = BoundedChannelFullMode.Wait,
            AllowSynchronousContinuations = false,
        });
        _writerTask = Task.Run(ProcessQueueAsync);
    }

    public ILogger CreateLogger(string categoryName) => new FileLogger(categoryName, _messages.Writer);

    private async Task ProcessQueueAsync()
    {
        StreamWriter? writer = null;
        try
        {
            await foreach (var line in _messages.Reader.ReadAllAsync().ConfigureAwait(false))
            {
                try
                {
                    writer ??= new StreamWriter(
                        new FileStream(_filePath, FileMode.Append, FileAccess.Write, FileShare.ReadWrite))
                    {
                        AutoFlush = true,
                    };
                    await writer.WriteLineAsync(line).ConfigureAwait(false);
                }
                catch (Exception ex)
                {
                    writer?.Dispose();
                    writer = null;
                    System.Diagnostics.Debug.WriteLine(
                        $"FileLoggerProvider: Log-Write fehlgeschlagen: {ex.Message}");
                }
            }
        }
        finally
        {
            if (writer != null)
                await writer.DisposeAsync().ConfigureAwait(false);
        }
    }

    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
            return;

        _messages.Writer.TryComplete();
        try
        {
            if (!_writerTask.Wait(TimeSpan.FromSeconds(2)))
                System.Diagnostics.Debug.WriteLine("FileLoggerProvider: Log-Drain Timeout");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"FileLoggerProvider: Log-Drain fehlgeschlagen: {ex.Message}");
        }
    }
}

internal class FileLogger : ILogger
{
    private readonly string _category;
    private readonly ChannelWriter<string> _writer;

    public FileLogger(string category, ChannelWriter<string> writer)
    {
        _category = category;
        _writer = writer;
    }

    public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
    public bool IsEnabled(LogLevel logLevel) => logLevel >= LogLevel.Debug;

    public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        if (!IsEnabled(logLevel)) return;

        var line = $"{DateTime.Now:HH:mm:ss.fff} [{logLevel}] {_category}: {formatter(state, exception)}";
        if (exception != null)
            line += Environment.NewLine + exception.ToString();

        _writer.TryWrite(line);
    }
}
