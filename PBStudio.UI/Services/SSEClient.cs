using System.Globalization;
using System.IO;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
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
    private volatile bool _isListening;
    private volatile bool _disposed;
    private readonly Dictionary<string, DateTime> _lastReconnectLogUtc = [];

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

                if (reconnectAttempts > 0)
                    _logger.LogInformation("SSE {Endpoint} wieder verbunden nach {Attempts} Reconnect-Versuchen", endpoint, reconnectAttempts);

                reconnectDelayMs = InitialReconnectDelayMs;
                reconnectAttempts = 0;

                var eventType = "message";
                var dataBuilder = new StringBuilder();

                while (!ct.IsCancellationRequested)
                {
                    var line = await reader.ReadLineAsync(ct).ConfigureAwait(false);
                    if (line == null)
                        break;

                    if (string.IsNullOrEmpty(line))
                    {
                        DispatchBufferedEvent(streamKind, eventType, dataBuilder);
                        eventType = "message";
                        dataBuilder.Clear();
                        continue;
                    }

                    if (line.StartsWith(':'))
                        continue;

                    if (line.StartsWith("event: ", StringComparison.Ordinal))
                    {
                        eventType = line[7..].Trim();
                        continue;
                    }

                    if (line.StartsWith("data: ", StringComparison.Ordinal))
                    {
                        if (dataBuilder.Length > 0)
                            dataBuilder.Append('\n');
                        dataBuilder.Append(line[6..]);
                    }
                }

                DispatchBufferedEvent(streamKind, eventType, dataBuilder);
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

                LogReconnectFailure(endpoint, reconnectDelayMs, reconnectAttempts, ex);

                await Task.Delay(reconnectDelayMs, ct).ConfigureAwait(false);
                reconnectDelayMs = Math.Min(reconnectDelayMs * 2, MaxReconnectDelayMs);
            }
        }
    }

    private void DispatchBufferedEvent(StreamKind streamKind, string eventType, StringBuilder dataBuilder)
    {
        if (dataBuilder.Length == 0)
            return;

        ProcessEvent(streamKind, eventType, dataBuilder.ToString());
    }

    private void LogReconnectFailure(string endpoint, int reconnectDelayMs, int reconnectAttempts, Exception ex)
    {
        var now = DateTime.UtcNow;
        var isConnectionRefused = ex is HttpRequestException httpEx && httpEx.InnerException is SocketException { SocketErrorCode: SocketError.ConnectionRefused };
        var shouldLog = !_lastReconnectLogUtc.TryGetValue(endpoint, out var lastLogUtc)
            || now - lastLogUtc >= TimeSpan.FromSeconds(30)
            || reconnectAttempts <= 2;

        if (!shouldLog)
            return;

        _lastReconnectLogUtc[endpoint] = now;

        if (isConnectionRefused)
        {
            _logger.LogInformation(
                "SSE {Endpoint} wartet auf Backend, nächster Reconnect in {Delay}ms (Versuch {Attempt}/{Max}).",
                endpoint,
                reconnectDelayMs,
                reconnectAttempts,
                MaxReconnectAttempts);
            return;
        }

        _logger.LogWarning(
            ex,
            "SSE {Endpoint} Verbindung unterbrochen, Reconnect in {Delay}ms (Versuch {Attempt}/{Max})...",
            endpoint,
            reconnectDelayMs,
            reconnectAttempts,
            MaxReconnectAttempts);
    }

    private void ProcessEvent(StreamKind streamKind, string eventType, string jsonData)
    {
        try
        {
            using var json = JsonDocument.Parse(jsonData);
            var root = json.RootElement;

            switch (streamKind)
            {
                case StreamKind.Progress when eventType is "analysis_progress" or "render_progress" or "stem_progress" or "import_progress" or "gpu_error":
                    ProgressReceived?.Invoke(this, new ProgressEventArgs
                    {
                        EventType = eventType,
                        Percent = TryGetDouble(root, "percent"),
                        Message = FirstNonEmpty(
                            TryGetString(root, "message"),
                            TryGetString(root, "error"),
                            TryGetString(root, "detail")),
                        TaskId = FirstNonEmpty(TryGetString(root, "task_id"), TryGetString(root, "job_id")),
                        Status = NormalizeStatus(root),
                        CurrentFrame = TryGetInt(root, "current_frame"),
                        TotalFrames = TryGetInt(root, "total_frames"),
                        ElapsedSeconds = TryGetDouble(root, "elapsed_seconds"),
                        EtaSeconds = TryGetDouble(root, "eta_seconds"),
                        OutputPath = TryGetString(root, "output_path"),
                        Error = TryGetString(root, "error"),
                    });
                    break;

                case StreamKind.Log when eventType == "log":
                    LogReceived?.Invoke(this, new LogEventArgs
                    {
                        Level = string.IsNullOrWhiteSpace(TryGetString(root, "level")) ? "info" : TryGetString(root, "level"),
                        Message = FirstNonEmpty(TryGetString(root, "message"), TryGetString(root, "detail")),
                    });
                    break;

                case StreamKind.Gpu when eventType == "gpu_status":
                    GpuStatusReceived?.Invoke(this, new GpuEventArgs
                    {
                        VramUsedMb = (int)Math.Round(TryGetDouble(root, "vram_used_mb")),
                        VramTotalMb = (int)Math.Round(TryGetDouble(root, "vram_total_mb")),
                        TemperatureC = (int)Math.Round(TryGetDouble(root, "temperature_c")),
                        GpuLoadPercent = TryGetDouble(root, "gpu_load"),
                        Error = TryGetString(root, "error"),
                    });
                    break;
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "SSE Event Parsing fehlgeschlagen ({StreamKind}): {Data}", streamKind, jsonData);
        }
    }

    private static string NormalizeStatus(JsonElement root)
    {
        var status = FirstNonEmpty(
            TryGetString(root, "status"),
            TryGetString(root, "state"),
            TryGetString(root, "phase"));

        return status.ToLowerInvariant() switch
        {
            "done" or "complete" => "completed",
            "error" => "failed",
            _ => status,
        };
    }

    private static string FirstNonEmpty(params string[] values)
        => values.FirstOrDefault(static value => !string.IsNullOrWhiteSpace(value)) ?? string.Empty;

    private static string TryGetString(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out var value))
            return string.Empty;

        return value.ValueKind switch
        {
            JsonValueKind.String => value.GetString() ?? string.Empty,
            JsonValueKind.Number => value.GetRawText(),
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            _ => string.Empty,
        };
    }

    private static double TryGetDouble(JsonElement root, string propertyName)
    {
        if (!root.TryGetProperty(propertyName, out var value))
            return 0;

        return value.ValueKind switch
        {
            JsonValueKind.Number when value.TryGetDouble(out var d) => d,
            JsonValueKind.String when double.TryParse(value.GetString(), NumberStyles.Any, CultureInfo.InvariantCulture, out var parsed) => parsed,
            _ => 0,
        };
    }

    private static int TryGetInt(JsonElement root, string propertyName)
        => (int)Math.Round(TryGetDouble(root, propertyName));

    public void Dispose()
    {
        if (_disposed) return; _disposed = true;
        StopListening();
        // FINDING-020 Fix: Erst auf Tasks warten, dann HttpClient freigeben.
        // Sonst kann ein noch laufender ListenAsync-Task eine ObjectDisposedException
        // auf dem bereits entsorgten HttpClient werfen.
        if (_listenTasks.Count > 0)
            Task.WaitAll([.. _listenTasks], TimeSpan.FromMilliseconds(200));
        _httpClient.Dispose();
        _cts?.Dispose();
        _cts = null;
    }

    private enum StreamKind
    {
        Progress,
        Log,
        Gpu,
    }
}

public class ProgressEventArgs : EventArgs
{
    public string EventType { get; init; } = "";
    public double Percent { get; init; }
    public string Message { get; init; } = "";
    public string TaskId { get; init; } = "";
    public string Status { get; init; } = "";
    public int CurrentFrame { get; init; }
    public int TotalFrames { get; init; }
    public double ElapsedSeconds { get; init; }
    public double EtaSeconds { get; init; }
    public string OutputPath { get; init; } = "";
    public string Error { get; init; } = "";
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
    public double GpuLoadPercent { get; init; }
    public string Error { get; init; } = "";
}
