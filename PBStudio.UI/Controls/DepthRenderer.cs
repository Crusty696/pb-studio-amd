using System.Collections.Generic;
using System.Collections.Specialized;
using System.Windows;
using System.Windows.Media;

namespace PBStudio.UI.Controls;

public class DepthRenderer : FrameworkElement
{
    private readonly VisualCollection _children;
    private readonly DrawingVisual _drawingVisual;

    public static readonly DependencyProperty PointsProperty =
        DependencyProperty.Register(nameof(Points), typeof(IEnumerable<Point>), typeof(DepthRenderer),
            new FrameworkPropertyMetadata(null, FrameworkPropertyMetadataOptions.AffectsRender, OnPointsChanged));

    public IEnumerable<Point> Points
    {
        get => (IEnumerable<Point>)GetValue(PointsProperty);
        set => SetValue(PointsProperty, value);
    }

    public static readonly DependencyProperty PixelsPerSecondProperty =
        DependencyProperty.Register(nameof(PixelsPerSecond), typeof(double), typeof(DepthRenderer),
            new FrameworkPropertyMetadata(100.0, FrameworkPropertyMetadataOptions.AffectsRender));

    public double PixelsPerSecond
    {
        get => (double)GetValue(PixelsPerSecondProperty);
        set => SetValue(PixelsPerSecondProperty, value);
    }

    public static readonly DependencyProperty LineBrushProperty =
        DependencyProperty.Register(nameof(LineBrush), typeof(Brush), typeof(DepthRenderer),
            new FrameworkPropertyMetadata(Brushes.Cyan));

    public Brush LineBrush
    {
        get => (Brush)GetValue(LineBrushProperty);
        set => SetValue(LineBrushProperty, value);
    }

    public DepthRenderer()
    {
        _children = new VisualCollection(this);
        _drawingVisual = new DrawingVisual();
        _children.Add(_drawingVisual);
    }

    private static void OnPointsChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is DepthRenderer renderer)
        {
            renderer.InvalidateVisual();
        }
    }

    protected override void OnRender(DrawingContext drawingContext)
    {
        base.OnRender(drawingContext);
        Render();
    }

    private void Render()
    {
        using (var dc = _drawingVisual.RenderOpen())
        {
            if (Points == null) return;

            var pen = new Pen(LineBrush, 1.0);
            pen.Freeze();

            StreamGeometry geometry = new StreamGeometry();
            using (StreamGeometryContext ctx = geometry.Open())
            {
                bool first = true;
                foreach (var p in Points)
                {
                    // X = Zeit * PPS, Y = Centroid (skaliert)
                    // Centroid ist oft im Bereich 0-8000 Hz, wir skalieren auf 0-50 Pixel
                    double x = p.X * PixelsPerSecond;
                    double y = 50 - (p.Y / 8000.0 * 50);

                    if (first)
                    {
                        ctx.BeginFigure(new Point(x, y), false, false);
                        first = false;
                    }
                    else
                    {
                        ctx.LineTo(new Point(x, y), true, false);
                    }
                }
            }
            geometry.Freeze();
            dc.DrawGeometry(null, pen, geometry);
        }
    }

    protected override int VisualChildrenCount => _children.Count;
    protected override Visual GetVisualChild(int index) => _children[index];
}
