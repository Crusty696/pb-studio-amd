using System.Windows;
using System.Windows.Controls;

namespace PBStudio.UI.Controls;

/// <summary>
/// Progress-Bar mit zentriertem Label (default: "{Percent:0.00} %").
/// Bindbar an feingranulare Werte (0.01-Schritte).
/// </summary>
public partial class ProgressBarWithLabel : UserControl
{
    public static readonly DependencyProperty PercentProperty = DependencyProperty.Register(
        nameof(Percent), typeof(double), typeof(ProgressBarWithLabel),
        new FrameworkPropertyMetadata(0.0, FrameworkPropertyMetadataOptions.BindsTwoWayByDefault, OnPercentChanged));

    public static readonly DependencyProperty IsIndeterminateProperty = DependencyProperty.Register(
        nameof(IsIndeterminate), typeof(bool), typeof(ProgressBarWithLabel),
        new FrameworkPropertyMetadata(false));

    public static readonly DependencyProperty LabelTextProperty = DependencyProperty.Register(
        nameof(LabelText), typeof(string), typeof(ProgressBarWithLabel),
        new FrameworkPropertyMetadata("0.00 %"));

    public static readonly DependencyProperty CustomLabelProperty = DependencyProperty.Register(
        nameof(CustomLabel), typeof(string), typeof(ProgressBarWithLabel),
        new FrameworkPropertyMetadata(null, OnCustomLabelChanged));

    public double Percent
    {
        get => (double)GetValue(PercentProperty);
        set => SetValue(PercentProperty, value);
    }

    public bool IsIndeterminate
    {
        get => (bool)GetValue(IsIndeterminateProperty);
        set => SetValue(IsIndeterminateProperty, value);
    }

    public string LabelText
    {
        get => (string)GetValue(LabelTextProperty);
        private set => SetValue(LabelTextProperty, value);
    }

    /// <summary>Optionaler Custom-Label-Override. Wenn gesetzt, ueberschreibt %-Anzeige.</summary>
    public string? CustomLabel
    {
        get => (string?)GetValue(CustomLabelProperty);
        set => SetValue(CustomLabelProperty, value);
    }

    public ProgressBarWithLabel()
    {
        InitializeComponent();
        UpdateLabel();
    }

    private static void OnPercentChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
        => ((ProgressBarWithLabel)d).UpdateLabel();

    private static void OnCustomLabelChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
        => ((ProgressBarWithLabel)d).UpdateLabel();

    private void UpdateLabel()
    {
        if (!string.IsNullOrEmpty(CustomLabel))
        {
            LabelText = CustomLabel;
        }
        else
        {
            // 2 Nachkommastellen fuer 0.01-Aufloesung
            LabelText = $"{Percent:0.00} %";
        }
    }
}
