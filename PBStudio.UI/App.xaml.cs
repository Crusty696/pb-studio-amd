using System;
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

        var services = new ServiceCollection();
        ConfigureServices(services);
        _serviceProvider = services.BuildServiceProvider();

        // KRITISCH: Ioc.Default konfigurieren — Views nutzen Ioc.Default.GetRequiredService<T>()
        // für DataContext-Auflösung ohne XAML-Instantiierung
        Ioc.Default.ConfigureServices(_serviceProvider);

        // Python Backend asynchron starten — UI blockiert nicht beim Backend-Start.
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

        // MainWindow mit DI
        var mainWindow = _serviceProvider.GetRequiredService<MainWindow>();
        mainWindow.Show();
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
            builder.SetMinimumLevel(LogLevel.Debug);
            builder.AddFilter("Microsoft.Extensions.Http", LogLevel.Warning);
            builder.AddFilter("System.Net.Http.HttpClient", LogLevel.Warning);
        });

        // HTTP Client für API-Kommunikation (ApiClient + SSEClient)
        services.AddHttpClient<ApiClient>(client =>
        {
            client.BaseAddress = new Uri("http://127.0.0.1:8765");
            client.Timeout = TimeSpan.FromSeconds(30);
        });

        // Services (Singleton für Desktop-App)
        services.AddSingleton<PythonBridgeService>();   // erstellt HttpClient intern (kein DI-HttpClient)
        // KEIN AddSingleton<ApiClient>() -- würde AddHttpClient<ApiClient> überschreiben (BaseAddress-Bug)
        services.AddSingleton<IApiClient>(sp => sp.GetRequiredService<ApiClient>());
        services.AddSingleton<SSEClient>();
        services.AddSingleton<NavigationService>();
        services.AddSingleton<ProjectService>();
        services.AddSingleton<TimelineStateService>();
        services.AddSingleton<AudioLibraryStateService>();
        services.AddSingleton<VideoLibraryStateService>();

        // ViewModels (Transient — jeder Tab bekommt seine eigene Instanz via Ioc.Default)
        services.AddTransient<MainViewModel>();
        services.AddTransient<MediaIngestViewModel>();
        services.AddTransient<AudioLibraryViewModel>();
        services.AddTransient<VideoLibraryViewModel>();
        services.AddTransient<AnchorViewModel>();
        services.AddTransient<DirectorViewModel>();
        services.AddTransient<TimelineViewModel>();
        services.AddTransient<ProductionViewModel>();
        services.AddTransient<SettingsViewModel>();

        // Windows
        services.AddTransient<MainWindow>();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        var api = _serviceProvider?.GetService<IApiClient>();

        // P-3: Auto-Save: Projekt speichern bevor Backend beendet wird (5s Timeout)
        try
        {
            using var saveCts = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            var saveTask = api?.SaveProjectAsync() ?? Task.CompletedTask;
            saveTask.Wait(saveCts.Token);
        }
        catch { /* unkritisch — Projekt wird beim nächsten Start ggf. neu geladen */ }

        // Graceful Backend-Shutdown via API (3s Timeout)
        try { api?.ShutdownAsync().GetAwaiter().GetResult(); } catch { /* unkritisch */ }

        var bridge = _serviceProvider?.GetService<PythonBridgeService>();
        bridge?.StopAsync().GetAwaiter().GetResult();

        _serviceProvider?.Dispose();
        base.OnExit(e);
    }
}
