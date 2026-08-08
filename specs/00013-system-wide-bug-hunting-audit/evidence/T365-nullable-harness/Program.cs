using System.Net;
using System.Diagnostics.CodeAnalysis;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging.Abstractions;
using PBStudio.UI.Services;

if (args.Length != 1)
{
    Console.Error.WriteLine("Usage: T365.NullableHarness <evidence-json-path>");
    return 2;
}

const string responseJson = """
{
  "clip_id": 42,
  "scene_count": 1,
  "avg_motion": 0.0,
  "dominant_colors": [],
  "tags": [],
  "has_embedding": false,
  "embedding_dim": 0,
  "scenes": [
    {
      "start_time": 0.0,
      "end_time": 1.5,
      "scene_type": "cut",
      "confidence": null
    }
  ],
  "status": "completed",
  "stage_status": {},
  "stage_errors": {}
}
""";

var handler = new RecordingHandler(responseJson);
using var http = new HttpClient(handler)
{
    BaseAddress = new Uri("http://127.0.0.1:8765"),
};
using var client = new ApiClient(http, NullLogger<ApiClient>.Instance);

var result = await client.AnalyzeVideoAsync(42);
Require(result is not null, "AnalyzeVideoAsync returned null");
Require(result.ClipId == 42, $"Unexpected clip_id: {result.ClipId}");
Require(result.Scenes is { Count: 1 }, "Expected exactly one scene");
Require(result.Scenes[0].Confidence is null, "confidence=null was not preserved");
Require(handler.RequestCount == 1, $"Expected exactly one HTTP request, got {handler.RequestCount}");
Require(handler.LastMethod == HttpMethod.Post, $"Expected POST, got {handler.LastMethod}");
Require(handler.LastPath == "/video/analyze", $"Unexpected request path: {handler.LastPath}");

using var requestBody = JsonDocument.Parse(handler.LastBody ?? "{}");
Require(
    requestBody.RootElement.TryGetProperty("clip_id", out var clipId)
    && clipId.GetInt32() == 42,
    "Request body did not contain clip_id=42");

var evidence = new
{
    status = "PASS",
    tested_at = DateTimeOffset.Now,
    runtime = Environment.Version.ToString(),
    request_count = handler.RequestCount,
    request_method = handler.LastMethod?.Method,
    request_path = handler.LastPath,
    request_clip_id = clipId.GetInt32(),
    response_clip_id = result.ClipId,
    scene_count = result.Scenes.Count,
    confidence_is_null = result.Scenes[0].Confidence is null,
    retry_storm_absent = handler.RequestCount == 1,
};

var outputPath = Path.GetFullPath(args[0]);
Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
await File.WriteAllTextAsync(
    outputPath,
    JsonSerializer.Serialize(evidence, new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine,
    new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

Console.WriteLine(JsonSerializer.Serialize(evidence));
return 0;

static void Require([DoesNotReturnIf(false)] bool condition, string message)
{
    if (!condition)
    {
        throw new InvalidOperationException(message);
    }
}

sealed class RecordingHandler(string responseJson) : HttpMessageHandler
{
    public int RequestCount { get; private set; }
    public HttpMethod? LastMethod { get; private set; }
    public string? LastPath { get; private set; }
    public string? LastBody { get; private set; }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        RequestCount++;
        LastMethod = request.Method;
        LastPath = request.RequestUri?.AbsolutePath;
        LastBody = request.Content is null
            ? null
            : await request.Content.ReadAsStringAsync(cancellationToken);

        return new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(responseJson, Encoding.UTF8, "application/json"),
            RequestMessage = request,
        };
    }
}
