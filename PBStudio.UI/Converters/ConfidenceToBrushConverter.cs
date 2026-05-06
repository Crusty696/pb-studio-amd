using System;
using System.Globalization;
using System.Windows.Data;
using System.Windows.Media;

namespace PBStudio.UI.Converters;

/// <summary>
/// Plan Phase 5: maps Brain-Confidence 0..1 to red→yellow→green linear gradient.
/// 0.0 = pure red (#D04040), 0.5 = yellow (#D0B040), 1.0 = green (#40C060).
/// </summary>
public class ConfidenceToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        double v = 0.0;
        if (value is double d) v = d;
        else if (value is float f) v = f;
        else if (value != null) double.TryParse(value.ToString(), NumberStyles.Float, CultureInfo.InvariantCulture, out v);

        v = Math.Max(0.0, Math.Min(1.0, v));

        byte r, g, b;
        if (v < 0.5)
        {
            double t = v * 2.0;  // 0..1 in lower half
            r = 0xD0;
            g = (byte)(0x40 + (0xB0 - 0x40) * t);
            b = 0x40;
        }
        else
        {
            double t = (v - 0.5) * 2.0;  // 0..1 in upper half
            r = (byte)(0xD0 - (0xD0 - 0x40) * t);
            g = (byte)(0xB0 + (0xC0 - 0xB0) * t);
            b = (byte)(0x40 + (0x60 - 0x40) * t);
        }

        return new SolidColorBrush(Color.FromRgb(r, g, b));
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        => throw new NotSupportedException();
}
