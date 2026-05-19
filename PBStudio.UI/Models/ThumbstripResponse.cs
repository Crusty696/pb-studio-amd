using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace PBStudio.UI.Models;

/// <summary>
/// Antwort von <c>GET /video/thumbstrip/{clip_id}?n=8</c>.
/// Liefert n gleichmaessig ueber die Cliplaenge verteilte Thumbnail-Frames
/// als Base64-encoded JPEG-Strings — fuer die Multi-Lane-Timeline-Strip-Ansicht.
/// </summary>
public record ThumbstripResponse
{
    [JsonPropertyName("clip_id")] public int ClipId { get; init; }
    [JsonPropertyName("count")] public int Count { get; init; }
    [JsonPropertyName("frames")] public List<string> Frames { get; init; } = new();
}
