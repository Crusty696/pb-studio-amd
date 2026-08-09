using System;
using System.Collections.Generic;
using System.Linq;

namespace PBStudio.UI.Helpers;

public enum SnapPointType
{
    Playhead,
    Beat,
    Onset,
    ClipEdge
}

public record SnapPoint(double Time, SnapPointType Type);

public class SnapEngine
{
    private readonly double _pixelThreshold;
    public double PixelsPerSecond { private get; set; }

    public SnapEngine(double pixelThreshold, double pixelsPerSecond)
    {
        _pixelThreshold = pixelThreshold;
        PixelsPerSecond = pixelsPerSecond;
    }

    /// <summary>
    /// Finds the best snap point for a given time.
    /// Priority: Playhead > Beat > Onset > ClipEdge.
    /// </summary>
    public SnapPoint? FindSnapPoint(double time, IEnumerable<SnapPoint> availablePoints)
    {
        double timeThreshold = _pixelThreshold / Math.Max(PixelsPerSecond, 0.001);
        
        var candidates = availablePoints
            .Select(p => new { Point = p, Distance = Math.Abs(p.Time - time) })
            .Where(x => x.Distance <= timeThreshold)
            .OrderBy(x => x.Distance)
            .ToList();

        if (!candidates.Any()) return null;

        // If equidistant or close, apply priority logic
        var closestDistance = candidates.First().Distance;
        var ties = candidates.Where(c => Math.Abs(c.Distance - closestDistance) < 0.001).ToList();

        if (ties.Count > 1)
        {
            return ties
                .OrderBy(t => GetPriority(t.Point.Type))
                .First().Point;
        }

        return candidates.First().Point;
    }

    private int GetPriority(SnapPointType type)
    {
        return type switch
        {
            SnapPointType.Playhead => 0,
            SnapPointType.Beat => 1,
            SnapPointType.Onset => 2,
            SnapPointType.ClipEdge => 3,
            _ => 99
        };
    }
}
