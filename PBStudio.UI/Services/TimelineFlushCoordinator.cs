using System.Windows.Threading;

namespace PBStudio.UI.Services;

public sealed class TimelineFlushCoordinator : ITimelineFlushCoordinator, IDisposable
{
    private readonly object _registrationLock = new();
    private readonly SemaphoreSlim _flushGate = new(1, 1);
    private Registration? _active;
    private bool _disposed;

    public IDisposable Register(
        Dispatcher dispatcher,
        Func<CancellationToken, Task<TimelineFlushResult>> flushAsync)
    {
        ArgumentNullException.ThrowIfNull(dispatcher);
        ArgumentNullException.ThrowIfNull(flushAsync);

        lock (_registrationLock)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            var registration = new Registration(this, dispatcher, flushAsync);
            _active = registration;
            return registration;
        }
    }

    public async Task<TimelineFlushResult> FlushAsync(
        CancellationToken cancellationToken = default)
    {
        try
        {
            await _flushGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            return TimelineFlushResult.CancelledResult();
        }

        try
        {
            Registration? registration;
            lock (_registrationLock)
            {
                if (_disposed)
                    return TimelineFlushResult.Failed("Timeline-Flush-Koordinator ist beendet.");
                registration = _active;
            }

            if (registration is null)
                return TimelineFlushResult.Succeeded;

            try
            {
                if (registration.Dispatcher.CheckAccess())
                    return await registration.FlushAsync(cancellationToken);

                return await registration.Dispatcher
                    .InvokeAsync(() => registration.FlushAsync(cancellationToken))
                    .Task
                    .Unwrap()
                    .ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return TimelineFlushResult.CancelledResult();
            }
            catch (Exception ex)
            {
                return TimelineFlushResult.Failed(ex.Message);
            }
        }
        finally
        {
            _flushGate.Release();
        }
    }

    private void Unregister(Registration registration)
    {
        lock (_registrationLock)
        {
            if (ReferenceEquals(_active, registration))
                _active = null;
        }
    }

    public void Dispose()
    {
        lock (_registrationLock)
        {
            if (_disposed)
                return;
            _disposed = true;
            _active = null;
        }
        _flushGate.Dispose();
    }

    private sealed class Registration(
        TimelineFlushCoordinator owner,
        Dispatcher dispatcher,
        Func<CancellationToken, Task<TimelineFlushResult>> flushAsync) : IDisposable
    {
        private int _disposed;

        public Dispatcher Dispatcher { get; } = dispatcher;
        public Func<CancellationToken, Task<TimelineFlushResult>> FlushAsync { get; } = flushAsync;

        public void Dispose()
        {
            if (Interlocked.Exchange(ref _disposed, 1) == 0)
                owner.Unregister(this);
        }
    }
}
