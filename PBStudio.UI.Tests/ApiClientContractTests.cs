using System.IO;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Services;

namespace PBStudio.UI.Tests;

[TestClass]
public sealed class ApiClientContractTests
{
    [TestMethod]
    public async Task ClearChatHistory_NonSuccessStatusReturnsFalse()
    {
        using var client = CreateClient(
            (_, _) => Task.FromResult(new HttpResponseMessage(
                HttpStatusCode.InternalServerError)));

        var result = await client.ClearChatHistoryAsync();

        Assert.IsFalse(result);
    }

    [TestMethod]
    public async Task ClearChatHistory_SuccessStatusReturnsTrue()
    {
        using var client = CreateClient(
            (_, _) => Task.FromResult(new HttpResponseMessage(
                HttpStatusCode.NoContent)));

        var result = await client.ClearChatHistoryAsync();

        Assert.IsTrue(result);
    }

    [TestMethod]
    public async Task CleanupGpu_DeserializesTypedNegativeResult()
    {
        using var client = CreateClient(
            (_, _) => JsonResponse(
                """{"success":false,"freed_mb":0,"error":"models active"}"""));

        var result = await client.CleanupGpuAsync();

        Assert.IsNotNull(result);
        Assert.IsFalse(result.Success);
        Assert.AreEqual(0, result.FreedMb);
        Assert.AreEqual("models active", result.Error);
    }

    [TestMethod]
    public async Task TimelinePreview_ForwardsCancellationToHttpRequest()
    {
        var requestStarted = new TaskCompletionSource(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var handlerSawCancellation = new TaskCompletionSource(
            TaskCreationOptions.RunContinuationsAsynchronously);
        using var client = CreateClient(async (_, cancellationToken) =>
        {
            requestStarted.SetResult();
            try
            {
                await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
                throw new AssertFailedException("Request hätte abgebrochen werden müssen.");
            }
            catch (OperationCanceledException)
            {
                handlerSawCancellation.SetResult();
                throw;
            }
        });
        using var cancellation = new CancellationTokenSource();

        var previewTask = client.GenerateTimelinePreviewAsync(
            1.0,
            2.0,
            cancellation.Token);
        await requestStarted.Task.WaitAsync(TimeSpan.FromSeconds(2));
        cancellation.Cancel();
        var result = await previewTask;
        await handlerSawCancellation.Task.WaitAsync(TimeSpan.FromSeconds(2));

        Assert.IsNull(result);
    }

    [TestMethod]
    public async Task BrainFeedback_RetryIdIsStableOnlyWithinSameProject()
    {
        var operationIds = new List<Guid>();
        using var client = CreateClient(async (request, cancellationToken) =>
        {
            if (request.RequestUri?.AbsolutePath == "/project/open")
            {
                var requestJson = await request.Content!.ReadAsStringAsync(cancellationToken);
                using var requestBody = JsonDocument.Parse(requestJson);
                var path = requestBody.RootElement.GetProperty("path").GetString()!;
                var responseJson = JsonSerializer.Serialize(new
                {
                    name = Path.GetFileName(path),
                    path,
                    audio_count = 0,
                    video_count = 0,
                    has_timeline = false,
                });
                return await JsonResponse(responseJson);
            }

            var feedbackJson = await request.Content!.ReadAsStringAsync(cancellationToken);
            using var feedbackBody = JsonDocument.Parse(feedbackJson);
            operationIds.Add(feedbackBody.RootElement.GetProperty("operation_id").GetGuid());
            return new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
        });

        await client.OpenProjectAsync(@"C:\Projects\A");
        await client.BrainFeedbackAsync(17, "perfect");
        await client.BrainFeedbackAsync(17, "perfect");

        await client.OpenProjectAsync(@"C:\Projects\B");
        await client.BrainFeedbackAsync(17, "perfect");

        Assert.AreEqual(3, operationIds.Count);
        Assert.AreEqual(operationIds[0], operationIds[1]);
        Assert.AreNotEqual(operationIds[0], operationIds[2]);
    }

    private static ApiClient CreateClient(
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> responder)
    {
        var http = new HttpClient(new StubHttpMessageHandler(responder))
        {
            BaseAddress = new Uri("http://127.0.0.1:8765"),
        };
        return new ApiClient(http, NullLogger<ApiClient>.Instance);
    }

    private static Task<HttpResponseMessage> JsonResponse(string json) =>
        Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(
                json,
                Encoding.UTF8,
                "application/json"),
        });

    private sealed class StubHttpMessageHandler(
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> responder)
        : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken) =>
            responder(request, cancellationToken);
    }
}
