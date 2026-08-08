namespace PBStudio.UI.Models;

/// <summary>
/// Ein manueller Anker: fixiert einen Video-Clip auf eine Zeit im Mix.
///
/// Audit 2026-08-06 (T4.3): Der ANCHOR-Tab mutierte bis dahin nur eine
/// ObservableCollection — es gab weder Route noch Schema noch Persistenz, und
/// beim Projektwechsel wurde die Liste geleert. Die Pacing-Engine konnte
/// manuelle Anker laengst, aber ausschliesslich aus einem Obsidian-.canvas-File.
/// Diese DTOs sind die fehlende Bruecke.
/// </summary>
public record AnchorEntry(
    double Time,
    string Label = "",
    int? VideoClipId = null);

/// <summary>Antwort von <c>GET/POST /project/anchors</c>.</summary>
public record AnchorListResponse(
    List<AnchorEntry>? Anchors = null,
    int Count = 0);
