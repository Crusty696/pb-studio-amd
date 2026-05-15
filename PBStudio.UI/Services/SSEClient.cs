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
    private readonly object _stateLock = new object(); // BUG-056 FIX
    private volatile bool _disposed;
    private readonly Dictionary<string, DateTime> _lastReconnectLogUtc = [];

    private const int InitialReconnectDelayMs = 3000;
    private const int MaxReconnectDelayMs = 30000;
    private const int MaxReconnectAttempts = 50;
    // Spec 00010 T003 (TR-001): nach diesem Schwellwert UI per BackendReachabilityChanged
    // benachrichtigen. Verhindert UI-Flackern bei kurzen Drops.
    private const int NotifyUiAfterAttempts = 5;

    public event EventHandler<ProgressEventArgs>? ProgressReceived;
    public event EventHandler<LogEventArgs>? LogReceived;
    public event EventHandler<GpuEventArgs>? GpuStatusReceived;
    public event EventHandler<bool>? ConnectionStateChanged;
    /// <summary>
    /// Spec 00010 T003: Feuert true sobald Backend wieder erreichbar ist; feuert false
    /// erst nach NotifyUiAfterAttempts (5) fehlgeschlagenen Reconnect-Versuchen.
    /// UI bindet hier den ConnectionStatus-Overlay (T004) gegen — verhindert
    /// UI-Flackern bei kurzen Verbindungsabbruechen.
    /// </summary>
    public event EventHandler<bool>? BackendReachabilityChanged;

    private bool _isConnected;
    public bool IsConnected
    {
        get => _isConnected;
        private set
        {
            if (_isConnected != value)
            {
                _isConnected = value;
                ConnectionStateChanged?.Invoke(this, _isConnected);
            }
        }
    }

    private bool _isBackendReachable = true;
    /// <summary>Spec 00010 T003: latched reachability gegen UI-Flicker (5-Attempt-Threshold).</summary>
    public bool IsBackendReachable
    {
        get => _isBackendReachable;
        private set
        {
            if (_isBackendReachable != value)
            {
                _isBackendReachable = value;
                BackendReachabilityChanged?.Invoke(this, _isBackendReachable);
            }
        }
    }

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
        lock (_stateLock)
        {
            if (_isListening)
            {
                _logger.LogDebug("SSE Client läuft bereits");
                return;
            }

            // R16/CRITICAL-001: Dispose previous CTS before overwriting — a stop+start
            // cycle would leak the old CancellationTokenSource without this guard.
            _cts?.Dispose();
            _cts = new CancellationTokenSource();
            _listenTasks.Clear();
            _listenTasks.Add(Task.Run(() => ListenAsync("/events/progress", StreamKind.Progress, _cts.Token)));
            _listenTasks.Add(Task.Run(() => ListenAsync("/events/log", StreamKind.Log, _cts.Token)));
            _listenTasks.Add(Task.Run(() => ListenAsync("/events/gpu", StreamKind.Gpu, _cts.Token)));
            _isListening = true;
        }
        _logger.LogInformation("SSE Client gestartet (progress, log, gpu)");
    }

    public void StopListening()
    {
        lock (_stateLock)
        {
            if (!_isListening)
                return;

            _cts?.Cancel();
            _isListening = false;
        }
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

                IsConnected = true;
                // Spec 00010 T003: Erfolgreicher Connect — Reachability laut markieren.
                IsBackendReachable = true;

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
                IsConnected = false;
                reconnectAttempts++;
                // Spec 00010 T003 (TR-001): UI erst nach 5 fehlgeschlagenen Versuchen
                // benachrichtigen — kurze Drops (Backend-Restart, transientes Netzproblem)
                // werden so vor dem User versteckt.
                if (reconnectAttempts >= NotifyUiAfterAttempts)
                {
                    IsBackendReachable = false;
                }
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
                        Step = TryGetString(root, "step"),
                        StepIndex = TryGetInt(root, "step_index"),
                        StepTotal = TryGetInt(root, "step_total"),
                        ClipId = TryGetInt(root, "clip_id"),
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
        {
            // Wait up to 2 s for listen tasks to observe CancellationToken and exit cleanly
            // before we dispose the HttpClient they are using (CRITICAL-001 fix).
            Task.WaitAll([.. _listenTasks], TimeSpan.FromSeconds(2));
            _listenTasks.Clear();
        }
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
    public double Percent { get; init; } = -1.0; // -1 = nicht gesetzt (0 ist gueltig)
    public string Message { get; init; } = "";
    public string TaskId { get; init; } = "";
    public string Status { get; init; } = "";
    public int CurrentFrame { get; init; }
    public int TotalFrames { get; init; }
    public double ElapsedSeconds { get; init; }
    public double EtaSeconds { get; init; }
    public string OutputPath { get; init; } = "";
    public string Error { get; init; } = "";
    public string Step { get; init; } = "";       // Feature-3: phase-Identifier
    public int StepIndex { get; init; }            // 1-based current step
    public int StepTotal { get; init; }            // total steps in pipeline
    public int ClipId { get; init; }               // betroffenen Clip-ID
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
