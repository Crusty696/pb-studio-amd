using System;
using System.Globalization;
using System.Windows.Data;

namespace PBStudio.UI.Converters;

/// <summary>
/// Rechnet Zeit (Sekunden) in Pixel um, basierend auf dem aktuellen Zoom-Level (PixelsPerSecond).
/// Wird für MultiBinding in der Timeline genutzt.
/// </summary>
public class TimeToPixelConverter : IMultiValueConverter
{
    public object Convert(object[] values, Type targetType, object parameter, CultureInfo culture)
    {
        if (values.Length < 2) return 0.0;

        // Value 0: Zeit in Sekunden (double)
        // Value 1: Zoom Level in Pixel pro Sekunde (double)
        if (values[0] is double time && values[1] is double pps)
        {
            return time * pps;
        }

        if (values[0] is float fTime && values[1] is double fPps)
        {
            return (double)fTime * fPps;
        }

        return 0.0;
    }

    public object[] ConvertBack(object value, Type[] targetTypes, object parameter, CultureInfo culture)
    {
        // Wird für Drag & Drop benötigt (Pixel -> Sekunden)
        throw new NotImplementedException();
    }
}
