using System.Net;
using System.Net.Http;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Services;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class T413OwnerProofTransportTests
{
    private const string HeaderName = "X-PBStudio-Owner-Capability";
    private const string Domain = "PBStudio-health-proof-v1\0";
    private const string Nonce = "T413_owner_proof_nonce";

    [TestMethod]
    public async Task ProtectedRequest_UsesOneVerifiedHeader_WithoutDefaultHeader()
    {
        var capability = EnsureVerifiedCapability();
        string[]? received = null;
        using var http = CreateProtectedHttpClient(request =>
        {
            received = GetHeader(request);
            return new HttpResponseMessage(HttpStatusCode.NoContent);
        });
        using var client = new ApiClient(http, NullLogger<ApiClient>.Instance);

        Assert.IsTrue(await client.ClearChatHistoryAsync());
        CollectionAssert.AreEqual(new[] { capability }, received!);
        Assert.IsFalse(http.DefaultRequestHeaders.Contains(HeaderName));
    }

    [TestMethod]
    public async Task SendDuringRevalidation_WaitsThenSendsOnceAfterVerification()
    {
        var capability = EnsureVerifiedCapability();
        var requestSeen = new TaskCompletionSource(
            TaskCreationOptions.RunContinuationsAsynchronously);
        string[]? received = null;
        using var http = CreateProtectedHttpClient(request =>
        {
            received = GetHeader(request);
            requestSeen.SetResult();
            return new HttpResponseMessage(HttpStatusCode.NoContent);
        });
        using IDisposable revalidation = BeginRevalidation();

        var pending = http.GetAsync("/project/info");
        await Task.Delay(50);
        Assert.IsFalse(requestSeen.Task.IsCompleted);

        CompleteVerification(revalidation);
        using var response = await pending;
        await requestSeen.Task.WaitAsync(TimeSpan.FromSeconds(2));

        Assert.AreEqual(HttpStatusCode.NoContent, response.StatusCode);
        CollectionAssert.AreEqual(new[] { capability }, received!);
    }

    [TestMethod]
    public async Task FailedProof_RejectsProtectedRequestWithoutSendingHeader()
    {
        EnsureVerifiedCapability();
        var requestSent = false;
        using var http = CreateProtectedHttpClient(_ =>
        {
            requestSent = true;
            return new HttpResponseMessage(HttpStatusCode.OK);
        });
        using (IDisposable revalidation = BeginRevalidation())
        {
        }

        try
        {
            await http.GetAsync("/project/info");
            Assert.Fail("Unverified backend ownership must reject protected requests.");
        }
        catch (HttpRequestException)
        {
        }
        Assert.IsFalse(requestSent);
        Assert.IsFalse(http.DefaultRequestHeaders.Contains(HeaderName));
    }

    [TestMethod]
    public async Task UntrustedOrUnresolvedTarget_FailsClosedWithoutSendingCapability()
    {
        EnsureVerifiedCapability();
        var sent = 0;
        using var http = CreateProtectedHttpClient(_ =>
        {
            sent++;
            return new HttpResponseMessage(HttpStatusCode.OK);
        });

        foreach (var target in new[]
                 {
                     "http://127.0.0.1:8766/project/info",
                     "http://localhost:8765/project/info",
                     "https://127.0.0.1:8765/project/info",
                 })
        {
            await AssertRequestRejectedAsync(() => http.GetAsync(target));
        }

        using var handler = CreateProtectedHandler(_ =>
            new HttpResponseMessage(HttpStatusCode.OK));
        using var invoker = new HttpMessageInvoker(handler);
        await AssertRequestRejectedAsync(() => invoker.SendAsync(
            new HttpRequestMessage(HttpMethod.Get, "/project/info"),
            CancellationToken.None));

        Assert.AreEqual(0, sent);
        Assert.IsFalse(http.DefaultRequestHeaders.Contains(HeaderName));
    }

    [TestMethod]
    public async Task RedirectResponse_IsReturnedWithoutFollowingSecondRequest()
    {
        var capability = EnsureVerifiedCapability();
        var requests = 0;
        string[]? header = null;
        using var http = CreateProtectedHttpClient(request =>
        {
            requests++;
            header = GetHeader(request);
            return new HttpResponseMessage(HttpStatusCode.Found)
            {
                Headers = { Location = new Uri("http://127.0.0.1:8765/redirected") },
            };
        });

        using var response = await http.GetAsync("/project/info");

        Assert.AreEqual(HttpStatusCode.Found, response.StatusCode);
        Assert.AreEqual(1, requests);
        CollectionAssert.AreEqual(new[] { capability }, header!);
    }

    [TestMethod]
    public async Task ProtectedShutdown_WaitsForRevalidationAndSendsOneCapability()
    {
        var capability = EnsureVerifiedCapability();
        var sent = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        string[]? header = null;
        using var bootstrap = new HttpClient(new StubHandler(_ =>
            new HttpResponseMessage(HttpStatusCode.OK)));
        using var protectedHttp = CreateProtectedHttpClient(request =>
        {
            header = GetHeader(request);
            sent.SetResult();
            return new HttpResponseMessage(HttpStatusCode.NoContent);
        });
        using var bridge = CreateBridge(bootstrap, protectedHttp);
        using IDisposable revalidation = BeginRevalidation();

        var pending = InvokeOwnedShutdownAsync(bridge);
        await Task.Delay(50);
        Assert.IsFalse(sent.Task.IsCompleted);

        CompleteVerification(revalidation);
        await pending;
        await sent.Task.WaitAsync(TimeSpan.FromSeconds(2));

        CollectionAssert.AreEqual(new[] { capability }, header!);
        Assert.IsFalse(bootstrap.DefaultRequestHeaders.Contains(HeaderName));
        Assert.IsFalse(protectedHttp.DefaultRequestHeaders.Contains(HeaderName));
    }

    [TestMethod]
    public async Task CanceledProtectedSend_ReleasesItsRequestLease()
    {
        EnsureVerifiedCapability();
        using var http = CreateProtectedHttpClient(_ =>
            throw new OperationCanceledException());

        try
        {
            await http.GetAsync("/project/info");
            Assert.Fail("The canceled transport must propagate cancellation.");
        }
        catch (OperationCanceledException)
        {
        }

        using IDisposable revalidation = BeginRevalidation();
        CompleteVerification(revalidation);
    }

    [TestMethod]
    public async Task PortRebind_HealthAndProofAreHeaderless_ThenApiAndSseRemainDefaultHeaderFree()
    {
        var capability = EnsureVerifiedCapability();
        var receivedHeaders = new Dictionary<string, string[]>();
        using var bootstrapHttp = new HttpClient(new StubHandler(request =>
        {
            var path = request.RequestUri!.AbsolutePath;
            receivedHeaders[path] = GetHeader(request);
            if (path == "/health")
                return new HttpResponseMessage(HttpStatusCode.OK);

            var nonce = request.RequestUri.Query["?nonce=".Length..];
            return JsonResponse(CreateProof(capability, nonce));
        }))
        {
            BaseAddress = new Uri("http://127.0.0.1:8765"),
        };
        using var bridge = CreateBridge(bootstrapHttp);
        using var apiHttp = CreateProtectedHttpClient(_ =>
            new HttpResponseMessage(HttpStatusCode.NoContent));
        using var api = new ApiClient(apiHttp, NullLogger<ApiClient>.Instance);
        using var sse = new SSEClient(
            NullLogger<SSEClient>.Instance,
            new TerminalLogBuffer());
        var sseHttp = (HttpClient)typeof(SSEClient)
            .GetField("_httpClient", BindingFlags.Instance | BindingFlags.NonPublic)!
            .GetValue(sse)!;

        Assert.IsTrue(await InvokeOwnedHealthCheckAsync(bridge));
        Assert.AreEqual(0, receivedHeaders["/health"].Length);
        Assert.AreEqual(0, receivedHeaders["/health/proof"].Length);
        Assert.IsFalse(apiHttp.DefaultRequestHeaders.Contains(HeaderName));
        Assert.IsFalse(sseHttp.DefaultRequestHeaders.Contains(HeaderName));
    }

    [TestMethod]
    public void DisposedClient_DoesNotReceiveFutureCapabilityMutation()
    {
        EnsureVerifiedCapability();
        var http = CreateProtectedHttpClient(_ => new HttpResponseMessage(HttpStatusCode.OK));
        http.Dispose();

        using IDisposable revalidation = BeginRevalidation();
        CompleteVerification(revalidation);
    }

    private static string EnsureVerifiedCapability()
    {
        var capability = EnsureCapability();
        using IDisposable revalidation = BeginRevalidation();
        Assert.IsTrue(VerifyProof(Nonce, CreateProof(capability, Nonce)));
        CompleteVerification(revalidation);
        return capability;
    }

    private static HttpClient CreateProtectedHttpClient(
        Func<HttpRequestMessage, HttpResponseMessage> respond)
    {
        var handler = CreateProtectedHandler(respond);
        return new HttpClient(handler)
        {
            BaseAddress = new Uri("http://127.0.0.1:8765"),
        };
    }

    private static DelegatingHandler CreateProtectedHandler(
        Func<HttpRequestMessage, HttpResponseMessage> respond)
    {
        var handler = (DelegatingHandler)Activator.CreateInstance(
            CapabilityAssemblyType("OwnerCapabilityRequestHandler"),
            nonPublic: true)!;
        handler.InnerHandler = new StubHandler(respond);
        return handler;
    }

    private static IDisposable BeginRevalidation()
    {
        var task = (Task)CapabilityMethod("BeginRevalidationAsync")
            .Invoke(null, [CancellationToken.None])!;
        task.GetAwaiter().GetResult();
        return (IDisposable)task.GetType().GetProperty("Result")!.GetValue(task)!;
    }

    private static void CompleteVerification(object lease) =>
        lease.GetType().GetMethod("CompleteVerification")!.Invoke(lease, null);

    private static string EnsureCapability() =>
        (string)CapabilityMethod("Ensure").Invoke(null, null)!;

    private static bool VerifyProof(string nonce, string proof) =>
        (bool)CapabilityMethod("VerifyHealthProof").Invoke(null, [nonce, proof])!;

    private static MethodInfo CapabilityMethod(string name) =>
        CapabilityAssemblyType("BackendOwnerCapability")
            .GetMethod(name, BindingFlags.Public | BindingFlags.Static)!;

    private static Type CapabilityAssemblyType(string name) =>
        typeof(ApiClient).Assembly.GetType(
            $"PBStudio.UI.Services.{name}",
            throwOnError: true)!;

    private static PythonBridgeService CreateBridge(HttpClient bootstrapHttp) =>
        (PythonBridgeService)typeof(PythonBridgeService)
            .GetConstructor(
                BindingFlags.Instance | BindingFlags.NonPublic,
                binder: null,
                [typeof(Microsoft.Extensions.Logging.ILogger<PythonBridgeService>), typeof(HttpClient)],
                modifiers: null)!
            .Invoke([NullLogger<PythonBridgeService>.Instance, bootstrapHttp]);

    private static PythonBridgeService CreateBridge(
        HttpClient bootstrapHttp,
        HttpClient protectedHttp) =>
        (PythonBridgeService)typeof(PythonBridgeService)
            .GetConstructor(
                BindingFlags.Instance | BindingFlags.NonPublic,
                binder: null,
                [
                    typeof(Microsoft.Extensions.Logging.ILogger<PythonBridgeService>),
                    typeof(HttpClient),
                    typeof(HttpClient),
                ],
                modifiers: null)!
            .Invoke([NullLogger<PythonBridgeService>.Instance, bootstrapHttp, protectedHttp]);

    private static Task<bool> InvokeOwnedHealthCheckAsync(PythonBridgeService bridge) =>
        (Task<bool>)typeof(PythonBridgeService)
            .GetMethod(
                "IsBackendOwnedHealthyAsync",
                BindingFlags.Instance | BindingFlags.NonPublic)!
            .Invoke(bridge, null)!;

    private static Task InvokeOwnedShutdownAsync(PythonBridgeService bridge) =>
        (Task)typeof(PythonBridgeService)
            .GetMethod(
                "RequestOwnedShutdownAsync",
                BindingFlags.Instance | BindingFlags.NonPublic)!
            .Invoke(bridge, null)!;

    private static async Task AssertRequestRejectedAsync(Func<Task<HttpResponseMessage>> request)
    {
        try
        {
            using var response = await request();
            Assert.Fail("Untrusted backend targets must fail closed.");
        }
        catch (HttpRequestException)
        {
        }
    }

    private static string[] GetHeader(HttpRequestMessage request) =>
        request.Headers.TryGetValues(HeaderName, out var values) ? values.ToArray() : [];

    private static HttpResponseMessage JsonResponse(string proof) =>
        new(HttpStatusCode.OK)
        {
            Content = new StringContent(
                $"{{\"status\":\"ok\",\"proof\":\"{proof}\"}}"),
        };

    private static string CreateProof(string capability, string nonce) =>
        Convert.ToHexString(HMACSHA256.HashData(
            Encoding.UTF8.GetBytes(capability),
            Encoding.ASCII.GetBytes(Domain + nonce))).ToLowerInvariant();

    private sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> respond)
        : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken) => Task.FromResult(respond(request));
    }
}
