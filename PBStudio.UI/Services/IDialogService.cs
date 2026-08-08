using System.Collections.Generic;

namespace PBStudio.UI.Services;

/// <summary>
/// Service für native Windows-Dateidialoge.
/// </summary>
public interface IDialogService
{
    /// <summary>
    /// Öffnet einen Dialog zur Auswahl einer einzelnen Datei.
    /// </summary>
    string? OpenFile(string title, string filter, string? initialDirectory = null);

    /// <summary>
    /// Öffnet einen Dialog zur Auswahl mehrerer Dateien.
    /// </summary>
    List<string> OpenFiles(string title, string filter, string? initialDirectory = null);

    /// <summary>
    /// Öffnet einen Dialog zur Auswahl eines Ordners (.NET 9 native).
    /// </summary>
    string? OpenFolder(string title, string? initialDirectory = null);

    /// <summary>
    /// Öffnet einen Dialog zum Speichern einer Datei.
    /// </summary>
    string? SaveFile(string title, string filter, string defaultFileName, string? initialDirectory = null);

    /// <summary>
    /// Fordert vor einer irreversiblen Aktion eine ausdrückliche Bestätigung an.
    /// </summary>
    bool ConfirmDestructiveAction(string title, string message);
}
