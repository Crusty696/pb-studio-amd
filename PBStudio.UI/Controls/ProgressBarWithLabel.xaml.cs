using System.Windows;
using System.Windows.Controls;

namespace PBStudio.UI.Controls;

/// <summary>
/// Progress-Bar mit zentriertem Label (default: "{Percent:0.00} %").
/// Bindbar an feingranulare Werte (0.01-Schritte). Self-rendering Fill-Bar
/// (kein WPF-default ProgressBar wegen Z-Order Issues mit zentriertem Text).
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

    public static readonly DependencyProperty FillWidthProperty = DependencyProperty.Register(
        nameof(FillWidth), typeof(double), typeof(ProgressBarWithLabel),
        new FrameworkPropertyMetadata(0.0));

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

    public string? CustomLabel
    {
        get => (string?)GetValue(CustomLabelProperty);
        set => SetValue(CustomLabelProperty, value);
    }

    /// <summary>Berechnete Pixel-Breite der Fill-Bar (Bound von XAML).</summary>
    public double FillWidth
    {
        get => (double)GetValue(FillWidthProperty);
        private set => SetValue(FillWidthProperty, value);
    }

    public ProgressBarWithLabel()
    {
        InitializeComponent();
        UpdateLabel();
        SizeChanged += (_, _) => UpdateFillWidth();
    }

    private static void OnPercentChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        var c = (ProgressBarWithLabel)d;
        c.UpdateLabel();
        c.UpdateFillWidth();
    }

    private static void OnCustomLabelChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
        => ((ProgressBarWithLabel)d).UpdateLabel();

    private void UpdateLabel()
    {
        if (!string.IsNullOrEmpty(CustomLabel))
            LabelText = CustomLabel;
        else
            LabelText = $"{Percent:0.00} %";
    }

    private void UpdateFillWidth()
    {
        // Innenbreite = ActualWidth - 6 (3px Margin links/rechts vom Fill)
        var innerWidth = ActualWidth - 6;
        if (innerWidth <= 0) { FillWidth = 0; return; }
        var clamped = System.Math.Max(0, System.Math.Min(100, Percent));
        FillWidth = innerWidth * clamped / 100.0;
    }
}
