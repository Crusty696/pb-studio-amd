using System.Globalization;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;

namespace PBStudio.UI.Converters;

/// <summary>
/// Audit-Fix 2026-07-10 (Sweep-Finding HIGH-12): TimelineViewModel.StatusText
/// wurde gesetzt (u.a. "Timeline laden fehlgeschlagen"), war aber an KEIN
/// XAML-Element gebunden — Refresh-Fehler blieben fuer den User unsichtbar,
/// die Timeline zeigte einfach lautlos veraltete/leere Daten weiter an.
/// Faerbt den Status-Text rot bei erkannten Fehlermeldungen, sonst gedimmt.
/// </summary>
[ValueConversion(typeof(string), typeof(Brush))]
public class StatusTextToBrushConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
    {
        var text = value as string ?? "";
        if (text.Contains("fehlgeschlagen", StringComparison.OrdinalIgnoreCase)
            || text.Contains("fehler", StringComparison.OrdinalIgnoreCase))
        {
            return Brushes.OrangeRed;
        }
        return Application.Current.TryFindResource("AbletonTextDim") as Brush ?? Brushes.Gray;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        => throw new NotImplementedException();
}
