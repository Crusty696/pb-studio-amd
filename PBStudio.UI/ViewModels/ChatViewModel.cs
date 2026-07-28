using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Models;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>
/// ViewModel fuer den KI-Chat-Tab (Ollama Tool-Use, Phase 2026-05-16).
///
/// Verbindet sich mit dem Backend-SSE-Stream <c>POST /chat/message</c>, parsed
/// die Events (model/text/tool_call/tool_result/error/done) und baut daraus
/// <see cref="ChatMessageViewModel"/>-Eintraege fuer die UI auf.
///
/// User kann in DE oder EN tippen, der Bot antwortet in derselben Sprache.
/// </summary>
public partial class ChatViewModel : ObservableObject, IDisposable
{
    private readonly IApiClient _api;
    private readonly ILogger<ChatViewModel>? _logger;
    private CancellationTokenSource? _streamCts;
    private int _streamGeneration;
    private bool _disposed;

    [ObservableProperty] private string _inputText = string.Empty;
    [ObservableProperty] private bool _isStreaming;
    [ObservableProperty] private string _mode = "balance";
    [ObservableProperty] private string _statusText = "Bereit. Frag mich was zu deinem Projekt.";
    [ObservableProperty] private string? _currentModel;

    public ObservableCollection<ChatMessageViewModel> Messages { get; } = new();

    public IReadOnlyList<string> Modes { get; } = new[] { "speed", "balance", "quality" };

    public ChatViewModel(IApiClient api, ILogger<ChatViewModel>? logger = null)
    {
        _api = api;
        _logger = logger;
        AddWelcomeMessage();
    }

    private void AddWelcomeMessage()
    {
        Messages.Add(new ChatMessageViewModel(
            ChatMessage.CreateAssistant(
                "Hi! Ich bin der KI-Assistent von PB Studio.\n\n" +
                "Du kannst mich auf Deutsch oder English fragen. Beispiele:\n" +
                "• \"Liste meine Audio-Clips\"\n" +
                "• \"Analyze video clip 3\"\n" +
                "• \"Generiere ein Pacing fuer Audio-Clip 1 mit Brain\"\n" +
                "• \"Show me the brain stats\"")));
    }

    public bool CanSend => !IsStreaming && !string.IsNullOrWhiteSpace(InputText);

    partial void OnInputTextChanged(string value) => SendCommand.NotifyCanExecuteChanged();
    partial void OnIsStreamingChanged(bool value)
    {
        SendCommand.NotifyCanExecuteChanged();
        StopCommand.NotifyCanExecuteChanged();
    }

    [RelayCommand(CanExecute = nameof(CanSend))]
    public async Task SendAsync()
    {
        if (_disposed) return;

        var userText = (InputText ?? string.Empty).Trim();
        if (userText.Length == 0) return;
        InputText = string.Empty;

        var userMsg = ChatMessage.CreateUser(userText);
        Messages.Add(new ChatMessageViewModel(userMsg));

        var historyForBackend = Messages
            .Where(m => !m.IsStreaming && (m.Role == ChatRole.User || m.Role == ChatRole.Assistant))
            .Where(m => !ReferenceEquals(m.Message, userMsg))  // exclude the just-added user msg (backend re-adds it)
            .TakeLast(40)  // limit history sent over the wire
            .Select(m => m.Message)
            .ToList();

        var assistantVm = new ChatMessageViewModel(
            ChatMessage.CreateAssistant("", isStreaming: true));
        Messages.Add(assistantVm);

        IsStreaming = true;
        StatusText = "Frage Modell...";
        var generation = Interlocked.Increment(ref _streamGeneration);
        var previous = _streamCts;
        var current = new CancellationTokenSource();
        _streamCts = current;
        previous?.Cancel();
        var token = current.Token;

        var textBuilder = new System.Text.StringBuilder();
        var toolCalls = new List<ToolCallInfo>();
        string? errorMessage = null;

        try
        {
            await foreach (var ev in _api.SendChatMessageAsync(
                userText,
                historyForBackend,
                Mode,
                saveHistory: true,
                ct: token).ConfigureAwait(true))
            {
                if (_disposed
                    || generation != Volatile.Read(ref _streamGeneration)
                    || token.IsCancellationRequested)
                {
                    break;
                }

                switch (ev.Type)
                {
                    case ChatEventType.Model:
                        CurrentModel = ev.ModelName;
                        StatusText = $"Modell: {ev.ModelName} ({ev.ModelReason})";
                        assistantVm.UpdateModelName(ev.ModelName);
                        break;
                    case ChatEventType.Text:
                        if (!string.IsNullOrEmpty(ev.Text))
                        {
                            textBuilder.Clear();
                            textBuilder.Append(ev.Text);
                            assistantVm.UpdateContent(textBuilder.ToString());
                        }
                        break;
                    case ChatEventType.ToolCall:
                        var tc = new ToolCallInfo(
                            Name: ev.ToolName ?? "(unknown)",
                            ArgumentsJson: ev.ToolArgumentsJson);
                        toolCalls.Add(tc);
                        assistantVm.AddOrUpdateToolCall(tc);
                        StatusText = $"Tool: {tc.Name}";
                        break;
                    case ChatEventType.ToolResult:
                        var lastIdx = toolCalls.FindLastIndex(t => t.Name == (ev.ToolName ?? ""));
                        if (lastIdx >= 0)
                        {
                            var prev = toolCalls[lastIdx];
                            var updated = prev with { ResultJson = ev.ToolResultJson, IsCompleted = true };
                            toolCalls[lastIdx] = updated;
                            assistantVm.AddOrUpdateToolCall(updated);
                        }
                        else
                        {
                            var newTc = new ToolCallInfo(
                                Name: ev.ToolName ?? "(unknown)",
                                ArgumentsJson: null,
                                ResultJson: ev.ToolResultJson,
                                IsCompleted: true);
                            toolCalls.Add(newTc);
                            assistantVm.AddOrUpdateToolCall(newTc);
                        }
                        break;
                    case ChatEventType.Error:
                        errorMessage = ev.ErrorMessage ?? "Unbekannter Fehler";
                        assistantVm.SetError(errorMessage);
                        StatusText = $"Fehler: {errorMessage}";
                        break;
                    case ChatEventType.Done:
                        if (!string.IsNullOrEmpty(ev.Text) && textBuilder.Length == 0)
                        {
                            textBuilder.Append(ev.Text);
                            assistantVm.UpdateContent(textBuilder.ToString());
                        }
                        break;
                }
            }
        }
        catch (OperationCanceledException)
        {
            if (!_disposed && generation == Volatile.Read(ref _streamGeneration))
                assistantVm.AppendContent("\n[abgebrochen]");
        }
        catch (Exception ex)
        {
            _logger?.LogError(ex, "Chat-Stream fehlgeschlagen");
            if (!_disposed && generation == Volatile.Read(ref _streamGeneration))
                assistantVm.SetError($"Chat-Stream-Fehler: {ex.Message}");
        }
        finally
        {
            current.Dispose();
            if (ReferenceEquals(_streamCts, current))
                _streamCts = null;

            if (!_disposed && generation == Volatile.Read(ref _streamGeneration))
            {
                assistantVm.MarkComplete();
                IsStreaming = false;
                if (errorMessage is null)
                    StatusText = $"Bereit. ({toolCalls.Count} Tool-Calls)";
            }
        }
    }

