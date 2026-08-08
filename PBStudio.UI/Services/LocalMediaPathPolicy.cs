using System;
using System.IO;

namespace PBStudio.UI.Services;

/// <summary>Defense-in-depth guard for paths consumed by WPF MediaElement.</summary>
internal static class LocalMediaPathPolicy
{
    public static bool TryCreateFileUri(string? value, out Uri? uri) =>
        TryCreateFileUri(value, allowedRoot: null, out uri);

    public static bool TryCreateFileUri(
        string? value,
        string? allowedRoot,
        out Uri? uri)
    {
        uri = null;
        if (string.IsNullOrWhiteSpace(value)
            || value.StartsWith(@"\\", StringComparison.Ordinal)
            || value.StartsWith(@"//", StringComparison.Ordinal))
        {
            return false;
        }

        if (!Uri.TryCreate(value, UriKind.Absolute, out var parsed)
            || !parsed.IsFile
            || parsed.IsUnc)
        {
            return false;
        }

        string fullPath;
        try
        {
            fullPath = Path.GetFullPath(parsed.LocalPath);
        }
        catch (Exception ex) when (
            ex is ArgumentException
            or NotSupportedException
            or PathTooLongException)
        {
            return false;
        }

        if (fullPath.StartsWith(@"\\", StringComparison.Ordinal)
            || fullPath.StartsWith(@"\\?\", StringComparison.Ordinal)
            || fullPath.StartsWith(@"\\.\", StringComparison.Ordinal))
        {
            return false;
        }

        try
        {
            var root = Path.GetPathRoot(fullPath);
            if (string.IsNullOrWhiteSpace(root)
                || new DriveInfo(root).DriveType == DriveType.Network)
            {
                return false;
            }

            var current = root;
            var relative = Path.GetRelativePath(root, fullPath);
            foreach (var component in relative.Split(
                         new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
                         StringSplitOptions.RemoveEmptyEntries))
            {
                current = Path.Combine(current, component);
                if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                {
                    return false;
                }
            }
        }
        catch (Exception ex) when (
            ex is IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException)
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(allowedRoot))
        {
            string root;
            try
            {
                root = Path.GetFullPath(allowedRoot)
                    .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            }
            catch (Exception ex) when (
                ex is ArgumentException
                or NotSupportedException
                or PathTooLongException)
            {
                return false;
            }

            var prefix = root + Path.DirectorySeparatorChar;
            if (!fullPath.Equals(root, StringComparison.OrdinalIgnoreCase)
                && !fullPath.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }
        }

        if (!File.Exists(fullPath))
        {
            return false;
        }

        uri = new Uri(fullPath, UriKind.Absolute);
        return true;
    }
}
