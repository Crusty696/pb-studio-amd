using System.Diagnostics;
using System.IO;
using System.Net.Http;
using Microsoft.Extensions.Logging;

namespace PBStudio.UI.Services;

/// <summary>
/// Verwaltet den Python FastAPI Backend-Prozess.
/// Startet, überwacht und stoppt den Python-Server.
/// </summary>
public class PythonBridgeService
{
    private readonly ILogger<PythonBridgeService> _logger;
    private readonly HttpClient _httpClient;
    private Process? _pythonProcess;
    private bool _isRunning;

    // BUG-007 Fix: Python-Pfad konfigurierbar (Env: PBSTUDIO_PYTHON_EXE oder auto-detect)
    private static readonly string PythonExe = ResolvePythonExe();
    private const int Port = 8765;
    private const int StartupTimeoutMs = 30_000;
    private const int HealthCheckIntervalMs = 500;

    public bool IsRunning => _isRunning;
    public event EventHandler<bool>? StatusChanged;

    // KORREKTUR: HttpClient direkt erstellen — kein DI-Injection Problem für Singleton
    public PythonBridgeService(ILogger<PythonBridgeService> logger)
    {
        _logger = logger;
        _httpClient = new HttpClient
        {
            BaseAddress = new Uri($"http://127.0.0.1:{Port}"),
            Timeout = TimeSpan.FromSeconds(30),
        };
    }

    /// <summary>Startet den Python FastAPI Server.</summary>
    public async Task StartAsync()
    {
        if (_isRunning) return;

        var backendDir = FindBackendDirectory();
        if (backendDir == null)
        {
            _logger.LogError("Backend-Verzeichnis nicht gefunden!");
            return;
        }

        _logger.LogInformation("Starte Python Backend: {Dir}", backendDir);

        var startInfo = new ProcessStartInfo
        {
            FileName = PythonExe,
            Arguments = $"-m uvicorn backend.main:app --host 127.0.0.1 --port {Port}",
            WorkingDirectory = Path.GetDirectoryName(backendDir)!,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };

        try
        {
            _pythonProcess = Process.Start(startInfo);
            if (_pythonProcess == null)
            {
                _logger.LogError("Python-Prozess konnte nicht gestartet werden");
                return;
            }

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

            _isRunning = await WaitForHealthAsync().ConfigureAwait(false);
            StatusChanged?.Invoke(this, _isRunning);

            if (_isRunning)
            {
                _logger.LogInformation("Python Backend gestartet (PID={Pid})", _pythonProcess.Id);
                StartWatchdog();
            }
            else
                _logger.LogError("Python Backend Health-Check fehlgeschlagen");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Fehler beim Starten des Python Backends");
        }
    }

    /// <summary>Stoppt den Python FastAPI Server.</summary>
    public async Task StopAsync()
    {
        if (!_isRunning || _pythonProcess == null) return;

        _logger.LogInformation("Stoppe Python Backend...");

        try
        {
            await _httpClient.PostAsync("/shutdown", null).ConfigureAwait(false);
            await Task.Delay(3000).ConfigureAwait(false);
        }
        catch { }

        try
        {
            if (!_pythonProcess.HasExited)
            {
                _pythonProcess.Kill(entireProcessTree: true);
                await _pythonProcess.WaitForExitAsync().ConfigureAwait(false);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Fehler beim Stoppen des Python-Prozesses");
        }

        _isRunning = false;
        StatusChanged?.Invoke(this, false);
        _logger.LogInformation("Python Backend gestoppt");
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
                    _logger.LogWarning("Python Backend unerwartet beendet — starte neu...");
                    _isRunning = false;
                    StatusChanged?.Invoke(this, false);
                    await StartAsync().ConfigureAwait(false);
                    break;
                }
            }
        });
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

    /// <summary>
    /// Ermittelt den Python-Interpreter-Pfad.
    /// Priorität: PBSTUDIO_PYTHON_EXE (Env) → py.exe Launcher → Standard-Pfade → PATH
    /// </summary>
    private static string ResolvePythonExe()
    {
        var envPath = Environment.GetEnvironmentVariable("PBSTUDIO_PYTHON_EXE");
        if (!string.IsNullOrEmpty(envPath) && File.Exists(envPath))
            return envPath;

        // Bevorzuge venv-Python im Projekt-Verzeichnis
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

    private static string? FindBackendDirectory()
    {
        var exeDir = AppDomain.CurrentDomain.BaseDirectory;
        var candidates = new[]
        {
            Path.Combine(exeDir, "..", "..", "..", "..", "backend"),
            Path.Combine(exeDir, "..", "backend"),
            Path.Combine(exeDir, "backend"),
        };

        foreach (var candidate in candidates)
        {
            var full = Path.GetFullPath(candidate);
            if (Directory.Exists(full) && File.Exists(Path.Combine(full, "main.py")))
                return full;
        }

        return null;
    }
}
