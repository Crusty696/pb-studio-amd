using System.Net.Http;

namespace PBStudio.UI.Services;

/// <summary>
/// Binds the verified owner capability to one protected request at a time.
/// Bootstrap health endpoints deliberately remain unauthenticated.
/// </summary>
internal sealed class OwnerCapabilityRequestHandler : DelegatingHandler
{
    private static readonly Uri BackendOrigin = new("http://127.0.0.1:8765");

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        request.Headers.Remove(BackendOwnerCapability.HeaderName);
        if (!IsTrustedBackendRequest(request))
        {
            throw new HttpRequestException(
                "Backend owner capability may only be sent to the local backend origin.");
        }

        if (IsBootstrapHealthRequest(request))
        {
            return await base.SendAsync(request, cancellationToken)
                .ConfigureAwait(false);
        }

        using var lease = await BackendOwnerCapability
            .AcquireRequestLeaseAsync(cancellationToken)
            .ConfigureAwait(false);
        request.Headers.TryAddWithoutValidation(
            BackendOwnerCapability.HeaderName,
            lease.Capability);
        return await base.SendAsync(request, cancellationToken)
            .ConfigureAwait(false);
    }

    private static bool IsBootstrapHealthRequest(HttpRequestMessage request)
    {
        if (request.Method != HttpMethod.Get)
            return false;

        return request.RequestUri!.AbsolutePath is "/health" or "/health/proof";
    }

    private static bool IsTrustedBackendRequest(HttpRequestMessage request)
    {
        var uri = request.RequestUri;
        return uri is { IsAbsoluteUri: true }
            && uri.Scheme == BackendOrigin.Scheme
            && uri.Host == BackendOrigin.Host
            && uri.Port == BackendOrigin.Port
            && string.IsNullOrEmpty(uri.UserInfo);
    }
}
