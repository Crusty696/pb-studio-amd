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
    // =====================================================================
    // Chat (KI-Chat Track 2026-05-16)
    // =====================================================================

    public async IAsyncEnumerable<ChatStreamEvent> SendChatMessageAsync(
        string message,
        IReadOnlyList<ChatMessage>? history = null,
        string mode = "balance",
        bool saveHistory = true,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct = default)
    {
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;

        var historyPayload = history?
            .Where(m => m.Role == ChatRole.User || m.Role == ChatRole.Assistant)
            .Select(m => new
            {
                role = m.Role == ChatRole.User ? "user" : "assistant",
                content = m.Content ?? string.Empty,
            })
            .ToList();

        var body = new
        {
            message,
            history = historyPayload,
            mode,
            save_history = saveHistory,
        };

        var stream = await OpenChatStreamAsync(body, token, ct).ConfigureAwait(false);
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
                        var ev = ParseChatEvent(currentEvent, dataBuffer.ToString());
                        if (ev is not null) yield return ev;
                    }
                    yield break;
                }

                if (line!.Length == 0)
                {
                    if (dataBuffer.Length > 0)
                    {
                        var ev = ParseChatEvent(currentEvent, dataBuffer.ToString());
                        if (ev is not null)
                        {
                            yield return ev;
                            if (ev.Type == ChatEventType.Done)
                            {
                                yield break;
                            }
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
            }
        }
        finally
        {
            stream.Dispose();
        }
    }

    private async Task<System.IO.Stream?> OpenChatStreamAsync(object body, CancellationToken token, CancellationToken originalCt)
    {
        try
        {
            var request = new HttpRequestMessage(HttpMethod.Post, "/chat/message")
            {
                Content = JsonContent.Create(body, options: JsonOptions),
            };
            var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, token).ConfigureAwait(false);
            try
            {
                response.EnsureSuccessStatusCode();
                return await response.Content.ReadAsStreamAsync(token).ConfigureAwait(false);
            }
            catch
            {
                response.Dispose();
                throw;
            }
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, originalCt))
        {
            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "SendChatMessageAsync: Failed to open stream");
            throw;
        }
    }

    private static ChatStreamEvent? ParseChatEvent(string? eventName, string dataJson)
    {
        if (string.IsNullOrWhiteSpace(dataJson)) return null;
        JsonElement root;
        try
        {
            using var doc = JsonDocument.Parse(dataJson);
            root = doc.RootElement.Clone();
        }
        catch (JsonException)
        {
            return new ChatStreamEvent(ChatEventType.Unknown, eventName ?? "unknown");
        }

        var type = eventName?.ToLowerInvariant() switch
        {
            "model" => ChatEventType.Model,
            "text" => ChatEventType.Text,
            "text_delta" => ChatEventType.TextDelta,
            "tool_call" => ChatEventType.ToolCall,
            "tool_confirmation_required" => ChatEventType.ToolConfirmationRequired,
            "tool_result" => ChatEventType.ToolResult,
            "error" => ChatEventType.Error,
            "done" => ChatEventType.Done,
            _ => ChatEventType.Unknown,
        };

        string? Str(string key) => root.TryGetProperty(key, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
        string? RawJson(string key) => root.TryGetProperty(key, out var v) ? v.GetRawText() : null;

        return type switch
        {
            ChatEventType.Model => new ChatStreamEvent(type, eventName!, ModelName: Str("model"), ModelReason: Str("reason")),
            ChatEventType.Text => new ChatStreamEvent(type, eventName!, Text: Str("content")),
            ChatEventType.TextDelta => new ChatStreamEvent(type, eventName!, Text: Str("delta") ?? Str("content")),
            ChatEventType.ToolCall => new ChatStreamEvent(type, eventName!, ToolName: Str("name"), ToolArgumentsJson: RawJson("arguments"), ToolCallId: Str("id")),
            ChatEventType.ToolConfirmationRequired => new ChatStreamEvent(
                type,
                eventName!,
                ToolName: Str("name"),
                ToolArgumentsJson: RawJson("arguments"),
                ConfirmationId: Str("confirmation_id"),
                ConfirmationExpiresInSeconds: root.TryGetProperty("expires_in_seconds", out var expires)
                    && expires.TryGetDouble(out var seconds) ? seconds : null),
            ChatEventType.ToolResult => new ChatStreamEvent(type, eventName!, ToolName: Str("name"), ToolResultJson: RawJson("result"), ToolCallId: Str("id")),
            ChatEventType.Error => new ChatStreamEvent(type, eventName!, ErrorMessage: Str("message"), ErrorStage: Str("stage"), ToolCallId: Str("tool_call_id")),
            ChatEventType.Done => new ChatStreamEvent(type, eventName!, Text: Str("final_text"), DoneReason: Str("reason")),
            _ => new ChatStreamEvent(type, eventName ?? "unknown"),
        };
    }

    public async Task<bool> DecideChatToolConfirmationAsync(
        string confirmationId, bool approve, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(confirmationId)) return false;
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        var decision = approve ? "approve" : "reject";
        try
        {
            using var response = await _http.PostAsync(
                $"/chat/confirm/{Uri.EscapeDataString(confirmationId)}/{decision}",
                content: null,
                token).ConfigureAwait(false);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex) when (IsExpectedCancellation(ex, ct))
        {
            return false;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Chat tool confirmation failed");
            return false;
        }
    }

    public async Task<bool> ClearChatHistoryAsync(CancellationToken ct = default)
    {
        using var requestCts = ct.CanBeCanceled
            ? CancellationTokenSource.CreateLinkedTokenSource(ct, _shutdownCts.Token)
            : null;
        var token = requestCts?.Token ?? _shutdownCts.Token;
        try
        {
            using var response = await _http.DeleteAsync("/chat/history", token).ConfigureAwait(false);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "ClearChatHistoryAsync failed");
            return false;
        }
    }
}
