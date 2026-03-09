namespace PBStudio.UI.Services;

/// <summary>
/// Einfacher Navigation Service für Tab-Wechsel.
/// </summary>
public class NavigationService
{
    public event EventHandler<int>? NavigationRequested;

    public void NavigateTo(int tabIndex)
    {
        NavigationRequested?.Invoke(this, tabIndex);
    }
}
