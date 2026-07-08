using System;
using System.Globalization;
using System.Windows;
using System.Windows.Media;

namespace PBStudio.UI.Helpers;

public class RulerRenderer
{
    // B5-Fix (2026-05-19): _children war never-used (CS0169 + CS8618 Non-Nullable).
    // Entfernt — Rendering nutzt direkt DrawingContext, keine VisualCollection.
    private readonly DrawingVisual _drawingVisual;

    public RulerRenderer(Visual parent)
    {
        _drawingVisual = new DrawingVisual();
    }

    public void Render(DrawingContext dc, double totalDuration, double pixelsPerSecond, double actualWidth, Brush textBrush, Brush lineBrush)
    {
        if (totalDuration <= 0 || pixelsPerSecond <= 0) return;

        double interval = GetInterval(pixelsPerSecond);
        var typeface = new Typeface("Segoe UI");
        var culture = CultureInfo.CurrentCulture;

        for (double t = 0; t <= totalDuration; t += interval)
        {
            double x = t * pixelsPerSecond;
            if (x > actualWidth + 100) break; // Optimization: only draw visible

            // Long mark
            dc.DrawLine(new Pen(lineBrush, 1), new Point(x, 0), new Point(x, 15));

            // Text
            var text = new FormattedText(
                TimeSpan.FromSeconds(t).ToString(@"mm\:ss"),
                culture,
                FlowDirection.LeftToRight,
                typeface,
                9,
                textBrush,
                VisualTreeHelper.GetDpi(new DrawingVisual()).PixelsPerDip);
            
            dc.DrawText(text, new Point(x + 2, 10));

            // Short marks
            if (interval > 1.0)
            {
                double halfX = (t + interval / 2.0) * pixelsPerSecond;
                if (halfX <= actualWidth)
                {
                    dc.DrawLine(new Pen(lineBrush, 0.5), new Point(halfX, 0), new Point(halfX, 6));
                }
            }
        }
    }

    private double GetInterval(double pps)
    {
        if (pps > 100) return 1.0;
        if (pps > 50) return 5.0;
        if (pps < 20) return 30.0;
        return 10.0;
    }
}
