using System.Collections.Concurrent;
using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;

namespace PBStudio.UI.Services;

public partial class ApiClient
{
    #region Model Manager
    // ----------------------------------------------------------------------
    // Ollama-Modell-Management. Backend: backend/routers/models_router.py
    //
    // Pull-Stream: Backend sendet SSE-Frames:
    //   event: pull_progress
    //   data: {"status":"pulling manifest", ...}
    //   <blank line>
    //
    // Wir parsen die SSE-Frames inline (kein dedizierter SSEClient noetig,
    // weil das hier ein per-Aufruf-Stream mit POST-Body ist).
    // ----------------------------------------------------------------------

    public Task<ModelListResponse?> GetInstalledModelsAsync(CancellationToken ct = default)
        => GetAsync<ModelListResponse>("/models/list?refresh=true", ct);

    public Task<AvailableModelsResponse?> GetAvailableModelsAsync(CancellationToken ct = default)
        => GetAsync<AvailableModelsResponse>("/models/available", ct);

    public async Task<bool> SelectProviderAsync(
        string provider,
        CancellationToken ct = default)
    {
        try
        {
            var result = await PostOwnerAuthorizedAsync<object>(
                "/models/provider",
                new { provider },
                ct).ConfigureAwait(false);
            return result != null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "SelectProviderAsync {Provider} fehlgeschlagen", provider);
            return false;
        }
    }

    public Task<ModelRecommendationResponse?> GetModelRecommendationAsync(
        string task = "video_captioning",
        string mode = "balance",
        CancellationToken ct = default)
    {
        var url = $"/models/recommendations?task={Uri.EscapeDataString(task)}&mode={Uri.EscapeDataString(mode)}";
        return GetAsync<ModelRecommendationResponse>(url, ct);
    }

    public async Task<bool> ActivateModelAsync(string name, string provider, CancellationToken ct = default)
    {
        try
        {
            var result = await PostOwnerAuthorizedAsync<object>(
                "/models/activate",
                new { name, provider },
                ct).ConfigureAwait(false);
            return result != null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "ActivateModelAsync {Name} fehlgeschlagen", name);
            return false;
        }
    }

    public async Task<bool> UpdateKiModeAsync(string mode, CancellationToken ct = default)
    {
        try
        {
            var result = await PostOwnerAuthorizedAsync<object>(
                "/models/mode",
                new { mode },
                ct).ConfigureAwait(false);
            return result != null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "UpdateKiModeAsync {Mode} fehlgeschlagen", mode);
            return false;
        }
    }

    public async Task<ModelTestResponse?> TestModelAsync(string name, string provider, CancellationToken ct = default)
    {
        try
        {
            return await PostOwnerAuthorizedAsync<ModelTestResponse>(
                "/models/test",
                new { name, provider },
                ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "TestModelAsync {Name} fehlgeschlagen", name);
            return new ModelTestResponse(false, 0.0, "", ex.Message);
        }
    }

    /// <summary>
    /// Loescht eine exakt live verifizierte Ollama-Modell-ID.
    /// LM-Studio-Modelle bleiben in der Desktop-App verwaltet.
    /// </summary>
    public async Task<bool> DeleteModelAsync(string name, CancellationToken ct = default)
    {
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;

        try
        {
            var url = $"/models/{Uri.EscapeDataString(name)}";
            using var request = new HttpRequestMessage(HttpMethod.Delete, url);
            using var response = await _http.SendAsync(request, token)
                .ConfigureAwait(false);

            if ((int)response.StatusCode == 501)
            {
                _logger.LogInformation(
                    "DeleteModel {Name}: Backend antwortete 501 — LM Studio managed Modelle ueber die App",
                    name);
                throw new NotSupportedException(
                    "Modell-Loeschung wird nicht mehr ueber PB Studio unterstuetzt. " +
                    "Bitte oeffne LM Studio -> My Models um das Modell zu entfernen.");
            }

            if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
            {
                LastErrorDetail = await CaptureErrorDetailAsync(response, token).ConfigureAwait(false);
                _logger.LogInformation("DeleteModel: {Name} nicht gefunden", name);
                return false;
            }
            if (!response.IsSuccessStatusCode)
            {
                LastErrorDetail = await CaptureErrorDetailAsync(response, token).ConfigureAwait(false)
                    ?? $"HTTP {(int)response.StatusCode} {response.ReasonPhrase}";
                return false;
            }
            LastErrorDetail = null;
            return true;
        }
        catch (NotSupportedException)
        {
            throw;
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, ct))
        {
            return false;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "DeleteModel {Name} fehlgeschlagen", name);
            return false;
        }
    }

    public async IAsyncEnumerable<PullProgressEvent> PullModelAsync(
        string name,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct = default)
    {
        // Hinweis: yield return darf NICHT in try/catch stehen (CS1626/CS1631).
        // Deshalb wickeln wir IO + Setup in OpenPullStreamAsync / ReadLineSafeAsync, die
        // bei Cancellation/Errors null liefern statt zu werfen.
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;

        var stream = await OpenPullStreamAsync(name, token, ct).ConfigureAwait(false);
        if (stream is null) yield break;

        try
        {
            using var reader = new System.IO.StreamReader(stream, System.Text.Encoding.UTF8);
            string? currentEvent = null;
            var dataBuffer = new System.Text.StringBuilder();

            while (true)
            {
                var (line, eof, cancelled) = await ReadLineSafeAsync(reader, token, ct).ConfigureAwait(false);
                if (cancelled) yield break;

                if (eof)
                {
                    if (dataBuffer.Length > 0)
                    {
                        var evtFlush = ParseEvent(currentEvent, dataBuffer.ToString());
                        if (evtFlush is not null) yield return evtFlush;
                    }
                    yield break;
                }

                if (line!.Length == 0)
                {
                    if (dataBuffer.Length > 0)
                    {
                        var evt = ParseEvent(currentEvent, dataBuffer.ToString());
                        if (evt is not null)
                        {
                            yield return evt;
                            if (evt.IsTerminal) yield break;
                        }
                    }
                    currentEvent = null;
                    dataBuffer.Clear();
                    continue;
                }

                if (line.StartsWith("event:", StringComparison.Ordinal))
                {
                    currentEvent = line.Substring(6).Trim();
                }
                else if (line.StartsWith("data:", StringComparison.Ordinal))
                {
                    if (dataBuffer.Length > 0) dataBuffer.Append('\n');
                    dataBuffer.Append(line.Substring(5).TrimStart());
                }
                // Andere SSE-Felder (id:, retry:) ignorieren wir.
            }
        }
        finally
        {
            stream.Dispose();
        }
    }

    /// <summary>Setup-Helfer fuer einen live verifizierten Ollama-Pull.</summary>
    private async Task<System.IO.Stream?> OpenPullStreamAsync(string name, CancellationToken token, CancellationToken originalCt)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/models/pull")
        {
            Content = JsonContent.Create(new { name }, options: JsonOptions),
        };
        // request bewusst NICHT disposen — der Lifetime ist an die Response gekoppelt,
        // und das Disposen waehrend der Streamkonsum kann den Socket killen. Der GC raeumt's.
        var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, token).ConfigureAwait(false);
        try
        {
            if ((int)response.StatusCode == 501)
            {
                _logger.LogInformation(
                    "PullModel {Name}: Backend antwortete 501 — LM Studio managed Downloads ueber die App",
                    name);
                throw new NotSupportedException(
                    "Modell-Download wird nicht mehr ueber PB Studio unterstuetzt. " +
                    "Bitte oeffne LM Studio -> Discover-Tab um das Modell herunterzuladen.");
            }

            if (!response.IsSuccessStatusCode)
            {
                LastErrorDetail = await CaptureErrorDetailAsync(response, token).ConfigureAwait(false)
                    ?? $"HTTP {(int)response.StatusCode} {response.ReasonPhrase}";
                response.Dispose();
                return null;
            }
            LastErrorDetail = null;
            return await response.Content.ReadAsStreamAsync(token).ConfigureAwait(false);
        }
        catch (NotSupportedException)
        {
            response.Dispose();
            throw;
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, originalCt))
        {
            response.Dispose();
            return null;
        }
        catch (Exception ex)
        {
            response.Dispose();
            _logger.LogWarning(ex, "PullModel({Name}): Stream-Open fehlgeschlagen", name);
            return null;
        }
    }

    private PullProgressEvent? ParseEvent(string? eventName, string data)
    {
        if (string.IsNullOrWhiteSpace(data)) return null;

        try
        {
            var doc = JsonDocument.Parse(data);
            var root = doc.RootElement;

            // pull_error-Event: Backend sendet {"error": "..."}.
            // pull_progress-Event: Ollama liefert {status, completed, total, digest}.
            string? status = null, digest = null, error = null;
            long? completed = null, total = null;

            if (root.TryGetProperty("status", out var st) && st.ValueKind == JsonValueKind.String)
                status = st.GetString();
            if (root.TryGetProperty("digest", out var dg) && dg.ValueKind == JsonValueKind.String)
                digest = dg.GetString();
            if (root.TryGetProperty("error", out var er) && er.ValueKind == JsonValueKind.String)
                error = er.GetString();
            if (root.TryGetProperty("completed", out var cp) && cp.ValueKind == JsonValueKind.Number && cp.TryGetInt64(out var cpVal))
                completed = cpVal;
            if (root.TryGetProperty("total", out var tt) && tt.ValueKind == JsonValueKind.Number && tt.TryGetInt64(out var ttVal))
                total = ttVal;

            // pull_error-Event hat keinen "status" — wir setzen ihn synthetisch
            if (error is not null && status is null)
                status = "error";

            return new PullProgressEvent(status, completed, total, digest, error);
        }
        catch (JsonException ex)
        {
            _logger.LogDebug(ex, "PullStream: ungueltige JSON-Zeile event={Event}, data={Data}", eventName, data);
            return null;
        }
    }
    #endregion
}
