using System.Collections.Concurrent;
using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;

namespace PBStudio.UI.Services;

/// <summary>
/// Typisierter HTTP Client für Kommunikation mit dem Python FastAPI Backend.
/// Alle Methoden sind async und blockieren das UI nicht.
/// </summary>
public partial class ApiClient : IApiClient, IProviderSelectionApi
{
    private readonly HttpClient _http;
    private readonly ILogger<ApiClient> _logger;
    private readonly CancellationTokenSource _shutdownCts = new();
    private readonly ConcurrentDictionary<(string ProjectIdentity, int CutId, string Rating), Guid>
        _pendingBrainFeedbackOperations = new();
    private string _activeProjectIdentity = $"session:{Guid.NewGuid():N}";
    private volatile bool _isShuttingDown;
    private bool _disposed;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    public ApiClient(HttpClient http, ILogger<ApiClient> logger)
    {
        _http = http;
        _http.Timeout = TimeSpan.FromMinutes(20);
        _logger = logger;
    }

    public void BeginShutdown()
    {
        if (_isShuttingDown)
            return;

        _isShuttingDown = true;
        _shutdownCts.Cancel();
    }

    /// <summary>
    /// Grund des zuletzt fehlgeschlagenen Requests, wie ihn das Backend im
    /// <c>detail</c>-Feld gemeldet hat. Vor dem Fix wurde dieser Body verworfen,
    /// wodurch jedes 4xx für User und Log grundlos blieb (Audit 2026-08-05, C-1/T0.1).
    /// </summary>
    public string? LastErrorDetail { get; private set; }

    /// <summary>Liest das <c>detail</c>-Feld einer Fehlerantwort und merkt es sich.</summary>
    private async Task<string?> CaptureErrorDetailAsync(
        HttpResponseMessage response,
        CancellationToken token)
    {
        try
        {
            var raw = await response.Content.ReadAsStringAsync(token).ConfigureAwait(false);
            LastErrorDetail = ExtractDetail(raw);
        }
        catch (Exception ex) when (!IsExpectedCancellation(ex, token))
        {
            LastErrorDetail = null;
        }
        return LastErrorDetail;
    }

    /// <summary>
    /// Zieht den lesbaren Fehlergrund aus einem FastAPI-Body. <c>detail</c> ist
    /// entweder ein String (HTTPException) oder eine Liste (Validierungsfehler).
    /// </summary>
    private static string? ExtractDetail(string? rawBody)
    {
        if (string.IsNullOrWhiteSpace(rawBody))
            return null;

        try
        {
            using var doc = JsonDocument.Parse(rawBody);
            if (doc.RootElement.ValueKind == JsonValueKind.Object
                && doc.RootElement.TryGetProperty("detail", out var detail))
            {
                if (detail.ValueKind == JsonValueKind.String)
                    return detail.GetString();

                if (detail.ValueKind == JsonValueKind.Array)
                {
                    var parts = detail.EnumerateArray()
                        .Select(item => item.ValueKind == JsonValueKind.Object
                            && item.TryGetProperty("msg", out var msg)
                                ? msg.GetString()
                                : item.ToString())
                        .Where(part => !string.IsNullOrWhiteSpace(part));
                    var joined = string.Join("; ", parts);
                    return string.IsNullOrWhiteSpace(joined) ? null : joined;
                }

                return detail.ToString();
            }
        }
        catch (JsonException)
        {
            // Kein JSON-Body — der Rohtext ist immer noch besser als gar nichts.
        }

        var trimmed = rawBody.Trim();
        return trimmed.Length > 500 ? trimmed[..500] : trimmed;
    }

