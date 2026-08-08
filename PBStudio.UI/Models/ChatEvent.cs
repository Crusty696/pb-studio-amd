using System.Collections.Generic;

namespace PBStudio.UI.Models;

// =====================================================================
// SSE-Events vom Backend POST /chat/message.
//
// Frame-Schema:
//   event: <type>\n
//   data: <json>\n\n
//
// Types:
//   - "model":       { model: str, reason: str, mode: str }
//   - "text":        { content: str }
//   - "tool_call":   { name: str, arguments: dict|str|null }
//   - "tool_result": { name: str, result: dict }
//   - "error":       { message: str, stage: str }
//   - "done":        { final_text?: str, reason?: str }
// =====================================================================

public enum ChatEventType
{
    Unknown,
    Model,
    Text,
    ToolCall,
    ToolConfirmationRequired,
    ToolResult,
    Error,
    Done,
}

/// <summary>Ein Event aus dem Chat-SSE-Stream.</summary>
public record ChatStreamEvent(
    ChatEventType Type,
    string RawEventName,
    string? Text = null,
    string? ModelName = null,
    string? ModelReason = null,
    string? ToolName = null,
    string? ToolArgumentsJson = null,
    string? ConfirmationId = null,
    double? ConfirmationExpiresInSeconds = null,
    string? ToolResultJson = null,
    string? ErrorMessage = null,
    string? ErrorStage = null,
    string? DoneReason = null);
