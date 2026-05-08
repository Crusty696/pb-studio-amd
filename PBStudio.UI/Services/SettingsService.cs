using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;

namespace PBStudio.UI.Services;

/// <summary>
/// Persistente Settings-Klasse (JSON-DTO).
/// Felder werden 1:1 nach %APPDATA%\PBStudio\settings.json serialisiert.
/// </summary>
public class PbSettings
{
    /// <summary>Vollständiger Pfad zur ffmpeg.exe. Leer = nicht gesetzt (Auto-Detect).</summary>
    public string FfmpegPath { get; set; } = "";

    /// <summary>VRAM-Cap (Slider). Default 8192 MB. Wird vom Backend-Arbiter genutzt.</summary>
    public int VramCapMb { get; set; } = 8192;

    /// <summary>
    /// Optional: erzwungener VRAM-Wert (PB_STUDIO_FORCED_VRAM env-var).
    /// null = Env-Var nicht setzen, Backend nutzt echtes VRAM.
    /// </summary>
    public int? ForcedVramMb { get; set; }
}

/// <summary>
/// Schnittstelle für Persistenz und Validierung von User-Settings.
/// </summary>
public interface ISettingsService
{
    PbSettings Current { get; }
    string ConfigFilePath { get; }

    void Load();
    void Save();

    /// <summary>Prüft ob der Pfad auf eine existierende ffmpeg.exe-Datei verweist.</summary>
    bool ValidateFFmpegPath(string? path, out string? errorMessage);

    /// <summary>Führt 'ffmpeg -version' aus und liefert die erste Zeile (z.B. "ffmpeg version 6.1.1 ...").</summary>
    Task<string?> ProbeFFmpegVersionAsync(string path, CancellationToken ct = default);
}

/// <summary>
/// Default-Implementierung. Speichert Settings in %APPDATA%\PBStudio\settings.json.
/// Verwendet pathlib-äquivalent System.IO.Path.Combine (R6).
/// </summary>
public class SettingsService : ISettingsService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    private PbSettings _current = new();
    public PbSettings Current => _current;

    public string ConfigFilePath { get; }

    public SettingsService(string? overridePath = null)
    {
        if (!string.IsNullOrWhiteSpace(overridePath))
        {
            ConfigFilePath = overridePath;
        }
        else
        {
            // %APPDATA%\PBStudio\settings.json - System.IO.Path.Combine ist hier korrekt (R6).
            var appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            var dir = Path.Combine(appData, "PBStudio");
            ConfigFilePath = Path.Combine(dir, "settings.json");
        }
    }

    /// <summary>
    /// Lädt die Settings vom Disk. Bei Fehler oder fehlender Datei: Defaults.
    /// Wirft NIE - Settings sind best-effort.
    /// </summary>
    public void Load()
    {
        try
        {
            if (!File.Exists(ConfigFilePath))
            {
                _current = new PbSettings();
                return;
            }
            var json = File.ReadAllText(ConfigFilePath, Encoding.UTF8);
            var loaded = JsonSerializer.Deserialize<PbSettings>(json, JsonOptions);
            _current = loaded ?? new PbSettings();
        }
        catch
        {
            _current = new PbSettings(); // Korrupte Datei -> Defaults
        }
    }

    /// <summary>
    /// Schreibt die aktuellen Settings als JSON. Erstellt Verzeichnis bei Bedarf.
    /// Wirft NIE - Fehler werden geschluckt (Settings sind best-effort).
    /// </summary>
    public void Save()
    {
        try
        {
            var dir = Path.GetDirectoryName(ConfigFilePath);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            var json = JsonSerializer.Serialize(_current, JsonOptions);
            File.WriteAllText(ConfigFilePath, json, new UTF8Encoding(false));
        }
        catch
        {
            // Best-effort: ignore disk errors, UI zeigt das via StatusText
        }
    }

    public bool ValidateFFmpegPath(string? path, out string? errorMessage)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            errorMessage = null; // leerer Pfad = Auto-Detect, kein Fehler
            return true;
        }

        // Pfad-Sicherheit: kein Crash bei ungültigen Zeichen
        try
        {
            var full = Path.GetFullPath(path);
            if (!File.Exists(full))
            {
                errorMessage = "Datei nicht gefunden.";
                return false;
            }
            // Sehr basale Plausibilitätsprüfung - Datei muss .exe oder ohne Endung sein
            var ext = Path.GetExtension(full);
            if (!string.IsNullOrEmpty(ext) &&
                !ext.Equals(".exe", StringComparison.OrdinalIgnoreCase))
            {
                errorMessage = "Datei ist keine .exe.";
                return false;
            }
            errorMessage = null;
            return true;
        }
        catch (Exception ex)
        {
            errorMessage = "Ungültiger Pfad: " + ex.Message;
            return false;
        }
    }

    public async Task<string?> ProbeFFmpegVersionAsync(string path, CancellationToken ct = default)
    {
        if (!ValidateFFmpegPath(path, out _))
            return null;

        try
        {
            using var proc = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = path,
                    Arguments = "-version",
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                }
            };
            if (!proc.Start())
                return null;

            // Hard timeout - ffmpeg -version sollte sub-sekünden zurückkommen
            var firstLineTask = proc.StandardOutput.ReadLineAsync(ct).AsTask();
            var completed = await Task.WhenAny(firstLineTask, Task.Delay(5000, ct))
                                      .ConfigureAwait(false);
            if (completed != firstLineTask)
            {
                try { proc.Kill(true); } catch { /* ignore */ }
                return null;
            }
            var line = await firstLineTask.ConfigureAwait(false);
            try
            {
                if (!proc.HasExited)
                    proc.WaitForExit(2000);
            }
            catch { /* ignore */ }

            if (string.IsNullOrWhiteSpace(line))
                return null;

            // Match "ffmpeg version 6.1.1-..."
            var match = Regex.Match(line, @"ffmpeg\s+version\s+(\S+)", RegexOptions.IgnoreCase);
            return match.Success ? match.Groups[1].Value : line.Trim();
        }
        catch
        {
            return null;
        }
    }
}
