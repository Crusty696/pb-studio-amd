using System;
using System.Security.Cryptography;

namespace PBStudio.UI.Services;

/// <summary>Process-local capability for destructive loopback operations.</summary>
internal static class BackendOwnerCapability
{
    public const string EnvironmentVariable = "PBSTUDIO_OWNER_CAPABILITY";
    public const string HeaderName = "X-PBStudio-Owner-Capability";

    private static readonly object Sync = new();
    private static string? _current;

    public static string Ensure()
    {
        lock (Sync)
        {
            if (!string.IsNullOrWhiteSpace(_current))
            {
                return _current;
            }

            var capability = Environment.GetEnvironmentVariable(
                EnvironmentVariable,
                EnvironmentVariableTarget.Process);
            if (string.IsNullOrWhiteSpace(capability))
            {
                capability = Convert.ToBase64String(
                    RandomNumberGenerator.GetBytes(32));
            }
            _current = capability;
            // Child processes receive the capability only through an explicit
            // ProcessStartInfo.Environment assignment.
            Environment.SetEnvironmentVariable(
                EnvironmentVariable,
                null,
                EnvironmentVariableTarget.Process);
            return _current;
        }
    }

    public static string? Current
    {
        get
        {
            lock (Sync)
            {
                return _current;
            }
        }
    }
}
