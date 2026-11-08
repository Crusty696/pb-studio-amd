namespace PBStudio.UI.Helpers;

/// <summary>Maps timeline positions to source or rendered-preview time.</summary>
public static class TimelineSeekCalculator
{
    public static double ToSourcePosition(
        double selectedTimelinePosition,
        double clipTimelineStart,
        double clipSourceStart,
        double clipSourceDuration)
    {
        var duration = Math.Max(0.0, clipSourceDuration);
        var offset = Math.Clamp(selectedTimelinePosition - clipTimelineStart, 0.0, duration);
        return clipSourceStart + offset;
    }

    public static double? ToRenderedPreviewPosition(
        double selectedTimelinePosition,
        double previewTimelineStart,
        double previewDuration)
    {
        var offset = selectedTimelinePosition - previewTimelineStart;
        var duration = Math.Max(0.0, previewDuration);
        if (offset < 0.0 || offset > duration)
            return null;

        return Math.Clamp(offset, 0.0, duration);
    }
}
