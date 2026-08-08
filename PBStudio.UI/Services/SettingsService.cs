using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
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

    /// <summary>
    /// KI-Modus fuer Auto-Selection von Vision-Modellen: "speed" | "balance" | "quality".
    /// Default "balance". Wird beim Captioning-Call und im /models/recommendations-Query
    /// mitgegeben. Persistiert in settings.json (snake_case: "ki_mode").
    /// </summary>
    public string KiMode { get; set; } = "balance";
}

public enum SettingsPersistenceFailure
{
    None,
    MalformedJson,
    ReadFailed,
    WriteFailed,
    VerificationFailed,
}

public sealed record SettingsLoadResult(
    bool Succeeded,
    bool LoadedFromDisk,
    SettingsPersistenceFailure Failure,
    string? ErrorMessage);

public sealed record SettingsSaveResult(
    bool Succeeded,
    SettingsPersistenceFailure Failure,
    string? ErrorMessage);

public sealed record FfmpegRuntimeProbeResult(
    bool Succeeded,
    string RuntimePath,
    string? Version,
    string? Sha256,
    string? FfprobeSha256,
    string? AssetSource,
    string? ErrorMessage);

/// <summary>
/// Schnittstelle für Persistenz und Validierung von User-Settings.
/// </summary>
public interface ISettingsService
{
    PbSettings Current { get; }
    string ConfigFilePath { get; }

    SettingsLoadResult Load();
    SettingsSaveResult Save();

    /// <summary>Prüft ob der Pfad auf eine existierende ffmpeg.exe-Datei verweist.</summary>
    bool ValidateFFmpegPath(string? path, out string? errorMessage);

    /// <summary>Führt 'ffmpeg -version' aus und liefert die erste Zeile (z.B. "ffmpeg version 6.1.1 ...").</summary>
    Task<string?> ProbeFFmpegVersionAsync(string path, CancellationToken ct = default);

    /// <summary>Prüft die tatsächlich verwendete Projekt-Runtime gegen ihre Manifest-Provenienz.</summary>
    Task<FfmpegRuntimeProbeResult> ProbeCanonicalFFmpegRuntimeAsync(CancellationToken ct = default);
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

    private readonly object _ioGate = new();
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
    /// Lädt Settings oder liefert einen typisierten, UI-sichtbaren Fehler.
    /// Eine fehlende Datei ist ein erfolgreicher Erststart mit Defaults.
    /// </summary>
    public SettingsLoadResult Load()
    {
        lock (_ioGate)
        {
            try
            {
                if (!File.Exists(ConfigFilePath))
                {
                    _current = new PbSettings();
                    return new SettingsLoadResult(
                        true,
                        false,
                        SettingsPersistenceFailure.None,
                        null);
                }

                var json = File.ReadAllText(ConfigFilePath, Encoding.UTF8);
                var loaded = JsonSerializer.Deserialize<PbSettings>(json, JsonOptions);
                if (loaded is null)
                {
                    _current = new PbSettings();
                    return new SettingsLoadResult(
                        false,
                        false,
                        SettingsPersistenceFailure.MalformedJson,
                        "Die Settings-Datei ist ungültig. Standardwerte wurden geladen.");
                }

                _current = loaded;
                return new SettingsLoadResult(
                    true,
                    true,
                    SettingsPersistenceFailure.None,
                    null);
            }
            catch (JsonException)
            {
                _current = new PbSettings();
                return new SettingsLoadResult(
                    false,
                    false,
                    SettingsPersistenceFailure.MalformedJson,
                    "Die Settings-Datei ist ungültig. Standardwerte wurden geladen.");
            }
            catch
            {
                _current = new PbSettings();
                return new SettingsLoadResult(
                    false,
                    false,
                    SettingsPersistenceFailure.ReadFailed,
                    "Die Settings-Datei konnte nicht gelesen werden. Standardwerte wurden geladen.");
            }
        }
    }

    /// <summary>
    /// Schreibt Settings in eine Datei im Zielverzeichnis, flush't sie auf Disk,
    /// veröffentlicht sie atomar und bestätigt anschließend die geschriebenen Bytes.
    /// </summary>
    public SettingsSaveResult Save()
    {
        lock (_ioGate)
        {
            string? temporaryPath = null;
            try
            {
                var targetPath = Path.GetFullPath(ConfigFilePath);
                var directory = Path.GetDirectoryName(targetPath)
                    ?? throw new IOException("Settings-Zielverzeichnis fehlt.");
                Directory.CreateDirectory(directory);

                var payload = JsonSerializer.SerializeToUtf8Bytes(_current, JsonOptions);
                temporaryPath = Path.Combine(
                    directory,
                    $".{Path.GetFileName(targetPath)}.{Guid.NewGuid():N}.tmp");

                using (var stream = new FileStream(
                    temporaryPath,
                    FileMode.CreateNew,
                    FileAccess.Write,
                    FileShare.None,
                    bufferSize: 4096,
                    FileOptions.WriteThrough))
                {
                    stream.Write(payload);
                    stream.Flush(flushToDisk: true);
                }

                if (File.Exists(targetPath))
                    File.Replace(temporaryPath, targetPath, null, ignoreMetadataErrors: true);
                else
                    File.Move(temporaryPath, targetPath);
                temporaryPath = null;

                var persisted = File.ReadAllBytes(targetPath);
                if (!persisted.AsSpan().SequenceEqual(payload))
                {
                    return new SettingsSaveResult(
                        false,
                        SettingsPersistenceFailure.VerificationFailed,
                        "Die gespeicherten Settings konnten nicht bestätigt werden.");
                }

                return new SettingsSaveResult(
                    true,
                    SettingsPersistenceFailure.None,
                    null);
            }
            catch
            {
                return new SettingsSaveResult(
                    false,
                    SettingsPersistenceFailure.WriteFailed,
                    "Die Settings-Datei konnte nicht atomar geschrieben werden.");
            }
            finally
            {
                if (temporaryPath is not null)
                {
                    try { File.Delete(temporaryPath); }
                    catch { /* Der Save-Fehler bleibt das primäre sichtbare Ergebnis. */ }
                }
            }
        }
    }

