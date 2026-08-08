using PBStudio.UI.Services;

namespace PBStudio.ConfirmationHarness;

internal static class Program
{
    [STAThread]
    private static int Main()
    {
        var confirmed = new DialogService().ConfirmDestructiveAction(
            "Alle Audio-Clips löschen",
            "ALLE 3 Audio-Clips dauerhaft löschen?");
        return confirmed ? 2 : 0;
    }
}