    public async Task ShutdownAsync()
    {
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            using var request = new HttpRequestMessage(HttpMethod.Post, "/shutdown")
            {
                Content = JsonContent.Create((object?)null, options: JsonOptions),
            };
            using var response = await _http.SendAsync(request, cts.Token).ConfigureAwait(false);
            _logger.LogInformation("Backend graceful shutdown angefordert: {StatusCode}", response.StatusCode);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Backend /shutdown fehlgeschlagen (unkritisch — Prozess wird beendet)");
        }
    }

    // --- Generische Helfer ---

    public async Task<T?> GetAsync<T>(string url, CancellationToken cancellationToken = default) where T : class
    {
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var response = await _http.GetAsync(url, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            // R16/MEDIUM-001: Use linked token (includes _shutdownCts) for deserialization too
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "GET {Url} fehlgeschlagen", url);
            return null;
        }
    }

    private async Task<T?> DeleteAsync<T>(
        string url,
        CancellationToken cancellationToken = default) where T : class
    {
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var response = await _http.DeleteAsync(url, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "DELETE {Url} fehlgeschlagen", url);
            return null;
        }
    }

    private async Task<T?> DeleteWithBodyAsync<T>(
        string url,
        object body,
        CancellationToken cancellationToken = default) where T : class
    {
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            // HttpClient.DeleteAsync supports no body; need explicit HttpRequestMessage
            using var request = new HttpRequestMessage(HttpMethod.Delete, url)
            {
                Content = JsonContent.Create(body, options: JsonOptions),
            };
            using var response = await _http.SendAsync(request, token).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "DELETE {Url} (with body) fehlgeschlagen", url);
            return null;
        }
    }

    private async Task<T?> PostAsync<T>(
        string url,
        object? body,
        CancellationToken cancellationToken = default) where T : class
    {
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var response = await _http.PostAsJsonAsync(url, body, JsonOptions, token).ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                var detail = await CaptureErrorDetailAsync(response, token).ConfigureAwait(false);
                LastErrorDetail = detail
                    ?? $"HTTP {(int)response.StatusCode} {response.ReasonPhrase}";
                _logger.LogWarning(
                    "POST {Url} fehlgeschlagen: {Status} — {Detail}",
                    url,
                    (int)response.StatusCode,
                    detail ?? "(kein Detail im Body)");
                return null;
            }

            LastErrorDetail = null;
            return await response.Content.ReadFromJsonAsync<T>(JsonOptions, token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            LastErrorDetail = ex.Message;
            _logger.LogWarning(ex, "POST {Url} fehlgeschlagen", url);
            return null;
        }
    }

    private bool IsExpectedCancellation(Exception ex, CancellationToken cancellationToken = default)
        => ex is OperationCanceledException
           || (_isShuttingDown && ex is ObjectDisposedException)
           || cancellationToken.IsCancellationRequested
           || _shutdownCts.IsCancellationRequested;

    // R16/CRITICAL-004: _shutdownCts was never disposed. IApiClient now extends
    // IDisposable so the DI container (singleton scoped) disposes this on app exit.
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        if (!_isShuttingDown)
        {
            _isShuttingDown = true;
            _shutdownCts.Cancel();
        }
        _shutdownCts.Dispose();
        _pendingBrainFeedbackOperations.Clear();
    }

    /// <summary>Liest eine SSE-Zeile. Return: (line, eof, cancelled).</summary>
    private static async Task<(string? line, bool eof, bool cancelled)> ReadLineSafeAsync(
        System.IO.StreamReader reader,
        CancellationToken token,
        CancellationToken originalCt)
    {
        try
        {
            var line = await reader.ReadLineAsync(token).ConfigureAwait(false);
            return (line, line is null, false);
        }
        catch (OperationCanceledException)
        {
            return (null, false, true);
        }
        catch
        {
            // Netzwerk-Fehler treat as EOF — Verbraucher merkt das am ausbleibenden Terminal-Event.
            return (null, true, false);
        }
    }

    private async Task<T?> PostOwnerAuthorizedAsync<T>(
        string url,
        object? body,
        CancellationToken cancellationToken = default) where T : class
    {
        // Bewusst KEINE Capability-Vorabpruefung mehr an dieser Stelle:
        // Der Getter liefert null, solange der 10-Sekunden-Watchdog revalidiert
        // (siehe BackendOwnerCapability, _isVerified wird dabei kurz false).
        // Die alte Pruefung lief ausserhalb des RevalidationGate und brach Requests
        // hart ab, die in dieses Fenster fielen — sichtbar als "Button reagiert nicht".
        // Der OwnerCapabilityRequestHandler wartet am Gate und prueft dort
        // fail-closed; der Sicherheitsgewinn der Vorabpruefung war also null.
        // Audit 2026-08-05, H-1/T1.2.
        using var requestCts = cancellationToken.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(
                cancellationToken,
                _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, url)
            {
                Content = JsonContent.Create(body, options: JsonOptions),
            };
            using var response = await _http.SendAsync(request, token)
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
            {
                var detail = await CaptureErrorDetailAsync(response, token).ConfigureAwait(false);
                _logger.LogWarning(
                    "Owner-authorized POST {Url} fehlgeschlagen: {Status} — {Detail}",
                    url,
                    (int)response.StatusCode,
                    detail ?? "(kein Detail im Body)");
                return null;
            }

            LastErrorDetail = null;
            return await response.Content.ReadFromJsonAsync<T>(
                JsonOptions,
                token).ConfigureAwait(false);
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, cancellationToken))
        {
            return null;
        }
        catch (Exception ex)
        {
            LastErrorDetail = ex.Message;
            _logger.LogWarning(ex, "Owner-authorized POST {Url} fehlgeschlagen", url);
            return null;
        }
    }
}
