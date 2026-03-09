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
    private Task? _listenTask;

    // Exponential Backoff für Reconnect
    private const int InitialReconnectDelayMs = 3000;
    private const int MaxReconnectDelayMs = 30000;
    private const int MaxReconnectAttempts = 50;
    private int _currentReconnectDelayMs = InitialReconnectDelayMs;
    private int _reconnectAttempts = 0;

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
        _cts = new CancellationTokenSource();
        _listenTask = Task.Run(() => ListenAsync(_cts.Token));
        _logger.LogInformation("SSE Client gestartet");
    }

    /// <summary>Stoppt das Lauschen.</summary>
    public void StopListening()
    {
        _cts?.Cancel();
        _logger.LogInformation("SSE Client gestoppt");
    }

    private async Task ListenAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, "/events/progress");
                using var response = await _httpClient.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct).ConfigureAwait(false);
                using var stream = await response.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
                using var reader = new StreamReader(stream);

                // Erfolgreiche Verbindung: Backoff zurücksetzen
                _currentReconnectDelayMs = InitialReconnectDelayMs;
                _reconnectAttempts = 0;

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
                        ProcessEvent(eventType ?? "message", data);
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
                _reconnectAttempts++;
                if (_reconnectAttempts > MaxReconnectAttempts)
                {
                    _logger.LogError("SSE: Max Reconnect-Versuche ({Attempts}) erreicht, gebe auf.", _reconnectAttempts);
                    break;
                }

                _logger.LogWarning(ex, "SSE Verbindung unterbrochen, Reconnect in {Delay}ms (Versuch {Attempt}/{Max})...",
                    _currentReconnectDelayMs, _reconnectAttempts, MaxReconnectAttempts);

                await Task.Delay(_currentReconnectDelayMs, ct).ConfigureAwait(false);

                // Exponential Backoff: 3s → 6s → 12s → 24s → 30s max
                _currentReconnectDelayMs = Math.Min(_currentReconnectDelayMs * 2, MaxReconnectDelayMs);
            }
        }
    }

    private void ProcessEvent(string eventType, string jsonData)
    {
        try
        {
            var json = JsonDocument.Parse(jsonData);
            var root = json.RootElement;

            switch (eventType)
            {
                case "analysis_progress":
                case "render_progress":
                case "stem_progress":
                case "import_progress":
                    ProgressReceived?.Invoke(this, new ProgressEventArgs
                    {
                        EventType = eventType,
                        Percent = root.TryGetProperty("percent", out var p) ? p.GetDouble() : 0,
                        Message = root.TryGetProperty("message", out var m) ? m.GetString() ?? "" : "",
                        TaskId = root.TryGetProperty("task_id", out var t) ? t.GetString() ?? "" : "",
                    });
                    break;

                case "log":
                    LogReceived?.Invoke(this, new LogEventArgs
                    {
                        Level = root.TryGetProperty("level", out var l) ? l.GetString() ?? "info" : "info",
                        Message = root.TryGetProperty("message", out var lm) ? lm.GetString() ?? "" : "",
                    });
                    break;

                case "gpu_status":
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
            _logger.LogWarning(ex, "SSE Event Parsing fehlgeschlagen: {Data}", jsonData);
        }
    }

    public void Dispose()
    {
        StopListening();
        _httpClient.Dispose();
        _cts?.Dispose();
    }
}

// --- Event Args ---

public class ProgressEventArgs : EventArgs
{
    public string EventType { get; init; } = "";
    public double Percent { get; init; }
    public string Message { get; init; } = "";
    public string TaskId { get; init; } = "";
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
