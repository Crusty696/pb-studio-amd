using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading;
using CommunityToolkit.Mvvm.Messaging;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Services.Messages;

namespace PBStudio.UI.Services;

/// <summary>
/// Verwaltet den Python FastAPI Backend-Prozess.
/// Startet, überwacht und stoppt den Python-Server.
/// </summary>
public class PythonBridgeService : IDisposable
{
    private readonly ILogger<PythonBridgeService> _logger;
    private readonly HttpClient _bootstrapHttpClient;
    private readonly HttpClient _protectedHttpClient;
    private Process? _pythonProcess;
    private bool _isRunning;
    private volatile bool _isStopping;
    private volatile bool _ownsProcess;
    private readonly SemaphoreSlim _lifecycleGate = new(1, 1);
    private bool _disposed;

    private static readonly string? PythonExe = ResolvePythonExe();
    private static readonly bool PreferExternalBackend = IsEnabled(Environment.GetEnvironmentVariable("PBSTUDIO_BACKEND_MANAGED_EXTERNALLY"));
    private const int Port = 8765;
    private const int StartupTimeoutMs = 30_000;
    private const int HealthCheckIntervalMs = 500;

    public static void ApplyRuntimeEnvironment(PbSettings settings)
    {
        ArgumentNullException.ThrowIfNull(settings);
        BackendOwnerCapability.Ensure();
        SetForcedVramEnvVar(settings.ForcedVramMb);
        SetVramLimitEnvVar(settings.VramCapMb);
        var (ffmpegPath, ffprobePath) = ResolveCanonicalFfmpegPair();
        settings.FfmpegPath = ffmpegPath;
        SetFfmpegPathEnvVar(ffmpegPath);
        SetFfprobePathEnvVar(ffprobePath);
    }

    /// <summary>
    /// Setzt die PB_STUDIO_FORCED_VRAM Env-Var auf Process-Ebene. Diese wird vom
    /// Python-Backend beim NÄCHSTEN Start gelesen (vererbt sich auf den Child-Prozess).
    /// mb=null entfernt die Variable.
    /// </summary>
    public static void SetForcedVramEnvVar(int? mb)
    {
        const string key = "PB_STUDIO_FORCED_VRAM";
        if (mb.HasValue && mb.Value > 0)
            Environment.SetEnvironmentVariable(key, mb.Value.ToString(), EnvironmentVariableTarget.Process);
        else
            Environment.SetEnvironmentVariable(key, null, EnvironmentVariableTarget.Process);
    }

    /// <summary>
    /// Setzt die PBSTUDIO_FFMPEG_PATH Env-Var auf Process-Ebene. Backend liest sie
    /// via pydantic-settings (env_prefix=PBSTUDIO_) automatisch in
    /// <c>ServerConfig.ffmpeg_path</c> beim Backend-Start. Leerer/null Pfad entfernt
    /// die Variable, sodass der Default aus config.py gilt.
    /// </summary>
    public static void SetFfmpegPathEnvVar(string? path)
    {
        const string key = "PBSTUDIO_FFMPEG_PATH";
        if (!string.IsNullOrWhiteSpace(path))
            Environment.SetEnvironmentVariable(key, path, EnvironmentVariableTarget.Process);
        else
            Environment.SetEnvironmentVariable(key, null, EnvironmentVariableTarget.Process);
    }

    /// <summary>
    /// Setzt die PBSTUDIO_VRAM_LIMIT_MB Env-Var auf Process-Ebene.
    /// Wird vom BudgetManager und Arbiter im Backend eingelesen.
    /// </summary>
    public static void SetVramLimitEnvVar(int? mb)
    {
        const string key = "PBSTUDIO_VRAM_LIMIT_MB";
        if (mb.HasValue && mb.Value > 0)
            Environment.SetEnvironmentVariable(key, mb.Value.ToString(), EnvironmentVariableTarget.Process);
        else
            Environment.SetEnvironmentVariable(key, null, EnvironmentVariableTarget.Process);
    }

    public bool IsRunning => _isRunning;
    public event EventHandler<bool>? StatusChanged;

    public PythonBridgeService(ILogger<PythonBridgeService> logger)
        : this(logger, CreateBootstrapHttpClient(), CreateProtectedHttpClient())
    {
    }

    internal PythonBridgeService(
        ILogger<PythonBridgeService> logger,
        HttpClient bootstrapHttpClient)
        : this(logger, bootstrapHttpClient, CreateProtectedHttpClient())
    {
    }

