using System.Globalization;
using System.Windows;
using System.Windows.Data;

namespace PBStudio.UI.Converters;

/// <summary>
/// null oder leerer/blanker String → Collapsed, sonst Visible.
///
/// Audit 2026-08-05: Der Converter prüfte ausschliesslich auf <c>null</c>. Bei
/// String-Properties, die im ViewModel mit <c>string.Empty</c> initialisiert
/// werden — die Regel im Projekt, weil <c>[ObservableProperty]</c> non-nullable
/// Strings bevorzugt — blieb das Element damit sichtbar und hinterliess eine
/// Leerzeile. Leerstring wird jetzt wie null behandelt.
/// </summary>
[ValueConversion(typeof(object), typeof(Visibility))]
public class NullToVisibilityConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        => value is null || (value is string text && string.IsNullOrWhiteSpace(text))
            ? Visibility.Collapsed
            : Visibility.Visible;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        => throw new NotImplementedException();
}

/// <summary>null → Visible, nicht-null → Collapsed (Platzhalter-Fallback)</summary>
[ValueConversion(typeof(object), typeof(Visibility))]
public class InverseNullToVisibilityConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object parameter, CultureInfo culture)
        => value == null ? Visibility.Visible : Visibility.Collapsed;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        => throw new NotImplementedException();
}

/// <summary>true → false, false → true (für IsEnabled-Bindings)</summary>
[ValueConversion(typeof(bool), typeof(bool))]
public class InverseBooleanConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
        => value is bool b ? !b : false;

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
        => value is bool b ? !b : false;
}