    [RelayCommand(CanExecute = nameof(IsStreaming))]
    public void Stop()
    {
        _streamCts?.Cancel();
    }

    [RelayCommand]
    public async Task ClearAsync()
    {
        if (_disposed) return;

        Interlocked.Increment(ref _streamGeneration);
        _streamCts?.Cancel();
        IsStreaming = false;
        await _api.ClearChatHistoryAsync().ConfigureAwait(true);
        if (_disposed) return;

        Messages.Clear();
        AddWelcomeMessage();
        StatusText = "History geleert.";
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        Interlocked.Increment(ref _streamGeneration);
        _streamCts?.Cancel();
        _streamCts = null;
    }
}

/// <summary>Pro-Nachricht-ViewModel mit beobachtbarem Content + Tool-Calls.</summary>
public partial class ChatMessageViewModel : ObservableObject
{
    [ObservableProperty] private string _content;
    [ObservableProperty] private bool _isStreaming;
    [ObservableProperty] private string? _modelName;
    [ObservableProperty] private string? _errorText;

    public ChatRole Role { get; }
    public DateTime Timestamp { get; }
    public ChatMessage Message { get; private set; }

    public ObservableCollection<ToolCallInfo> ToolCalls { get; } = new();

    public bool IsUser => Role == ChatRole.User;
    public bool IsAssistant => Role == ChatRole.Assistant;
    public bool HasToolCalls => ToolCalls.Count > 0;
    public bool HasError => !string.IsNullOrEmpty(ErrorText);
    public string TimestampDisplay => Timestamp.ToString("HH:mm:ss");
    public string RoleLabel => Role switch
    {
        ChatRole.User => "Du",
        ChatRole.Assistant => "PB Studio",
        ChatRole.Tool => "Tool",
        _ => Role.ToString(),
    };

    public ChatMessageViewModel(ChatMessage msg)
    {
        Message = msg;
        Role = msg.Role;
        Timestamp = msg.Timestamp;
        _content = msg.Content ?? string.Empty;
        _isStreaming = msg.IsStreaming;
        _modelName = msg.ModelName;
        _errorText = msg.Error;
        if (msg.ToolCalls is not null)
        {
            foreach (var tc in msg.ToolCalls)
                ToolCalls.Add(tc);
        }
    }

    public void UpdateContent(string content)
    {
        Content = content;
    }

    public void AppendContent(string append)
    {
        Content += append;
    }

    public void UpdateModelName(string? model)
    {
        ModelName = model;
    }

    public void AddOrUpdateToolCall(ToolCallInfo tc)
    {
        var idx = -1;
        for (int i = 0; i < ToolCalls.Count; i++)
        {
            if (ToolCalls[i].Name == tc.Name && !ToolCalls[i].IsCompleted)
            {
                idx = i;
                break;
            }
        }
        if (idx >= 0)
        {
            ToolCalls[idx] = tc;
        }
        else
        {
            ToolCalls.Add(tc);
        }
        OnPropertyChanged(nameof(HasToolCalls));
    }

    public void SetError(string error)
    {
        ErrorText = error;
        OnPropertyChanged(nameof(HasError));
    }

    public void MarkComplete()
    {
        IsStreaming = false;
        Message = Message with
        {
            Content = Content,
            IsStreaming = false,
            Error = ErrorText,
            ModelName = ModelName,
            ToolCalls = ToolCalls.Count > 0 ? ToolCalls.ToList() : null,
        };
    }
}