    internal PythonBridgeService(
        ILogger<PythonBridgeService> logger,
        HttpClient bootstrapHttpClient,
        HttpClient protectedHttpClient)
    {
        _logger = logger;
        _bootstrapHttpClient = bootstrapHttpClient;
        _protectedHttpClient = protectedHttpClient;
        _bootstrapHttpClient.BaseAddress ??= new Uri($"http://127.0.0.1:{Port}");
        _protectedHttpClient.BaseAddress ??= new Uri($"http://127.0.0.1:{Port}");
        _bootstrapHttpClient.Timeout = TimeSpan.FromMinutes(20);
        _protectedHttpClient.Timeout = TimeSpan.FromMinutes(20);
    }

    private static HttpClient CreateBootstrapHttpClient() => new(
        new HttpClientHandler
        {
            AllowAutoRedirect = false,
        });

    private static HttpClient CreateProtectedHttpClient() => new(
        new OwnerCapabilityRequestHandler
        {
            InnerHandler = new HttpClientHandler
            {
                AllowAutoRedirect = false,
            },
        });

    public async Task StartAsync()
    {
        if (_isStopping) return;

        await _lifecycleGate.WaitAsync().ConfigureAwait(false);
        try
        {
            if (_isStopping) return;
            _isStopping = false;

            if (_isRunning) return;

            using (var revalidation = await BackendOwnerCapability
                .BeginRevalidationAsync()
                .ConfigureAwait(false))
            {
                if (await IsBackendAlreadyHealthyAsync().ConfigureAwait(false))
                {
                    if (!BackendOwnerCapability.WasProvisioned)
                    {
                        _logger.LogError(
                            "Port {Port} belegt, aber keine externe Owner-Capability wurde bereitgestellt; fremdes Backend wird nicht übernommen",
                            Port);
                        return;
                    }

                    if (await VerifyBackendOwnershipAsync().ConfigureAwait(false))
                    {
                        revalidation.CompleteVerification();
                        AttachToExistingBackend("Externes Python Backend mit gültigem Owner-Proof auf Port {Port} verbunden");
                        return;
                    }

                    _logger.LogError(
                        "Port {Port} belegt, aber Health-Proof stimmt nicht mit Owner-Capability überein; fremdes Backend wird nicht übernommen",
                        Port);
                    return;
                }
            }

            if (PreferExternalBackend)
            {
                _logger.LogWarning("Extern verwaltetes Backend erwartet, aber Port {Port} ist nicht gesund - es wird kein zweiter Backend-Prozess gestartet", Port);
                return;
            }

            var pythonExe = PythonExe;
            if (string.IsNullOrWhiteSpace(pythonExe) || !IsPython311(pythonExe))
            {
                _logger.LogError(
                    "Python 3.11 wurde nicht gefunden oder der konfigurierte Interpreter ist inkompatibel. " +
                    "PBSTUDIO_PYTHON_EXE muss auf Python 3.11.x zeigen.");
                return;
            }

            var backendDir = FindBackendDirectory();
            if (backendDir == null)
            {
                _logger.LogError("Backend-Verzeichnis nicht gefunden!");
                return;
            }

            var projectRoot = Path.GetDirectoryName(backendDir)!;
            _logger.LogInformation("Starte Python Backend: {Dir}", backendDir);

            var startInfo = new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = $"-m uvicorn backend.main:app --host 127.0.0.1 --port {Port}",
                WorkingDirectory = projectRoot,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            startInfo.Environment["PYTHONPATH"] = Path.Combine(projectRoot, "src");
            var (ffmpegPath, ffprobePath) = ResolveCanonicalFfmpegPair();
            startInfo.Environment["PBSTUDIO_FFMPEG_PATH"] = ffmpegPath;
            startInfo.Environment["PBSTUDIO_FFPROBE_PATH"] = ffprobePath;
            var (lhmManifestHash, lhmLibraryHash) =
                ResolveCanonicalLhmHashes(projectRoot);
            startInfo.Environment["PBSTUDIO_LHM_MANIFEST_SHA256"] =
                lhmManifestHash;
            startInfo.Environment["PBSTUDIO_LHM_SHA256"] = lhmLibraryHash;
            startInfo.Environment[BackendOwnerCapability.EnvironmentVariable] =
                BackendOwnerCapability.Ensure();

            try
            {
                _pythonProcess = Process.Start(startInfo);
                _ownsProcess = _pythonProcess != null;
                if (_pythonProcess == null)
                {
                    _logger.LogError("Python-Prozess konnte nicht gestartet werden");
                    return;
                }

                // AP3.1 (Audit 2026-06-10): Kill-on-Close JobObject — beendet den
                // gesamten uvicorn-Prozessbaum garantiert mit, auch wenn die WPF-App
                // hart crasht (vorher: Zombie-Backend blockierte Port 8765).
                AssignToKillOnCloseJob(_pythonProcess, _logger);

                _pythonProcess.OutputDataReceived += (_, e) =>
                {
                    if (e.Data != null) _logger.LogDebug("[Python] {Line}", e.Data);
                };
                _pythonProcess.ErrorDataReceived += (_, e) =>
                {
                    if (e.Data != null) _logger.LogDebug("[Python] {Line}", e.Data);
                };
                _pythonProcess.BeginOutputReadLine();
                _pythonProcess.BeginErrorReadLine();

                var backendOwned = await WaitForHealthAsync().ConfigureAwait(false);
                if (backendOwned)
                {
                    _isRunning = true;
                    StatusChanged?.Invoke(this, true);
                    // AP3.2 (Audit 2026-06-10): BackendReadyMessage wurde nirgends
                    // gesendet — SettingsViewModel & Co. registrierten darauf und
                    // blieben dauerhaft auf "Backend: Offline".
                    WeakReferenceMessenger.Default.Send(new BackendReadyMessage());
                    _logger.LogInformation("Python Backend gestartet (Startprozess-PID={Pid})", _pythonProcess.Id);
                    StartWatchdog();
                    return;
                }

                _isRunning = false;
                _ownsProcess = false;
                StatusChanged?.Invoke(this, false);
                _logger.LogError("Python Backend Health- oder Owner-Proof-Check fehlgeschlagen");

                try
                {
                    if (!_pythonProcess.HasExited)
                    {
                        _pythonProcess.Kill(entireProcessTree: true);
                        await _pythonProcess.WaitForExitAsync().ConfigureAwait(false);
                    }
                }
                catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
                {
                    _logger.LogDebug(ex, "Python-Prozess war nach fehlgeschlagenem Start bereits beendet");
                }

                _pythonProcess = null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Fehler beim Starten des Python Backends");
            }
        }
        finally
        {
            _lifecycleGate.Release();
        }
    }

