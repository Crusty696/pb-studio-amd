using System;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Logging;

namespace PBStudio.UI.Services;

internal static class TerminalLogRedactor
{
    internal const string RedactedSecret = "[REDACTED]";
    internal const string RedactedPath = "[LOCAL_PATH]";

    private static readonly TimeSpan MatchTimeout = TimeSpan.FromMilliseconds(100);
    private const RegexOptions Options =
        RegexOptions.Compiled | RegexOptions.CultureInvariant | RegexOptions.IgnoreCase;

    private static readonly Regex BearerPattern = new Regex(
        @"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
        Options,
        MatchTimeout);

    private static readonly Regex SecretAssignmentPattern = new Regex(
        @"\b(?<name>api[_-]?key|access[_-]?token|auth(?:orization)?|password|passwd|pwd|secret|client[_-]?secret)\b(?<separator>\s*[:=]\s*)(?:""[^""\r\n]*""|'[^'\r\n]*'|[^\s,;]+)",
        Options,
        MatchTimeout);

    private static readonly Regex TokenPattern = new Regex(
        @"(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{16,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})",
        Options,
        MatchTimeout);

    private static readonly Regex UrlCredentialsPattern = new Regex(
        @"\b(?<scheme>https?://)[^/\s:@]+:[^@\s/]+@",
        Options,
        MatchTimeout);

    private static readonly Regex AbsolutePathPattern = new Regex(
        @"(?:""|')?(?:file:/+)?(?:(?<![A-Z])[A-Z]:[\\/]|\\\\)[^\r\n]*",
        Options,
        MatchTimeout);

    internal static string Redact(string message)
    {
        var result = message ?? string.Empty;
        try
        {
            result = BearerPattern.Replace(result, RedactedSecret);
            result = SecretAssignmentPattern.Replace(
                result,
                match =>
                    match.Groups["name"].Value
                    + match.Groups["separator"].Value
                    + RedactedSecret);
            result = TokenPattern.Replace(result, RedactedSecret);
            result = UrlCredentialsPattern.Replace(
                result,
                match => match.Groups["scheme"].Value + RedactedSecret + "@");
            return AbsolutePathPattern.Replace(result, RedactedPath);
        }
        catch (RegexMatchTimeoutException)
        {
            System.Diagnostics.Debug.WriteLine("Terminal log redaction timed out.");
            return "[REDACTION_FAILED]";
        }
    }
}

/// <summary>
/// LoggerProvider, der alle WPF Log-Nachrichten abfängt und an das Terminal streamt.
/// </summary>
public class TerminalLoggerProvider : ILoggerProvider
{
    private readonly TerminalLogBuffer _buffer;

    public TerminalLoggerProvider(TerminalLogBuffer buffer)
    {
        _buffer = buffer;
    }

    public ILogger CreateLogger(string categoryName) => new TerminalLogger(categoryName, _buffer);
    public void Dispose() { }
}

internal class TerminalLogger : ILogger
{
    private readonly string _category;
    private readonly TerminalLogBuffer _buffer;

    public TerminalLogger(string category, TerminalLogBuffer buffer)
    {
        _category = category;
        _buffer = buffer;
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

        var categoryShort = GetShortCategory(_category);
        _buffer.Append(levelStr, $"{categoryShort}: {message}");
    }

    private static string GetShortCategory(string category)
    {
        if (string.IsNullOrEmpty(category)) return "WPF";
        var idx = category.LastIndexOf('.');
        return idx >= 0 ? category[(idx + 1)..] : category;
    }
}
