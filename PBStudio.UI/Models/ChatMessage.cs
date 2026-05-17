using System;
using System.Collections.Generic;

namespace PBStudio.UI.Models;

// =====================================================================
// Chat-Datenmodelle fuer den KI-Chat-Tab (Ollama Tool-Use).
// Spiegeln das SSE-Protokoll des Backends (POST /chat/message).
// =====================================================================

public enum ChatRole
{
    User,
    Assistant,
    Tool,
    System,
}

/// <summary>Eine einzelne Chat-Nachricht in der Konversation.</summary>
public record ChatMessage(
    ChatRole Role,
    string Content,
    DateTime Timestamp,
    bool IsStreaming = false,
    string? ModelName = null,
    IReadOnlyList<ToolCallInfo>? ToolCalls = null,
    string? Error = null)
{
    public static ChatMessage CreateUser(string content) =>
        new(ChatRole.User, content, DateTime.Now);

    public static ChatMessage CreateAssistant(string content, string? modelName = null, bool isStreaming = false) =>
        new(ChatRole.Assistant, content, DateTime.Now, IsStreaming: isStreaming, ModelName: modelName);

    public static ChatMessage CreateError(string error) =>
        new(ChatRole.Assistant, "", DateTime.Now, Error: error);
}

/// <summary>Info-Block fuer einen vom LLM ausgeloesten Tool-Call (UI-Anzeige).</summary>
public record ToolCallInfo(
    string Name,
    string? ArgumentsJson,
    string? ResultJson = null,
    bool IsCompleted = false,
    string? Error = null);
