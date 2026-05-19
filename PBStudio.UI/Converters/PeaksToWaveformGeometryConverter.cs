using System;
using System.Collections.Generic;
using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;

namespace PBStudio.UI.Converters;

/// <summary>
/// Converts (peaks: IList&lt;float&gt;, width: double, height: double) to StreamGeometry,
/// drawing a symmetric mid-axis waveform (positive and mirrored negative).
/// </summary>
public class PeaksToWaveformGeometryConverter : IMultiValueConverter
{
    public object Convert(object[] values, Type targetType, object parameter, CultureInfo culture)
    {
        if (values.Length < 3) return Geometry.Empty;
        if (values[0] is not IList<float> peaks || peaks.Count == 0) return Geometry.Empty;
        if (values[1] is not double width || width <= 0) return Geometry.Empty;
        if (values[2] is not double height || height <= 0) return Geometry.Empty;

        var geo = new StreamGeometry();
        using (var ctx = geo.Open())
        {
            double mid = height / 2.0;
            double step = width / peaks.Count;
            for (int i = 0; i < peaks.Count; i++)
            {
                double x = i * step;
                double h = Math.Max(1.0, peaks[i] * mid);
                ctx.BeginFigure(new Point(x, mid - h), false, false);
                ctx.LineTo(new Point(x, mid + h), true, false);
            }
        }
        geo.Freeze();
        return geo;
    }

    public object[] ConvertBack(object value, Type[] targetTypes, object parameter, CultureInfo culture)
        => throw new NotImplementedException();
}
