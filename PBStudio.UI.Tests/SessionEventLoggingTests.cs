using System.Reflection;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Services;

namespace PBStudio.UI.Tests;

[TestClass]
public sealed class SessionEventLoggingTests
{
    [TestMethod]
    public void ReceivedEventsAreLoggedEvenWhenUiThrottlesAndSecretsAreRedacted()
    {
        var logger = new CaptureLogger();
        using var client = new SSEClient(logger, new TerminalLogBuffer());
        var last = (Dictionary<string, (DateTime, double)>)typeof(SSEClient)
            .GetField("_lastProgressUpdate", BindingFlags.Instance | BindingFlags.NonPublic)!
            .GetValue(client)!;
        last["job-test"] = (DateTime.MaxValue, 0);
        var uiEvents = 0;
        client.ProgressReceived += (_, _) => uiEvents++;
        var streamType = typeof(SSEClient).GetNestedType("StreamKind", BindingFlags.NonPublic)!;
        var stream = Enum.Parse(streamType, "Progress");
        var method = typeof(SSEClient).GetMethod("TryProcessEvent", BindingFlags.Instance | BindingFlags.NonPublic)!;
        const string payload = """{"task_id":"job-test","status":"running","percent":1,"api_key":"must-not-leak"}""";
        method.Invoke(client, [stream, "analysis_progress", payload]);
        method.Invoke(client, [stream, "analysis_progress", payload]);
        Assert.AreEqual(0, uiEvents);
        Assert.AreEqual(2, logger.Lines.Count(x => x.Contains("SSE-Ereignis:")));
        Assert.IsFalse(logger.Lines.Any(x => x.Contains("must-not-leak")));
        Assert.IsTrue(logger.Lines.Any(x => x.Contains("[REDACTED]")));
    }

    private sealed class CaptureLogger : ILogger<SSEClient>
    {
        public List<string> Lines { get; } = [];
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;
        public bool IsEnabled(LogLevel level) => true;
        public void Log<TState>(LogLevel level, EventId eventId, TState state, Exception? exception,
            Func<TState, Exception?, string> formatter) => Lines.Add(formatter(state, exception));
    }
}
