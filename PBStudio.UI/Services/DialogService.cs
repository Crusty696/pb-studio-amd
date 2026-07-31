using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using Microsoft.Win32;

namespace PBStudio.UI.Services;

/// <summary>
/// Implementierung des IDialogService unter Verwendung von Microsoft.Win32 (Native WPF).
/// Nutzt OpenFolderDialog (.NET 9+).
/// </summary>
public class DialogService : IDialogService
{
    public string? OpenFile(string title, string filter, string? initialDirectory = null)
    {
        var dialog = new OpenFileDialog
        {
            Title = title,
            Filter = filter,
            InitialDirectory = initialDirectory,
            Multiselect = false
        };

        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }

    public List<string> OpenFiles(string title, string filter, string? initialDirectory = null)
    {
        var dialog = new OpenFileDialog
        {
            Title = title,
            Filter = filter,
            InitialDirectory = initialDirectory,
            Multiselect = true
        };

        return dialog.ShowDialog() == true ? dialog.FileNames.ToList() : new List<string>();
    }

    public string? OpenFolder(string title, string? initialDirectory = null)
    {
        var dialog = new OpenFolderDialog
        {
            Title = title,
            InitialDirectory = initialDirectory,
            Multiselect = false
        };

        return dialog.ShowDialog() == true ? dialog.FolderName : null;
    }

    public string? SaveFile(string title, string filter, string defaultFileName, string? initialDirectory = null)
    {
        var dialog = new SaveFileDialog
        {
            Title = title,
            Filter = filter,
            FileName = defaultFileName,
            InitialDirectory = initialDirectory
        };

        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }

    public bool ConfirmDestructiveAction(string title, string message)
    {
        var result = MessageBox.Show(
            message,
            title,
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning,
            MessageBoxResult.No);
        return result == MessageBoxResult.Yes;
    }
}
