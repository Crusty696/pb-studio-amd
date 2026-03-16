using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace PBStudio.UI.Services;

public static class PromptDialog
{
    public static string? Show(string title, string prompt, string defaultValue = "")
    {
        var input = new TextBox
        {
            Text = defaultValue,
            Margin = new Thickness(0, 8, 0, 0),
            MinWidth = 320,
            Padding = new Thickness(6, 4, 6, 4),
        };

        var panel = new StackPanel();
        panel.Children.Add(new TextBlock
        {
            Text = prompt,
            Foreground = Brushes.White,
        });
        panel.Children.Add(input);

        var dialog = new Window
        {
            Title = title,
            Content = panel,
            Width = 380,
            Height = 150,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            ResizeMode = ResizeMode.NoResize,
            Background = new SolidColorBrush(Color.FromRgb(0x2A, 0x2A, 0x2A)),
            Foreground = Brushes.White,
            Owner = Application.Current?.MainWindow,
        };

        var ok = false;
        var buttons = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(0, 12, 0, 0),
        };

        var okButton = new Button { Content = "OK", MinWidth = 72, Margin = new Thickness(0, 0, 8, 0) };
        okButton.Click += (_, _) => { ok = true; dialog.Close(); };
        var cancelButton = new Button { Content = "Abbrechen", MinWidth = 72 };
        cancelButton.Click += (_, _) => dialog.Close();
        buttons.Children.Add(okButton);
        buttons.Children.Add(cancelButton);
        panel.Children.Add(buttons);

        dialog.Loaded += (_, _) => input.Focus();
        dialog.ShowDialog();
        return ok ? input.Text : null;
    }
}