    public async Task StopAsync()
    {
        await _lifecycleGate.WaitAsync().ConfigureAwait(false);
        try
        {
            _isStopping = true;

            if (!_isRunning)
                return;

            _logger.LogInformation("Stoppe Python Backend...");

            if (_ownsProcess)
            {
                try
                {
                    await RequestOwnedShutdownAsync().ConfigureAwait(false);
                    await Task.Delay(3000).ConfigureAwait(false);
                }
                catch { }

                if (_pythonProcess != null)
                {
                    try
                    {
                        if (!_pythonProcess.HasExited)
                        {
                            _pythonProcess.Kill(entireProcessTree: true);
                            await _pythonProcess.WaitForExitAsync().ConfigureAwait(false);
                        }
                    }
                    catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
                    {
                        _logger.LogDebug(ex, "Python-Prozess war beim Shutdown bereits beendet");
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, "Fehler beim Stoppen des Python-Prozesses");
                    }
                }
            }

            _pythonProcess = null;
            _ownsProcess = false;
            _isRunning = false;
            StatusChanged?.Invoke(this, false);
            _logger.LogInformation("Python Backend gestoppt");
        }
        finally
        {
            _lifecycleGate.Release();
        }
    }

    private async Task RequestOwnedShutdownAsync()
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/shutdown");
        using var response = await _protectedHttpClient
            .SendAsync(request)
            .ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
    }

    private void StartWatchdog()
    {
        _ = Task.Run(async () =>
        {
            while (_isRunning)
            {
                await Task.Delay(10_000).ConfigureAwait(false);
                if (await IsBackendOwnedHealthyAsync().ConfigureAwait(false))
                {
                    continue;
                }

                _isRunning = false;
                StatusChanged?.Invoke(this, false);

                if (_isStopping || !_ownsProcess)
                    break;

                _logger.LogWarning("Python Backend Health- oder Owner-Proof verlorengegangen – starte owned Prozess neu...");
                var process = _pythonProcess;
                _pythonProcess = null;
                if (process is not null)
                {
                    try
                    {
                        if (!process.HasExited)
                        {
                            process.Kill(entireProcessTree: true);
                            await process.WaitForExitAsync().ConfigureAwait(false);
                        }
                    }
                    catch (Exception ex) when (ex is InvalidOperationException or System.ComponentModel.Win32Exception)
                    {
                        _logger.LogDebug(ex, "Owned Python-Prozess war vor Watchdog-Restart bereits beendet");
                    }
                }
                await StartAsync().ConfigureAwait(false);
                break;
            }
        });
    }

    private void AttachToExistingBackend(string logMessage)
    {
        _pythonProcess = null;
        _isRunning = true;
        _ownsProcess = false;
        _logger.LogInformation(logMessage, Port);
        StatusChanged?.Invoke(this, true);
        // AP3.2: auch im Attach-Modus ist das Backend ab hier nutzbar
        WeakReferenceMessenger.Default.Send(new BackendReadyMessage());
        StartWatchdog();
    }

    private async Task<bool> IsBackendAlreadyHealthyAsync()
    {
        try
        {
            using var response = await _bootstrapHttpClient
                .GetAsync("/health")
                .ConfigureAwait(false);
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    private async Task<bool> WaitForHealthAsync()
    {
        var deadline = DateTime.UtcNow.AddMilliseconds(StartupTimeoutMs);

        while (DateTime.UtcNow < deadline)
        {
            try
            {
                if (await IsBackendOwnedHealthyAsync().ConfigureAwait(false))
                    return true;
            }
            catch { }

            await Task.Delay(HealthCheckIntervalMs).ConfigureAwait(false);
        }

        return false;
    }

    private async Task<bool> IsBackendOwnedHealthyAsync()
    {
        using var revalidation = await BackendOwnerCapability
            .BeginRevalidationAsync()
            .ConfigureAwait(false);
        if (!await IsBackendAlreadyHealthyAsync().ConfigureAwait(false))
            return false;
        if (!await VerifyBackendOwnershipAsync().ConfigureAwait(false))
            return false;
        revalidation.CompleteVerification();
        return true;
    }

    private async Task<bool> VerifyBackendOwnershipAsync()
    {
        var nonce = CreateHealthNonce();
        try
        {
            // This dedicated bootstrap client is never capability-registered.
            // Health and proof requests therefore cannot leak a prior owner key.
            using var response = await _bootstrapHttpClient.GetAsync(
                $"{BackendOwnerCapability.HealthProofPath}?nonce={nonce}")
                .ConfigureAwait(false);
            if (!response.IsSuccessStatusCode)
                return false;

            using var document = JsonDocument.Parse(
                await response.Content.ReadAsStreamAsync().ConfigureAwait(false));
            var root = document.RootElement;
            if (!root.TryGetProperty("status", out var status)
                || !string.Equals(status.GetString(), "ok", StringComparison.Ordinal)
                || !root.TryGetProperty("proof", out var proof)
                || proof.ValueKind != JsonValueKind.String
                || !BackendOwnerCapability.VerifyHealthProof(
                    nonce,
                    proof.GetString() ?? string.Empty))
            {
                return false;
            }
            return true;
        }
        catch (Exception ex) when (ex is HttpRequestException
            or TaskCanceledException
            or JsonException)
        {
            _logger.LogDebug(ex, "Backend Owner-Proof fehlgeschlagen");
            return false;
        }
    }

    private static string CreateHealthNonce()
        => Convert.ToBase64String(RandomNumberGenerator.GetBytes(32))
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');

    private static bool IsEnabled(string? value)
    {
        return value is not null &&
               (value.Equals("1", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("true", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("yes", StringComparison.OrdinalIgnoreCase));
    }

    private static string? ResolvePythonExe()
    {
        var backendDir = FindBackendDirectory();
        if (backendDir == null)
            return null;
        var projectRoot = Path.GetDirectoryName(backendDir)!;
        var canonical = Path.GetFullPath(
            Path.Combine(projectRoot, ".venv", "Scripts", "python.exe"));
        var envPath = Environment.GetEnvironmentVariable("PBSTUDIO_PYTHON_EXE");
        if (!string.IsNullOrWhiteSpace(envPath) &&
            !Path.GetFullPath(envPath).Equals(
                canonical,
                StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }
        return File.Exists(canonical) ? canonical : null;
    }

    public static void SetFfprobePathEnvVar(string path)
    {
        const string key = "PBSTUDIO_FFPROBE_PATH";
        Environment.SetEnvironmentVariable(
            key,
            path,
            EnvironmentVariableTarget.Process);
    }

    public static string GetCanonicalFfmpegPath()
    {
        return ResolveCanonicalFfmpegPair().FfmpegPath;
    }

    private static (string FfmpegPath, string FfprobePath) ResolveCanonicalFfmpegPair()
    {
        var backendDir = FindBackendDirectory()
            ?? throw new DirectoryNotFoundException(
                "Backend-Verzeichnis für den kanonischen FFmpeg-Pfad fehlt.");
        var projectRoot = Path.GetDirectoryName(backendDir)!;
        var stableBin = Path.Combine(projectRoot, "tools", "ffmpeg", "bin");
        var ffmpegPath = Path.Combine(stableBin, "ffmpeg.exe");
        var ffprobePath = Path.Combine(stableBin, "ffprobe.exe");
        if (!File.Exists(ffmpegPath) || !File.Exists(ffprobePath))
        {
            throw new FileNotFoundException(
                "Das kanonische FFmpeg/FFprobe-Paar ist unvollständig.",
                stableBin);
        }
        return (Path.GetFullPath(ffmpegPath), Path.GetFullPath(ffprobePath));
    }

    private static (string ManifestHash, string LibraryHash)
        ResolveCanonicalLhmHashes(string projectRoot)
    {
        var contractPath = Path.Combine(projectRoot, "config", "lhm-runtime.json");
        if (!File.Exists(contractPath))
            throw new FileNotFoundException(
                "Der kanonische LibreHardwareMonitor-Vertrag fehlt.",
                contractPath);

        using var document = JsonDocument.Parse(File.ReadAllBytes(contractPath));
        var root = document.RootElement;
        if (root.GetProperty("schema_version").GetInt32() != 1)
            throw new InvalidDataException(
                "Nicht unterstützte LibreHardwareMonitor-Vertragsversion.");

        var active = root.GetProperty("active");
        var bundleDir = Path.GetFullPath(
            Path.Combine(projectRoot, active.GetProperty("bundle_dir").GetString()!));
        var relativeBundle = Path.GetRelativePath(projectRoot, bundleDir);
        if (Path.IsPathRooted(relativeBundle) ||
            relativeBundle.Equals("..", StringComparison.Ordinal) ||
            relativeBundle.StartsWith(
                $"..{Path.DirectorySeparatorChar}",
                StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "LibreHardwareMonitor-Bundle liegt außerhalb des Projekts.");
        }

        var manifestName = active.GetProperty("manifest").GetString()!;
        var libraryName = active.GetProperty("library").GetString()!;
        if (Path.GetFileName(manifestName) != manifestName ||
            Path.GetFileName(libraryName) != libraryName)
        {
            throw new InvalidDataException(
                "LibreHardwareMonitor-Vertrag enthält ungültige Dateinamen.");
        }

        var manifestPath = Path.Combine(bundleDir, manifestName);
        var libraryPath = Path.Combine(bundleDir, libraryName);
        var expectedManifestHash = active
            .GetProperty("manifest_sha256")
            .GetString()!
            .ToUpperInvariant();
        var expectedLibraryHash = active
            .GetProperty("library_sha256")
            .GetString()!
            .ToUpperInvariant();
        var actualManifestHash = Convert.ToHexString(
            SHA256.HashData(File.ReadAllBytes(manifestPath)));
        var actualLibraryHash = Convert.ToHexString(
            SHA256.HashData(File.ReadAllBytes(libraryPath)));
        if (!actualManifestHash.Equals(
                expectedManifestHash,
                StringComparison.Ordinal) ||
            !actualLibraryHash.Equals(
                expectedLibraryHash,
                StringComparison.Ordinal))
        {
            throw new InvalidDataException(
                "LibreHardwareMonitor-Vertrag oder Bibliothek stimmt nicht mit " +
                "dem freigegebenen SHA-256 überein.");
        }
        return (expectedManifestHash, expectedLibraryHash);
    }

    private static bool IsPython311(string pythonExe)
    {
        try
        {
            using var process = Process.Start(new ProcessStartInfo
            {
                FileName = pythonExe,
                Arguments = "--version",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            });
            if (process == null)
                return false;

            if (!process.WaitForExit(5_000))
            {
                process.Kill(entireProcessTree: true);
                return false;
            }

            var version = process.StandardOutput.ReadToEnd().Trim();
            if (string.IsNullOrWhiteSpace(version))
                version = process.StandardError.ReadToEnd().Trim();
            return version.StartsWith("Python 3.11.", StringComparison.Ordinal);
        }
        catch
        {
            return false;
        }
    }

    // The lifecycle gate remains valid because bounded OnExit cleanup can still
    // be executing StartAsync/StopAsync when the service provider disposes this service.
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _isStopping = true;
        _bootstrapHttpClient.Dispose();
        if (!ReferenceEquals(_bootstrapHttpClient, _protectedHttpClient))
            _protectedHttpClient.Dispose();
    }

    // ── AP3.1: Kill-on-Close JobObject ───────────────────────────────────────
    // Garantiert, dass der uvicorn-Prozessbaum stirbt, sobald der WPF-Prozess
    // endet — auch bei hartem Crash, wo OnExit/StopAsync nie laufen.
    // Best-effort: schlägt die Zuweisung fehl (z.B. Prozess bereits in
    // einem Job ohne Nested-Job-Support), bleibt das bisherige Verhalten.

    private static IntPtr _jobHandle = IntPtr.Zero;
    private static readonly object _jobLock = new();

    private static void AssignToKillOnCloseJob(Process process, ILogger logger)
    {
        try
        {
            lock (_jobLock)
            {
                if (_jobHandle == IntPtr.Zero)
                {
                    _jobHandle = JobObjectNative.CreateJobObject(IntPtr.Zero, null);
                    if (_jobHandle == IntPtr.Zero)
                    {
                        logger.LogDebug("JobObject konnte nicht erstellt werden (Win32={Err})", Marshal.GetLastWin32Error());
                        return;
                    }

                    var info = new JobObjectNative.JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
                    info.BasicLimitInformation.LimitFlags = JobObjectNative.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                    var length = Marshal.SizeOf<JobObjectNative.JOBOBJECT_EXTENDED_LIMIT_INFORMATION>();
                    var infoPtr = Marshal.AllocHGlobal(length);
                    try
                    {
                        Marshal.StructureToPtr(info, infoPtr, false);
                        if (!JobObjectNative.SetInformationJobObject(
                                _jobHandle, JobObjectNative.JobObjectExtendedLimitInformation, infoPtr, (uint)length))
                        {
                            logger.LogDebug("SetInformationJobObject fehlgeschlagen (Win32={Err})", Marshal.GetLastWin32Error());
                            return;
                        }
                    }
                    finally
                    {
                        Marshal.FreeHGlobal(infoPtr);
                    }
                }

                if (JobObjectNative.AssignProcessToJobObject(_jobHandle, process.Handle))
                    logger.LogInformation("Python-Prozess dem Kill-on-Close JobObject zugewiesen (kein Zombie-Backend bei WPF-Crash)");
                else
                    logger.LogDebug("AssignProcessToJobObject fehlgeschlagen (Win32={Err})", Marshal.GetLastWin32Error());
            }
        }
        catch (Exception ex)
        {
            logger.LogDebug(ex, "JobObject-Zuweisung fehlgeschlagen (best-effort, kein Abbruch)");
        }
    }

    private static class JobObjectNative
    {
        internal const int JobObjectExtendedLimitInformation = 9;
        internal const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string? name);

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint infoLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

        [StructLayout(LayoutKind.Sequential)]
        internal struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public long Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        internal struct IO_COUNTERS
        {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        internal struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }
    }

    private static string? FindBackendDirectory()
    {
        var envBackend = Environment.GetEnvironmentVariable("PBSTUDIO_BACKEND_DIR");
        if (!string.IsNullOrWhiteSpace(envBackend))
        {
            var envFull = Path.GetFullPath(envBackend);
            if (Directory.Exists(envFull) && File.Exists(Path.Combine(envFull, "main.py")))
                return envFull;
        }

        var exeDir = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
        for (var current = exeDir; current != null; current = current.Parent)
        {
            var backendCandidate = Path.Combine(current.FullName, "backend");
            if (Directory.Exists(backendCandidate) && File.Exists(Path.Combine(backendCandidate, "main.py")))
                return backendCandidate;
        }

        var explicitCandidates = new[]
        {
            Path.Combine(exeDir.FullName, "..", "..", "..", "backend"),
            Path.Combine(exeDir.FullName, "..", "..", "..", "..", "backend"),
            Path.Combine(exeDir.FullName, "..", "backend"),
            Path.Combine(exeDir.FullName, "backend"),
        };

        foreach (var candidate in explicitCandidates)
        {
            var full = Path.GetFullPath(candidate);
            if (Directory.Exists(full) && File.Exists(Path.Combine(full, "main.py")))
                return full;
        }

        return null;
    }
}
