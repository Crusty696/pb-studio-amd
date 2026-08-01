using System;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using CommunityToolkit.Mvvm.DependencyInjection;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using PBStudio.UI.Services;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI;

/// <summary>
/// PB Studio AMD – WPF Application Entry Point.
/// Konfiguriert DI Container (ServiceProvider) und Ioc.Default (für View DataContext).
/// </summary>
public partial class App : Application
{
    private ServiceProvider? _serviceProvider;
    private int _fatalShutdownStarted;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // Unknown dispatcher failures are fatal: continuing can corrupt project state.
        DispatcherUnhandledException += (_, args) =>
        {
            try
            {
                LogRedactedException(
                    LogLevel.Critical,
                    "Unbehandelte UI-Exception",
                    args.Exception);
                args.Handled = true;
                BeginFatalShutdown();
            }
            catch
            {
                // If even the fatal path fails, let WPF terminate normally.
                args.Handled = false;
            }
        };
        AppDomain.CurrentDomain.UnhandledException += (_, args) =>
        {
            if (args.ExceptionObject is Exception ex)
            {
                LogRedactedException(
                    LogLevel.Critical,
                    "Unbehandelte Domain-Exception",
                    ex);
            }
        };
        TaskScheduler.UnobservedTaskException += (_, args) =>
        {
            LogRedactedException(
                LogLevel.Error,
                "Unbeobachtete Task-Exception",
                args.Exception);
            args.SetObserved();
        };

        var services = new ServiceCollection();
        ConfigureServices(services);
        _serviceProvider = services.BuildServiceProvider();

        Ioc.Default.ConfigureServices(_serviceProvider);

        // H-18: Runtime-Environment muss gesetzt sein, bevor der Backend-Prozess
        // erzeugt wird. SettingsViewModel entsteht erst beim ersten SETTINGS-Tab.
        var settings = _serviceProvider.GetRequiredService<ISettingsService>();
        settings.Load();
        PythonBridgeService.ApplyRuntimeEnvironment(settings.Current);

        // MainWindow SOFORT zeigen
        var mainWindow = _serviceProvider.GetRequiredService<MainWindow>();
        mainWindow.Show();

