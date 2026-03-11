using System.IO;
using System.Net.Http;
using System.Text.Json;
using Microsoft.Extensions.Logging;

namespace PBStudio.UI.Services;

/// <summary>
/// Server-Sent Events (SSE) Client für Echtzeit-Updates vom Python Backend.
/// Empfängt Progress-Events, Log-Nachrichten und GPU-Status.
/// </summary>
public class SSEClient : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<SSEClient> _logger;
    private CancellationTokenSource? _cts;
    private readonly List<Task> _listenTasks = [];
    private bool _isListening;

    // Exponential Backoff für Reconnect
    private const int InitialReconnectDelayMs = 3000;
    private const int MaxReconnectDelayMs = 30000;
    private const int MaxReconnectAttempts = 50;

    public event EventHandler<ProgressEventArgs>? ProgressReceived;
    public event EventHandler<LogEventArgs>? LogReceived;
    public event EventHandler<GpuEventArgs>? GpuStatusReceived;

    public SSEClient(ILogger<SSEClient> logger)
    {
        _logger = logger;
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri("http://127.0.0.1:8765"),
            Timeout = TimeSpan.FromMilliseconds(Timeout.Infinite),
        };
    }

    /// <summary>Startet das Lauschen auf SSE Events.</summary>
    public void StartListening()
    {
        if (_isListening)
        {
            _logger.LogDebug("SSE Client läuft bereits");
            return;
        }

        _cts = new CancellationTokenSource();
        _listenTasks.Clear();
        _listenTasks.Add(Task.Run(() => ListenAsync("/events/progress", StreamKind.Progress, _cts.Token)));
        _listenTasks.Add(Task.Run(() => ListenAsync("/events/log", StreamKind.Log, _cts.Token)));
        _listenTasks.Add(Task.Run(() => ListenAsync("/events/gpu", StreamKind.Gpu, _cts.Token)));
        _isListening = true;
        _logger.LogInformation("SSE Client gestartet (progress, log, gpu)");
    }

    /// <summary>Stoppt das Lauschen.</summary>
    public void StopListening()
    {
        if (!_isListening)
            return;

        _cts?.Cancel();
        _isListening = false;
        _logger.LogInformation("SSE Client gestoppt");
    }

    private async Task ListenAsync(string endpoint, StreamKind streamKind, CancellationToken ct)
    {
        var reconnectDelayMs = InitialReconnectDelayMs;
        var reconnectAttempts = 0;

        while (!ct.IsCancellationRequested)
        {
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, endpoint);
                using var response = await _httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct).ConfigureAwait(false);
                response.EnsureSuccessStatusCode();

                using var stream = await response.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
                using var reader = new StreamReader(stream);

                // Erfolgreiche Verbindung: Backoff zurücksetzen
                reconnectDelayMs = InitialReconnectDelayMs;
                reconnectAttempts = 0;

                string? eventType = null;

                while (!ct.IsCancellationRequested)
                {
                    var line = await reader.ReadLineAsync(ct).ConfigureAwait(false);
                    if (line == null) break;

                    if (line.StartsWith("event: "))
                    {
                        eventType = line[7..];
                    }
                    else if (line.StartsWith("data: "))
                    {
                        var data = line[6..];
                        ProcessEvent(streamKind, eventType ?? "message", data);
                        eventType = null;
                    }
                    else if (line.StartsWith(":"))
                    {
                        // Keepalive — ignorieren
                    }
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                reconnectAttempts++;
                if (reconnectAttempts > MaxReconnectAttempts)
                {
                    _logger.LogError("SSE {Endpoint}: Max Reconnect-Versuche ({Attempts}) erreicht, gebe auf.", endpoint, reconnectAttempts);
                    break;
                }

                _logger.LogWarning(ex,
                    "SSE {Endpoint} Verbindung unterbrochen, Reconnect in {Delay}ms (Versuch {Attempt}/{Max})...",
                    endpoint, reconnectDelayMs, reconnectAttempts, MaxReconnectAttempts);

                await Task.Delay(reconnectDelayMs, ct).ConfigureAwait(false);
                reconnectDelayMs = Math.Min(reconnectDelayMs * 2, MaxReconnectDelayMs);
            }
        }
    }

    private void ProcessEvent(StreamKind streamKind, string eventType, string jsonData)
    {
        try
        {
            var json = JsonDocument.Parse(jsonData);
            var root = json.RootElement;

            switch (streamKind)
            {
                case StreamKind.Progress when eventType is "analysis_progress" or "render_progress" or "stem_progress" or "import_progress":
                    ProgressReceived?.Invoke(this, new ProgressEventArgs
                    {
                        EventType = eventType,
                        Percent = root.TryGetProperty("percent", out var p) ? p.GetDouble() : 0,
                        Message = root.TryGetProperty("message", out var m) ? m.GetString() ?? "" : "",
                        TaskId = root.TryGetProperty("task_id", out var t) ? t.GetString() ?? "" : "",
                        Status = root.TryGetProperty("status", out var s) ? s.GetString() ?? "" : "",
                    });
                    break;

                case StreamKind.Log when eventType == "log":
                    LogReceived?.Invoke(this, new LogEventArgs
                    {
                        Level = root.TryGetProperty("level", out var l) ? l.GetString() ?? "info" : "info",
                        Message = root.TryGetProperty("message", out var lm) ? lm.GetString() ?? "" : "",
                    });
                    break;

                case StreamKind.Gpu when eventType == "gpu_status":
                    GpuStatusReceived?.Invoke(this, new GpuEventArgs
                    {
                        VramUsedMb = root.TryGetProperty("vram_used_mb", out var vu) ? vu.GetInt32() : 0,
                        VramTotalMb = root.TryGetProperty("vram_total_mb", out var vt) ? vt.GetInt32() : 0,
                        TemperatureC = root.TryGetProperty("temperature_c", out var tc) ? tc.GetInt32() : 0,
                    });
                    break;
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "SSE Event Parsing fehlgeschlagen ({StreamKind}): {Data}", streamKind, jsonData);
        }
    }

    public void Dispose()
    {
        StopListening();
        _httpClient.Dispose();
        _cts?.Dispose();
    }

    private enum StreamKind
    {
        Progress,
        Log,
        Gpu,
    }
}

// --- Event Args ---

public class ProgressEventArgs : EventArgs
{
    public string EventType { get; init; } = "";
    public double Percent { get; init; }
    public string Message { get; init; } = "";
    public string TaskId { get; init; } = "";
    public string Status { get; init; } = "";
}

public class LogEventArgs : EventArgs
{
    public string Level { get; init; } = "info";
    public string Message { get; init; } = "";
}

public class GpuEventArgs : EventArgs
{
    public int VramUsedMb { get; init; }
    public int VramTotalMb { get; init; }
    public int TemperatureC { get; init; }
}