    public bool ValidateFFmpegPath(string? path, out string? errorMessage)
    {
        try
        {
            var canonical = PythonBridgeService.GetCanonicalFfmpegPath();
            if (string.IsNullOrWhiteSpace(path))
            {
                errorMessage = "Der kanonische Projektpfad ist erforderlich.";
                return false;
            }
            var full = Path.GetFullPath(path);
            if (!full.Equals(canonical, StringComparison.OrdinalIgnoreCase))
            {
                errorMessage = "Nur die geprüfte Projekt-Runtime ist zulässig.";
                return false;
            }
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

    public async Task<FfmpegRuntimeProbeResult> ProbeCanonicalFFmpegRuntimeAsync(
        CancellationToken ct = default)
    {
        string canonicalPath;
        try
        {
            canonicalPath = PythonBridgeService.GetCanonicalFfmpegPath();
        }
        catch
        {
            return new FfmpegRuntimeProbeResult(
                false,
                "",
                null,
                null,
                null,
                null,
                "Die kanonische FFmpeg-Projekt-Runtime fehlt.");
        }

        string preProbeHash;
        try
        {
            preProbeHash = await ComputeSha256Async(canonicalPath, ct).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch
        {
            return new FfmpegRuntimeProbeResult(
                false,
                canonicalPath,
                null,
                null,
                null,
                null,
                "Die kanonische FFmpeg-Runtime konnte nicht gelesen werden.");
        }

        var version = await ProbeFFmpegVersionAsync(canonicalPath, ct).ConfigureAwait(false);
        if (string.IsNullOrWhiteSpace(version))
        {
            return new FfmpegRuntimeProbeResult(
                false,
                canonicalPath,
                null,
                null,
                null,
                null,
                "Die kanonische FFmpeg-Runtime konnte nicht ausgeführt werden.");
        }

        try
        {
            var runtimeHash = await ComputeSha256Async(canonicalPath, ct).ConfigureAwait(false);
            var stableBin = Path.GetDirectoryName(canonicalPath)
                ?? throw new DirectoryNotFoundException();
            var ffprobePath = Path.Combine(stableBin, "ffprobe.exe");
            var ffprobeHash = await ComputeSha256Async(ffprobePath, ct).ConfigureAwait(false);
            var projectRoot = Directory.GetParent(stableBin)?.Parent?.Parent?.FullName
                ?? throw new DirectoryNotFoundException();
            var manifestPath = Path.Combine(projectRoot, "config", "ffmpeg-runtime.json");
            using var manifest = JsonDocument.Parse(
                await File.ReadAllBytesAsync(manifestPath, ct).ConfigureAwait(false));

            var root = manifest.RootElement;
            var declaredStableBin = root.GetProperty("stable_bin").GetString()
                ?? throw new JsonException();
            var expectedStableBin = Path.GetFullPath(
                Path.Combine(projectRoot, declaredStableBin.Replace('/', Path.DirectorySeparatorChar)));
            var active = root.GetProperty("active");
            var declaredVersion = active.GetProperty("version").GetString()
                ?? throw new JsonException();
            var declaredHash = active.GetProperty("ffmpeg_sha256").GetString()
                ?? throw new JsonException();
            var declaredFfprobeHash = active.GetProperty("ffprobe_sha256").GetString()
                ?? throw new JsonException();
            var assetSource = active.GetProperty("asset_url").GetString()
                ?? throw new JsonException();

            var verified =
                stableBin.Equals(expectedStableBin, StringComparison.OrdinalIgnoreCase) &&
                version.Equals(declaredVersion, StringComparison.OrdinalIgnoreCase) &&
                runtimeHash.Equals(preProbeHash, StringComparison.OrdinalIgnoreCase) &&
                runtimeHash.Equals(declaredHash, StringComparison.OrdinalIgnoreCase) &&
                ffprobeHash.Equals(declaredFfprobeHash, StringComparison.OrdinalIgnoreCase);
            return new FfmpegRuntimeProbeResult(
                verified,
                canonicalPath,
                version,
                runtimeHash,
                ffprobeHash,
                assetSource,
                verified
                    ? null
                    : "FFmpeg-Runtime und aktive Manifest-Provenienz stimmen nicht überein.");
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch
        {
            return new FfmpegRuntimeProbeResult(
                false,
                canonicalPath,
                version,
                null,
                null,
                null,
                "Die FFmpeg-Manifest-Provenienz konnte nicht bestätigt werden.");
        }
    }

    private static async Task<string> ComputeSha256Async(
        string path,
        CancellationToken ct)
    {
        await using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            bufferSize: 1024 * 1024,
            FileOptions.Asynchronous | FileOptions.SequentialScan);
        using var sha256 = SHA256.Create();
        var hash = await sha256.ComputeHashAsync(stream, ct).ConfigureAwait(false);
        return Convert.ToHexString(hash);
    }
}
