using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Runtime.InteropServices;
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
    private readonly HttpClient _httpClient;
    private Process? _pythonProcess;
    private bool _isRunning;
    private volatile bool _isStopping;
    private volatile bool _ownsProcess;
    private readonly SemaphoreSlim _lifecycleGate = new(1, 1);
    private bool _disposed;

    private static readonly string PythonExe = ResolvePythonExe();
    private static readonly bool PreferExternalBackend = IsEnabled(Environment.GetEnvironmentVariable("PBSTUDIO_BACKEND_MANAGED_EXTERNALLY"));
    private const int Port = 8765;
    private const int StartupTimeoutMs = 30_000;
    private const int HealthCheckIntervalMs = 500;

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
    {
        _logger = logger;
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{Port}"),
            Timeout = TimeSpan.FromMinutes(20),
        };
    }

    public async Task StartAsync()
    {
        if (_isStopping) return;

        await _lifecycleGate.WaitAsync().ConfigureAwait(false);
        try
        {
            if (_isStopping) return;
            _isStopping = false;

            if (_isRunning) return;

            if (await IsBackendAlreadyHealthyAsync().ConfigureAwait(false))
            {
                AttachToExistingBackend("Python Backend läuft bereits auf Port {Port} - kein neuer Start nötig");
                return;
            }

            if (PreferExternalBackend)
            {
                _logger.LogWarning("Extern verwaltetes Backend erwartet, aber Port {Port} ist nicht gesund - es wird kein zweiter Backend-Prozess gestartet", Port);
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
                FileName = PythonExe,
                Arguments = $"-m uvicorn backend.main:app --host 127.0.0.1 --port {Port}",
                WorkingDirectory = projectRoot,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            startInfo.Environment["PYTHONPATH"] = Path.Combine(projectRoot, "src");

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

                var backendHealthy = await WaitForHealthAsync().ConfigureAwait(false);
                if (backendHealthy)
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

                if (await IsBackendAlreadyHealthyAsync().ConfigureAwait(false))
                {
                    AttachToExistingBackend("Backend wurde während des Starts von einem anderen Owner übernommen - hänge an bestehende Instanz an");
                    return;
                }

                _isRunning = false;
                _ownsProcess = false;
                StatusChanged?.Invoke(this, false);
                _logger.LogError("Python Backend Health-Check fehlgeschlagen");

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
                    await _httpClient.PostAsync("/shutdown", null).ConfigureAwait(false);
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

    private void StartWatchdog()
    {
        _ = Task.Run(async () =>
        {
            while (_isRunning)
            {
                await Task.Delay(10_000).ConfigureAwait(false);
                if (_pythonProcess == null || _pythonProcess.HasExited)
                {
                    if (await IsBackendAlreadyHealthyAsync().ConfigureAwait(false))
                    {
                        _logger.LogDebug("Backend-Health ist weiterhin OK, obwohl der Startprozess beendet wurde - vermutlich Python-Wrapper/Child-Prozess auf Windows");
                        continue;
                    }

                    _isRunning = false;
                    StatusChanged?.Invoke(this, false);

                    if (_isStopping || !_ownsProcess)
                        break;

                    _logger.LogWarning("Python Backend unerwartet beendet – starte neu...");
                    _pythonProcess = null;
                    await StartAsync().ConfigureAwait(false);
                    break;
                }
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
    }

    private async Task<bool> IsBackendAlreadyHealthyAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync("/health").ConfigureAwait(false);
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
                var response = await _httpClient.GetAsync("/health").ConfigureAwait(false);
                if (response.IsSuccessStatusCode)
                    return true;
            }
            catch { }

            await Task.Delay(HealthCheckIntervalMs).ConfigureAwait(false);
        }

        return false;
    }

    private static bool IsEnabled(string? value)
    {
        return value is not null &&
               (value.Equals("1", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("true", StringComparison.OrdinalIgnoreCase) ||
                value.Equals("yes", StringComparison.OrdinalIgnoreCase));
    }

    private static string ResolvePythonExe()
    {
        var envPath = Environment.GetEnvironmentVariable("PBSTUDIO_PYTHON_EXE");
        if (!string.IsNullOrEmpty(envPath) && File.Exists(envPath))
            return envPath;

        var backendDir = FindBackendDirectory();
        if (backendDir != null)
        {
            var projectRoot = Path.GetDirectoryName(backendDir)!;
            var venvPython = Path.Combine(projectRoot, ".venv", "Scripts", "python.exe");
            if (File.Exists(venvPython)) return venvPython;
        }

        var userName = Environment.UserName;
        var candidates = new[]
        {
            $@"C:\Users\{userName}\AppData\Local\Programs\Python\Python311\python.exe",
            $@"C:\Users\{userName}\AppData\Local\Programs\Python\Python312\python.exe",
            @"C:\Python311\python.exe",
            @"C:\Program Files\Python311\python.exe",
        };
        foreach (var c in candidates)
            if (File.Exists(c)) return c;

        var pyLauncher = @"C:\Windows\py.exe";
        if (File.Exists(pyLauncher)) return pyLauncher;

        return "python";
    }

    // R16/HIGH-002: PythonBridgeService owned an HttpClient and SemaphoreSlim but
    // had no IDisposable implementation. On app exit both were silently leaked.
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _isStopping = true;
        _httpClient.Dispose();
        _lifecycleGate.Dispose();
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
