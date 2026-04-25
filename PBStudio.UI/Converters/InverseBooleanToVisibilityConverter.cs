using System;
using System.Globalization;
using System.Windows;
using System.Windows.Data;

namespace PBStudio.UI.Converters;

/// <summary>
/// Invertiert einen Boolean-Wert und konvertiert ihn in Visibility (false -> Visible, true -> Collapsed).
/// </summary>
public class InverseBooleanToVisibilityConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        if (value is bool b)
        {
            return b ? Visibility.Collapsed : Visibility.Visible;
        }
        return Visibility.Visible;
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
    {
        if (value is Visibility v)
        {
            return v != Visibility.Visible;
        }
        return false;
    }
}
