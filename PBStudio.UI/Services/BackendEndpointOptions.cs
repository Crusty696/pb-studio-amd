using System.IO;
using System.Text.Json;

namespace PBStudio.UI.Services;

public sealed record BackendEndpointOptions(string Scheme, string Host, int Port)
{
    private static readonly HashSet<string> LoopbackHosts = new(
        ["127.0.0.1", "localhost", "::1"],
        StringComparer.Ordinal);

    public Uri BaseUri => new UriBuilder(Scheme, Host, Port).Uri;

    public string DisplayValue => $"{BaseUri.Scheme}://{BaseUri.Authority}";

    public static BackendEndpointOptions Load(string? path = null)
    {
        var resolvedPath = path ?? Path.Combine(
            AppContext.BaseDirectory,
            "appsettings.json");
        using var document = JsonDocument.Parse(File.ReadAllBytes(resolvedPath));
        var rootProperties = document.RootElement.EnumerateObject().ToArray();
        if (rootProperties.Length != 1 || rootProperties[0].Name != "Backend")
            throw new InvalidDataException("appsettings.json may only contain Backend.");
        if (!document.RootElement.TryGetProperty("Backend", out var backend)
            || backend.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidDataException(
                "appsettings.json must contain a Backend object.");
        }

        var scheme = ReadRequiredString(backend, "Scheme");
        var configuredHost = ReadRequiredString(backend, "Host");
        var host = Environment.GetEnvironmentVariable("PBSTUDIO_HOST")
            ?? configuredHost;
        var backendProperties = backend.EnumerateObject().Select(item => item.Name).ToHashSet();
        if (!backendProperties.SetEquals(["Scheme", "Host", "Port"]))
            throw new InvalidDataException(
                "Backend must contain Scheme, Host and Port only.");
        if (!backend.TryGetProperty("Port", out var portElement)
            || !portElement.TryGetInt32(out var configuredPort))
        {
            throw new InvalidDataException("Backend.Port must be an integer.");
        }
        var portOverride = Environment.GetEnvironmentVariable("PBSTUDIO_PORT");
        var port = string.IsNullOrEmpty(portOverride)
            ? configuredPort
            : int.TryParse(
                portOverride,
                System.Globalization.NumberStyles.None,
                System.Globalization.CultureInfo.InvariantCulture,
                out var parsedPort)
                ? parsedPort
                : throw new InvalidDataException(
                    "PBSTUDIO_PORT must be a decimal integer.");

        if (!scheme.Equals(Uri.UriSchemeHttp, StringComparison.Ordinal))
            throw new InvalidDataException("Backend.Scheme must be http.");
        if (!LoopbackHosts.Contains(host))
            throw new InvalidDataException("Backend.Host must be a loopback host.");
        if (port is < 1 or > 65535)
            throw new InvalidDataException("Backend.Port must be between 1 and 65535.");

        return new BackendEndpointOptions(
            Uri.UriSchemeHttp,
            host,
            port);
    }

    private static string ReadRequiredString(JsonElement parent, string name)
    {
        if (!parent.TryGetProperty(name, out var value)
            || value.ValueKind != JsonValueKind.String
            || string.IsNullOrWhiteSpace(value.GetString()))
        {
            throw new InvalidDataException($"Backend.{name} must be a string.");
        }
        var result = value.GetString()!;
        if (result != result.Trim())
            throw new InvalidDataException($"Backend.{name} may not contain whitespace.");
        return result;
    }
}
