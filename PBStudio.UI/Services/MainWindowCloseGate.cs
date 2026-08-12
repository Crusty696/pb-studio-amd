namespace PBStudio.UI.Services;

public sealed record MainWindowCloseResult(
    bool Authorized,
    bool InProgress,
    string? ErrorMessage);

public sealed class MainWindowCloseGate(ProjectService projectService)
{
    private int _running;
    private int _authorized;

    public bool IsAuthorized => Volatile.Read(ref _authorized) != 0;

    public void AuthorizeWithoutSave() =>
        Interlocked.Exchange(ref _authorized, 1);

    public async Task<MainWindowCloseResult> TryAuthorizeAsync()
    {
        if (IsAuthorized)
            return new MainWindowCloseResult(true, false, null);
        if (Interlocked.CompareExchange(ref _running, 1, 0) != 0)
            return new MainWindowCloseResult(false, true, null);

        try
        {
            var saved = !projectService.HasProject
                || await projectService.SaveProjectAsync();
            if (!saved)
            {
                var flushFailure = projectService.LastTimelineFlushResult;
                var errorMessage = flushFailure.Success
                    ? "Projekt konnte nicht gespeichert werden."
                    : flushFailure.Cancelled
                        ? "Timeline-Speicherung wurde abgebrochen: "
                            + (flushFailure.ErrorMessage ?? "Abbruch ohne Detailgrund.")
                        : flushFailure.ErrorMessage
                            ?? "Timeline konnte nicht gespeichert werden.";
                return new MainWindowCloseResult(
                    false,
                    false,
                    errorMessage);
            }

            Interlocked.Exchange(ref _authorized, 1);
            return new MainWindowCloseResult(true, false, null);
        }
        catch (Exception ex)
        {
            return new MainWindowCloseResult(false, false, ex.Message);
        }
        finally
        {
            Interlocked.Exchange(ref _running, 0);
        }
    }
}
