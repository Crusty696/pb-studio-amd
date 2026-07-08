using System;
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

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // R10/WPF-01: Global exception handlers — prevent silent crash swallowing
        DispatcherUnhandledException += (_, args) =>
        {
            System.Diagnostics.Debug.WriteLine(
                $"[PBStudio] Unhandled UI exception: {args.Exception}");
            _serviceProvider?.GetService<ILogger<App>>()
                ?.LogCritical(args.Exception, "Unbehandelte UI-Exception");
            args.Handled = true; // Prevent crash — log and continue
        };
        AppDomain.CurrentDomain.UnhandledException += (_, args) =>
        {
            if (args.ExceptionObject is Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[PBStudio] Unhandled domain exception: {ex}");
                _serviceProvider?.GetService<ILogger<App>>()
                    ?.LogCritical(ex, "Unbehandelte Domain-Exception");
            }
        };
        TaskScheduler.UnobservedTaskException += (_, args) =>
        {
            System.Diagnostics.Debug.WriteLine(
                $"[PBStudio] Unobserved task exception: {args.Exception}");
            _serviceProvider?.GetService<ILogger<App>>()
                ?.LogError(args.Exception, "Unbeobachtete Task-Exception");
            args.SetObserved(); // Prevent finalization crash
        };

        var services = new ServiceCollection();
        ConfigureServices(services);
        _serviceProvider = services.BuildServiceProvider();

        Ioc.Default.ConfigureServices(_serviceProvider);

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

    private static void ConfigureServices(IServiceCollection services)
    {
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
            builder.AddProvider(new TerminalLoggerProvider());
            builder.SetMinimumLevel(LogLevel.Debug);
            builder.AddFilter("Microsoft.Extensions.Http", LogLevel.Warning);
            builder.AddFilter("System.Net.Http.HttpClient", LogLevel.Warning);
        });

        // HTTP Client für API-Kommunikation (ApiClient + SSEClient)
        services.AddHttpClient<ApiClient>(client =>
        {
            client.BaseAddress = new Uri("http://127.0.0.1:8765");
            client.Timeout = TimeSpan.FromMinutes(20);
        });

        // Services (Singleton für Desktop-App)
        services.AddSingleton<PythonBridgeService>();   // erstellt HttpClient intern (kein DI-HttpClient)
        // KEIN AddSingleton<ApiClient>() -- würde AddHttpClient<ApiClient> überschreiben (BaseAddress-Bug)
        services.AddSingleton<IApiClient>(sp => sp.GetRequiredService<ApiClient>());
        services.AddSingleton<SSEClient>();
        services.AddSingleton<IDialogService, DialogService>();
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
                var cleanup = Task.Run(async () =>
                {
                    using var shutdownCts = new CancellationTokenSource(TimeSpan.FromSeconds(8));
                    var api = sp.GetService<IApiClient>();
                    if (api != null)
                    {
                        // K7: Speichern VOR BeginShutdown (Token-Cancel) ausführen
                        try
                        {
                            await api.SaveProjectAsync().WaitAsync(shutdownCts.Token).ConfigureAwait(false);
                        }
                        catch (Exception saveEx)
                        {
                            System.Diagnostics.Debug.WriteLine($"[PBStudio] Project save on exit failed: {saveEx.Message}");
                        }

                        // Jetzt laufende Background-Tasks canceln und uvicorn-Shutdown triggern
                        (api as ApiClient)?.BeginShutdown();

                        try
                        {
                            await api.ShutdownAsync().WaitAsync(shutdownCts.Token).ConfigureAwait(false);
                        }
                        catch (Exception shutdownEx)
                        {
                            System.Diagnostics.Debug.WriteLine($"[PBStudio] Backend shutdown call failed: {shutdownEx.Message}");
                        }
                    }
                    var bridge = sp.GetService<PythonBridgeService>();
                    if (bridge != null)
                        await bridge.StopAsync().WaitAsync(shutdownCts.Token).ConfigureAwait(false);
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
