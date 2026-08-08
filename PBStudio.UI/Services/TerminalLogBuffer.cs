namespace PBStudio.UI.Services;

public sealed record TerminalLogEntry(
    DateTime Timestamp,
    string Level,
    string Message);

public sealed class TerminalLogBuffer
{
    private const int MaxCharacters = 100_000;
    private readonly object _lock = new();
    private readonly Queue<TerminalLogEntry> _entries = new();
    private int _characterCount;
    private Action<TerminalLogEntry>? _entryAdded;

    public void Append(string level, string message)
    {
        var entry = new TerminalLogEntry(
            DateTime.Now,
            string.IsNullOrWhiteSpace(level) ? "INFO" : level.ToUpperInvariant(),
            TerminalLogRedactor.Redact(message));
        Action<TerminalLogEntry>? handlers;

        lock (_lock)
        {
            _entries.Enqueue(entry);
            _characterCount += Measure(entry);
            while (_characterCount > MaxCharacters && _entries.Count > 1)
            {
                _characterCount -= Measure(_entries.Dequeue());
            }
            handlers = _entryAdded;
        }

        if (handlers == null)
            return;

        foreach (Action<TerminalLogEntry> handler in handlers.GetInvocationList())
        {
            try
            {
                handler(entry);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"TerminalLogBuffer subscriber failed: {ex.Message}");
            }
        }
    }

    public TerminalLogEntry[] Subscribe(Action<TerminalLogEntry> handler)
    {
        lock (_lock)
        {
            _entryAdded += handler;
            return _entries.ToArray();
        }
    }

    public void Unsubscribe(Action<TerminalLogEntry> handler)
    {
        lock (_lock)
        {
            _entryAdded -= handler;
        }
    }

    public void Clear()
    {
        lock (_lock)
        {
            _entries.Clear();
            _characterCount = 0;
        }
    }

    private static int Measure(TerminalLogEntry entry) =>
        entry.Level.Length + entry.Message.Length + 24;
}
