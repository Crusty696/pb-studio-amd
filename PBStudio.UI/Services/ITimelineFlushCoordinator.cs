using System.Windows.Threading;

namespace PBStudio.UI.Services;

public sealed record TimelineFlushResult(
    bool Success,
    bool Cancelled,
    string? ErrorMessage)
{
    public static TimelineFlushResult Succeeded { get; } = new(true, false, null);

    public static TimelineFlushResult Failed(string errorMessage) =>
        new(false, false, errorMessage);

    public static TimelineFlushResult CancelledResult(string? errorMessage = null) =>
        new(false, true, errorMessage ?? "Timeline-Speicherung wurde abgebrochen.");
}

public interface ITimelineFlushCoordinator
{
    IDisposable Register(
        Dispatcher dispatcher,
        Func<CancellationToken, Task<TimelineFlushResult>> flushAsync);

    Task<TimelineFlushResult> FlushAsync(CancellationToken cancellationToken = default);
}
