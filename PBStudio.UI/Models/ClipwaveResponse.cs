using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace PBStudio.UI.Models;

/// <summary>
/// Antwort von <c>GET /video/clipwave/{clip_id}?n=256</c>.
/// Downsampled Mono-Peaks (0..1) fuer per-Clip-Mini-Waveforms in der Timeline.
/// </summary>
public record ClipwaveResponse
{
    [JsonPropertyName("clip_id")] public int ClipId { get; init; }
    [JsonPropertyName("count")] public int Count { get; init; }
    [JsonPropertyName("peaks")] public List<float> Peaks { get; init; } = new();
}
