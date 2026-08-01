using System.IO;
using System.Reflection;
using System.Runtime.ExceptionServices;
using PBStudio.UI.Services;

namespace PBStudio.UI.Tests;

internal sealed class ApiClientHarness
{
    private readonly Dictionary<string, Func<object?[]?, object?>> _handlers = [];

    private ApiClientHarness()
    {
        Client = DispatchProxy.Create<IApiClient, ApiClientProxy>();
        ((ApiClientProxy)(object)Client).InvokeHandler = Invoke;
    }

    public IApiClient Client { get; }

    public static ApiClientHarness Create() => new();

    public ApiClientHarness Handle(string methodName, Func<object?[]?, object?> handler)
    {
        _handlers[methodName] = handler;
        return this;
    }

    private object? Invoke(MethodInfo method, object?[]? arguments)
    {
        if (_handlers.TryGetValue(method.Name, out var handler))
            return handler(arguments);

        return ApiClientProxy.CompletedDefault(method.ReturnType);
    }

    public class ApiClientProxy : DispatchProxy
    {
        public Func<MethodInfo, object?[]?, object?>? InvokeHandler { get; set; }

        protected override object? Invoke(MethodInfo? targetMethod, object?[]? args)
        {
            ArgumentNullException.ThrowIfNull(targetMethod);
            return InvokeHandler?.Invoke(targetMethod, args)
                ?? CompletedDefault(targetMethod.ReturnType);
        }

        internal static object? CompletedDefault(Type returnType)
        {
            if (returnType == typeof(void))
                return null;
            if (returnType == typeof(Task))
                return Task.CompletedTask;
            if (returnType.IsGenericType
                && returnType.GetGenericTypeDefinition() == typeof(Task<>))
            {
                var valueType = returnType.GetGenericArguments()[0];
                return typeof(Task)
                    .GetMethod(nameof(Task.FromResult))!
                    .MakeGenericMethod(valueType)
                    .Invoke(null, [valueType.IsValueType ? Activator.CreateInstance(valueType) : null]);
            }
            if (returnType.IsGenericType
                && returnType.GetGenericTypeDefinition() == typeof(IAsyncEnumerable<>))
            {
                return typeof(ApiClientProxy)
                    .GetMethod(nameof(EmptyAsync), BindingFlags.Static | BindingFlags.NonPublic)!
                    .MakeGenericMethod(returnType.GetGenericArguments()[0])
                    .Invoke(null, null);
            }
            return returnType.IsValueType ? Activator.CreateInstance(returnType) : null;
        }

        private static async IAsyncEnumerable<T> EmptyAsync<T>()
        {
            await Task.CompletedTask;
            yield break;
        }
    }
}

internal sealed class SettingsServiceStub : ISettingsService
{
    public PbSettings Current { get; } = new();
    public string ConfigFilePath { get; init; } = @"C:\PBStudio.Tests\settings.json";
    public SettingsLoadResult LoadResult { get; set; } =
        new(true, false, SettingsPersistenceFailure.None, null);
    public SettingsSaveResult SaveResult { get; set; } =
        new(true, SettingsPersistenceFailure.None, null);
    public string? ValidationError { get; set; }

    public SettingsLoadResult Load() => LoadResult;
    public SettingsSaveResult Save() => SaveResult;

    public bool ValidateFFmpegPath(string? path, out string? errorMessage)
    {
        errorMessage = ValidationError;
        return errorMessage is null;
    }

    public Task<string?> ProbeFFmpegVersionAsync(
        string path,
        CancellationToken ct = default) =>
        Task.FromResult<string?>(null);

    public Task<FfmpegRuntimeProbeResult> ProbeCanonicalFFmpegRuntimeAsync(
        CancellationToken ct = default) =>
        Task.FromResult(new FfmpegRuntimeProbeResult(
            false,
            "",
            null,
            null,
            null,
            null,
            "Nicht für diesen Vertragstest konfiguriert."));
}

internal sealed class DialogServiceStub : IDialogService
{
    public string? OpenFile(string title, string filter, string? initialDirectory = null) => null;
    public List<string> OpenFiles(string title, string filter, string? initialDirectory = null) => [];
    public string? OpenFolder(string title, string? initialDirectory = null) => null;
    public string? SaveFile(
        string title,
        string filter,
        string defaultFileName,
        string? initialDirectory = null) => null;
    public bool ConfirmDestructiveAction(string title, string message) => false;
}

internal sealed class TemporaryDirectory : IDisposable
{
    public TemporaryDirectory()
    {
        Path = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(),
            "PBStudio.UI.Tests",
            Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path);
    }

    public string Path { get; }

    public void Dispose()
    {
        if (Directory.Exists(Path))
            Directory.Delete(Path, recursive: true);
    }
}

internal sealed class EnvironmentVariableScope : IDisposable
{
    private readonly string _name;
    private readonly string? _originalValue;

    public EnvironmentVariableScope(string name, string? value)
    {
        _name = name;
        _originalValue = Environment.GetEnvironmentVariable(name);
        Environment.SetEnvironmentVariable(name, value);
    }

    public void Dispose() =>
        Environment.SetEnvironmentVariable(_name, _originalValue);
}

internal static class RepositoryLayout
{
    public static string FindProjectRoot()
    {
        for (var current = new DirectoryInfo(AppContext.BaseDirectory);
             current is not null;
             current = current.Parent)
        {
            if (File.Exists(System.IO.Path.Combine(current.FullName, "backend", "main.py"))
                && File.Exists(System.IO.Path.Combine(
                    current.FullName,
                    "PBStudio.UI",
                    "PBStudio.UI.csproj")))
            {
                return current.FullName;
            }
        }

        throw new DirectoryNotFoundException(
            "PB-Studio-Projektwurzel für nativen Test nicht gefunden.");
    }
}

internal static class TestWait
{
    public static async Task UntilAsync(
        Func<bool> predicate,
        TimeSpan? timeout = null)
    {
        var expiresAt = DateTime.UtcNow + (timeout ?? TimeSpan.FromSeconds(3));
        while (!predicate())
        {
            if (DateTime.UtcNow >= expiresAt)
                throw new TimeoutException("Asynchroner Vertrag erreichte keinen Endzustand.");
            await Task.Delay(10);
        }
    }
}

internal static class StaTest
{
    public static void Run(Action action)
    {
        ExceptionDispatchInfo? failure = null;
        var thread = new Thread(() =>
        {
            try
            {
                action();
            }
            catch (Exception ex)
            {
                failure = ExceptionDispatchInfo.Capture(ex);
            }
        });
        thread.IsBackground = true;
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        if (!thread.Join(TimeSpan.FromSeconds(10)))
            throw new TimeoutException("STA-Vertragstest überschritt 10 Sekunden.");
        failure?.Throw();
    }
}
