using System.Globalization;
using System.Windows.Data;

namespace PBStudio.UI.Converters;

/// <summary>
/// Mappt einen Motion-Wert (typ. 0..50 RAFT-Flow-Magnitude) auf eine Sparkline-Bar-Hoehe
/// in Pixeln (0..20). Wird in der TimelineView fuer die Motion-Curve-Visualisierung
/// (Audit L-M5) verwendet. Skaliert linear, klemmt auf min=1 (immer sichtbar) und max=20.
/// </summary>
[ValueConversion(typeof(double), typeof(double))]
public class MotionToHeightConverter : IValueConverter
{
    private const double MaxMotion = 50.0;
    private const double MaxHeight = 20.0;
    private const double MinHeight = 1.0;

    public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
    {
        double d = value switch
        {
            double dv => dv,
            float fv => fv,
            int iv => iv,
            _ => 0.0,
        };

        var scaled = d / MaxMotion * MaxHeight;
        if (scaled < MinHeight) return MinHeight;
        if (scaled > MaxHeight) return MaxHeight;
        return scaled;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        => throw new NotImplementedException();
}