        // Erst danach Backend-Start triggern
        var bridge = _serviceProvider.GetRequiredService<PythonBridgeService>();
        _ = Task.Run(async () =>
        {
            try
            {
                await bridge.StartAsync();
            }
            catch (Exception ex)
            {
                var logger = _serviceProvider.GetService<ILogger<App>>();
                logger?.LogError(ex, "Python Backend konnte nicht gestartet werden");
            }
        });
    }

    private void BeginFatalShutdown()
    {
        if (Interlocked.Exchange(ref _fatalShutdownStarted, 1) != 0)
            return;

        MessageBox.Show(
            "PB Studio muss nach einem unerwarteten Fehler beendet werden. "
            + "Details wurden sicher im Protokoll gespeichert.",
            "PB Studio – Schwerwiegender Fehler",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
        Shutdown(-1);
    }

    private void LogRedactedException(
        LogLevel level,
        string source,
        Exception exception)
    {
        var redacted = TerminalLogRedactor.Redact(exception.ToString());
        System.Diagnostics.Debug.WriteLine($"[PBStudio] {source}: {redacted}");
        _serviceProvider?.GetService<ILogger<App>>()
            ?.Log(level, "{Source}: {Crash}", source, redacted);
    }

    private static void ConfigureServices(IServiceCollection services)
    {
        var terminalLogBuffer = new TerminalLogBuffer();
        services.AddSingleton(terminalLogBuffer);

        // Logging — Console + Datei
        var logPath = System.IO.Path.Combine(
            AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", "logs", "wpf_app.log");
        var logDir = System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(logPath))!;
        if (!System.IO.Directory.Exists(logDir))
            System.IO.Directory.CreateDirectory(logDir);
        var logFile = System.IO.Path.GetFullPath(logPath);

        services.AddLogging(builder =>
        {
            builder.AddConsole();
            builder.AddProvider(new FileLoggerProvider(logFile));
            builder.AddProvider(new TerminalLoggerProvider(terminalLogBuffer));
            builder.SetMinimumLevel(LogLevel.Debug);
            builder.AddFilter("Microsoft.Extensions.Http", LogLevel.Warning);
            builder.AddFilter("System.Net.Http.HttpClient", LogLevel.Warning);
        });

        // HTTP Client für API-Kommunikation (ApiClient + SSEClient)
        services.AddTransient<OwnerCapabilityRequestHandler>();
        services.AddHttpClient<ApiClient>(client =>
        {
            client.BaseAddress = new Uri("http://127.0.0.1:8765");
            client.Timeout = TimeSpan.FromMinutes(20);
        })
        .ConfigurePrimaryHttpMessageHandler(static () => new HttpClientHandler
        {
            AllowAutoRedirect = false,
        })
        .AddHttpMessageHandler<OwnerCapabilityRequestHandler>();

        // Services (Singleton für Desktop-App)
        services.AddSingleton<PythonBridgeService>();   // erstellt HttpClient intern (kein DI-HttpClient)
        // KEIN AddSingleton<ApiClient>() -- würde AddHttpClient<ApiClient> überschreiben (BaseAddress-Bug)
        services.AddSingleton<IApiClient>(sp => sp.GetRequiredService<ApiClient>());
        services.AddSingleton<SSEClient>();
        services.AddSingleton<IDialogService, DialogService>();
        services.AddSingleton<ISettingsService, SettingsService>();
        services.AddSingleton<ProjectService>();
        services.AddSingleton<TimelineStateService>();
        services.AddSingleton<AudioLibraryStateService>();
        services.AddSingleton<VideoLibraryStateService>();

        // ViewModels (Transient — jeder Tab bekommt seine eigene Instanz via Ioc.Default)
        services.AddTransient<MainViewModel>();
        services.AddTransient<ProjectOverviewViewModel>();
        services.AddTransient<MediaIngestViewModel>();
        services.AddTransient<AudioLibraryViewModel>();
        services.AddTransient<VideoLibraryViewModel>();
        services.AddTransient<AnchorViewModel>();
        services.AddTransient<DirectorViewModel>();
        services.AddTransient<TimelineViewModel>();
        services.AddTransient<ProductionViewModel>();
        services.AddTransient<SettingsViewModel>();
        services.AddTransient<BrainViewModel>();
        services.AddTransient<LearningSessionViewModel>();
        services.AddTransient<VramTelemetryViewModel>();
        services.AddTransient<ModelManagerViewModel>();
        services.AddTransient<ChatViewModel>();
        services.AddTransient<TerminalViewModel>();

        // Windows
        services.AddTransient<MainWindow>();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        // AP3.1 (Audit 2026-06-10): vorher `async void` — nach dem ersten await
        // kehrte OnExit zurück, der Prozess konnte enden BEVOR Save/Shutdown/
        // StopAsync liefen (uvicorn-Zombie auf Port 8765, Save verloren).
        // Jetzt: Cleanup läuft auf dem ThreadPool (kein SyncContext → kein
        // Deadlock) und OnExit blockiert gebunden (max. 12s), bis er fertig ist.
        try
        {
            var sp = _serviceProvider;
            if (sp != null)
            {
                var externalBackendFlag =
                    Environment.GetEnvironmentVariable("PBSTUDIO_BACKEND_MANAGED_EXTERNALLY");
                var externalBackendManaged = externalBackendFlag is not null &&
                    (externalBackendFlag.Equals("1", StringComparison.OrdinalIgnoreCase) ||
                     externalBackendFlag.Equals("true", StringComparison.OrdinalIgnoreCase) ||
                     externalBackendFlag.Equals("yes", StringComparison.OrdinalIgnoreCase));

                var cleanup = Task.Run(async () =>
                {
                    using var shutdownCts = new CancellationTokenSource(TimeSpan.FromSeconds(8));
                    var api = sp.GetService<IApiClient>();
                    if (api != null)
                    {
                        // Unknown UI failures may have left in-memory state inconsistent.
                        // A normal user exit still saves before cancellation.
                        if (Volatile.Read(ref _fatalShutdownStarted) == 0)
                        {
                            try
                            {
                                await api.SaveProjectAsync().WaitAsync(shutdownCts.Token).ConfigureAwait(false);
                            }
                            catch (Exception saveEx)
                            {
                                System.Diagnostics.Debug.WriteLine(
                                    $"[PBStudio] Project save on exit failed: {saveEx.Message}");
                            }
                        }

                        // Jetzt laufende Background-Tasks canceln und uvicorn-Shutdown triggern
                        (api as ApiClient)?.BeginShutdown();

                        if (!externalBackendManaged)
                        {
                            try
                            {
                                await api.ShutdownAsync().WaitAsync(shutdownCts.Token).ConfigureAwait(false);
                            }
                            catch (Exception shutdownEx)
                            {
                                System.Diagnostics.Debug.WriteLine($"[PBStudio] Backend shutdown call failed: {shutdownEx.Message}");
                            }
                        }
                    }
                    var bridge = sp.GetService<PythonBridgeService>();
                    if (!externalBackendManaged)
                    {
                        if (bridge != null)
                            await bridge.StopAsync().WaitAsync(shutdownCts.Token).ConfigureAwait(false);
                    }
                });

                if (!cleanup.Wait(TimeSpan.FromSeconds(12)))
                    System.Diagnostics.Debug.WriteLine("[PBStudio] OnExit cleanup timeout (12s) — fahre mit Dispose fort");
            }
        }
        catch (Exception ex)
        {
            // Shutdown errors are non-critical — log but always proceed with cleanup
            System.Diagnostics.Debug.WriteLine($"[PBStudio] OnExit error (non-critical): {ex.Message}");
        }
        finally
        {
            // Dispose MUST run even if shutdown tasks fail (CRITICAL-002 fix)
            try { _serviceProvider?.Dispose(); } catch { /* ServiceProvider.Dispose is best-effort */ }
            base.OnExit(e);
        }
    }
}
