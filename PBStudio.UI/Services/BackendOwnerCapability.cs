using System;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using System.Security.Cryptography;
using System.Text;

namespace PBStudio.UI.Services;

/// <summary>Process-local capability for destructive loopback operations.</summary>
internal static class BackendOwnerCapability
{
    public const string EnvironmentVariable = "PBSTUDIO_OWNER_CAPABILITY";
    public const string HeaderName = "X-PBStudio-Owner-Capability";
    public const string HealthProofPath = "/health/proof";
    private const string HealthProofDomain = "PBStudio-health-proof-v1\0";

    private static readonly object Sync = new();
    private static readonly SemaphoreSlim RevalidationGate = new(1, 1);
    private static TaskCompletionSource HeaderTransitionsDrained =
        CompletedTransitionSource();
    private static string? _current;
    private static bool _wasProvisioned;
    private static bool _isVerified;
    private static int _activeHeaderTransitions;

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
            _wasProvisioned = !string.IsNullOrWhiteSpace(capability);
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

    public static bool WasProvisioned
    {
        get
        {
            Ensure();
            lock (Sync)
            {
                return _wasProvisioned;
            }
        }
    }

    public static string? Current
    {
        get
        {
            lock (Sync)
            {
                return _isVerified ? _current : null;
            }
        }
    }

    public sealed class RevalidationLease : IDisposable
    {
        private int _completed;

        public void CompleteVerification()
        {
            if (Interlocked.Exchange(ref _completed, 1) != 0)
                throw new InvalidOperationException("Revalidation lease was already completed.");
            CompleteRevalidation(verified: true);
        }

        public void Dispose()
        {
            if (Interlocked.Exchange(ref _completed, 1) == 0)
                CompleteRevalidation(verified: false);
        }
    }

    public sealed class RequestLease : IDisposable
    {
        private int _released;

        internal RequestLease(string capability)
        {
            Capability = capability;
        }

        public string Capability { get; }

        public void Dispose()
        {
            if (Interlocked.Exchange(ref _released, 1) == 0)
                ReleaseRequestLease();
        }
    }

    public static bool VerifyHealthProof(string nonce, string proof)
    {
        if (!IsValidNonce(nonce) || !IsLowercaseHexProof(proof))
            return false;

        string? capability;
        lock (Sync)
        {
            capability = _current;
        }
        if (string.IsNullOrWhiteSpace(capability))
            return false;

        var message = Encoding.ASCII.GetBytes(HealthProofDomain + nonce);
        var key = Encoding.UTF8.GetBytes(capability);
        var expected = HMACSHA256.HashData(key, message);
        var received = Convert.FromHexString(proof);
        if (!CryptographicOperations.FixedTimeEquals(expected, received))
        {
            return false;
        }

        return true;
    }

    public static async Task<RevalidationLease> BeginRevalidationAsync(
        CancellationToken cancellationToken = default)
    {
        await RevalidationGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            lock (Sync)
            {
                _isVerified = false;
            }
            await HeaderTransitionsDrained.Task
                .WaitAsync(cancellationToken)
                .ConfigureAwait(false);
            return new RevalidationLease();
        }
        catch
        {
            RevalidationGate.Release();
            throw;
        }
    }

    public static async ValueTask<RequestLease> AcquireRequestLeaseAsync(
        CancellationToken cancellationToken)
    {
        await RevalidationGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            lock (Sync)
            {
                if (!_isVerified || string.IsNullOrWhiteSpace(_current))
                {
                    throw new HttpRequestException(
                        "Backend owner capability is not verified.");
                }

                if (Interlocked.Increment(ref _activeHeaderTransitions) == 1)
                {
                    HeaderTransitionsDrained = new TaskCompletionSource(
                        TaskCreationOptions.RunContinuationsAsynchronously);
                }
                return new RequestLease(_current);
            }
        }
        finally
        {
            RevalidationGate.Release();
        }
    }

    private static void ReleaseRequestLease()
    {
        if (Interlocked.Decrement(ref _activeHeaderTransitions) == 0)
        {
            HeaderTransitionsDrained.TrySetResult();
        }
    }

    private static void CompleteRevalidation(bool verified)
    {
        lock (Sync)
        {
            _isVerified = verified;
        }
        RevalidationGate.Release();
    }

    private static TaskCompletionSource CompletedTransitionSource()
    {
        var source = new TaskCompletionSource(
            TaskCreationOptions.RunContinuationsAsynchronously);
        source.SetResult();
        return source;
    }

    private static bool IsValidNonce(string nonce)
    {
        if (nonce.Length is < 22 or > 128)
            return false;
        foreach (var character in nonce)
        {
            if (!(character is >= 'A' and <= 'Z'
                or >= 'a' and <= 'z'
                or >= '0' and <= '9'
                or '_' or '-'))
            {
                return false;
            }
        }
        return true;
    }

    private static bool IsLowercaseHexProof(string proof)
    {
        if (proof.Length != 64)
            return false;
        foreach (var character in proof)
        {
            if (!((character is >= '0' and <= '9')
                || (character is >= 'a' and <= 'f')))
            {
                return false;
            }
        }
        return true;
    }
}
