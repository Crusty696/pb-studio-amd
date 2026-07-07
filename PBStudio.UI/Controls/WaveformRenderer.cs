using System;
using System.Collections.Generic;
using System.Collections.Specialized;
using System.Windows;
using System.Windows.Media;
using PBStudio.UI.Models;

namespace PBStudio.UI.Controls;

/// <summary>
/// GPU-beschleunigtes Custom Control für das performante Zeichnen der Wellenform.
/// Rendert die gesamte Amplitude in einer einzigen zusammenhängenden StreamGeometry.
/// </summary>
public class WaveformRenderer : FrameworkElement
{
    public static readonly DependencyProperty WaveformBarsProperty =
        DependencyProperty.Register(nameof(WaveformBars), typeof(IEnumerable<WaveformBarModel>), typeof(WaveformRenderer),
            new FrameworkPropertyMetadata(null, FrameworkPropertyMetadataOptions.AffectsRender, OnWaveformBarsChanged));

    public IEnumerable<WaveformBarModel> WaveformBars
    {
        get => (IEnumerable<WaveformBarModel>)GetValue(WaveformBarsProperty);
        set => SetValue(WaveformBarsProperty, value);
    }

    public static readonly DependencyProperty PixelsPerSecondProperty =
        DependencyProperty.Register(nameof(PixelsPerSecond), typeof(double), typeof(WaveformRenderer),
            new FrameworkPropertyMetadata(100.0, FrameworkPropertyMetadataOptions.AffectsRender));

    public double PixelsPerSecond
    {
        get => (double)GetValue(PixelsPerSecondProperty);
        set => SetValue(PixelsPerSecondProperty, value);
    }

    public static readonly DependencyProperty FillBrushProperty =
        DependencyProperty.Register(nameof(FillBrush), typeof(Brush), typeof(WaveformRenderer),
            new FrameworkPropertyMetadata(Brushes.DodgerBlue));

    public Brush FillBrush
    {
        get => (Brush)GetValue(FillBrushProperty);
        set => SetValue(FillBrushProperty, value);
    }

    // AP3.4 (Audit 2026-06-10): TimelineViewModel mutiert WaveformBars in-place
    // (Clear()+Add() — Property-Referenz bleibt identisch), das DP-Changed-Event
    // feuerte dadurch nie und die Waveform erschien erst bei Zoom/Resize.
    // Fix: bei INotifyCollectionChanged-Quellen auf CollectionChanged (un)subscriben.
    private static void OnWaveformBarsChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not WaveformRenderer renderer) return;

        if (e.OldValue is INotifyCollectionChanged oldCol)
            oldCol.CollectionChanged -= renderer.OnBarsCollectionChanged;
        if (e.NewValue is INotifyCollectionChanged newCol)
            newCol.CollectionChanged += renderer.OnBarsCollectionChanged;

        renderer.InvalidateVisual();
    }

    private void OnBarsCollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
        => InvalidateVisual();

    protected override void OnRender(DrawingContext drawingContext)
    {
        base.OnRender(drawingContext);

        if (WaveformBars == null) return;

        double height = ActualHeight;
        if (height <= 0) height = 80;
        double mid = height / 2.0;

        StreamGeometry geometry = new StreamGeometry();
        using (StreamGeometryContext ctx = geometry.Open())
        {
            bool first = true;
            double lastX = 0;
            var barList = new List<WaveformBarModel>();

            // 1. Obere Hälfte von links nach rechts zeichnen
            foreach (var bar in WaveformBars)
            {
                barList.Add(bar);
                double xStart = bar.X * PixelsPerSecond;
                double xEnd = (bar.X + bar.Width) * PixelsPerSecond;
                double topY = mid - (bar.Height / 2.0);

                if (first)
                {
                    ctx.BeginFigure(new Point(xStart, mid), true, true);
                    ctx.LineTo(new Point(xStart, topY), true, false);
                    ctx.LineTo(new Point(xEnd, topY), true, false);
                    first = false;
                }
                else
                {
                    ctx.LineTo(new Point(xStart, topY), true, false);
                    ctx.LineTo(new Point(xEnd, topY), true, false);
                }
                lastX = xEnd;
            }

            if (first || barList.Count == 0) return; // Keine Daten gezeichnet

            // Rechte Kante auf die Mitte setzen
            ctx.LineTo(new Point(lastX, mid), true, false);

            // 2. Untere Hälfte von rechts nach links zurückzeichnen (Spiegelung)
            for (int i = barList.Count - 1; i >= 0; i--)
            {
                var bar = barList[i];
                double xStart = bar.X * PixelsPerSecond;
                double xEnd = (bar.X + bar.Width) * PixelsPerSecond;
                double bottomY = mid + (bar.Height / 2.0);

                ctx.LineTo(new Point(xEnd, bottomY), true, false);
                ctx.LineTo(new Point(xStart, bottomY), true, false);
            }

            // Zurück zum Startpunkt auf der Mittelachse
            ctx.LineTo(new Point(barList[0].X * PixelsPerSecond, mid), true, false);
        }

        geometry.Freeze();
        drawingContext.DrawGeometry(FillBrush, null, geometry);
    }
}
