using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Services;
using System.IO;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class BackendEndpointOptionsTests
{
    [TestMethod]
    public void Load_AcceptsCanonicalLoopbackContract()
    {
        var options = LoadJson("""
            {"Backend":{"Scheme":"http","Host":"127.0.0.1","Port":43127}}
            """);

        Assert.AreEqual("http://127.0.0.1:43127", options.DisplayValue);
    }

    [TestMethod]
    [DataRow("{\"Backend\":{\"Scheme\":\"https\",\"Host\":\"127.0.0.1\",\"Port\":8765}}")]
    [DataRow("{\"Backend\":{\"Scheme\":\"http\",\"Host\":\"192.168.1.2\",\"Port\":8765}}")]
    [DataRow("{\"Backend\":{\"Scheme\":\"http\",\"Host\":\"127.0.0.1\",\"Port\":0}}")]
    [DataRow("{\"Backend\":{\"Scheme\":\"http\",\"Host\":\"127.0.0.1\",\"Port\":8765,\"Path\":\"/api\"}}")]
    [DataRow("{\"Backend\":{\"Scheme\":\"http\",\"Host\":\"127.0.0.1\",\"Port\":8765},\"Other\":true}")]
    [DataRow("{\"Backend\":{\"Scheme\":\"HTTP\",\"Host\":\"127.0.0.1\",\"Port\":8765}}")]
    [DataRow("{\"Backend\":{\"Scheme\":\"http\",\"Host\":\" localhost\",\"Port\":8765}}")]
    public void Load_RejectsInvalidOrAmbiguousContracts(string json)
    {
        Assert.ThrowsExactly<InvalidDataException>(() => LoadJson(json));
    }

    [TestMethod]
    public void Load_AppliesSharedHostAndPortEnvironmentOverrides()
    {
        using var host = new EnvironmentVariableScope("PBSTUDIO_HOST", "localhost");
        using var port = new EnvironmentVariableScope("PBSTUDIO_PORT", "43127");

        var options = LoadJson("""
            {"Backend":{"Scheme":"http","Host":"127.0.0.1","Port":8765}}
            """);

        Assert.AreEqual("http://localhost:43127", options.DisplayValue);
    }

    private static BackendEndpointOptions LoadJson(string json)
    {
        var path = Path.Combine(Path.GetTempPath(), $"pbstudio-endpoint-{Guid.NewGuid():N}.json");
        try
        {
            File.WriteAllText(path, json);
            return BackendEndpointOptions.Load(path);
        }
        finally
        {
            File.Delete(path);
        }
    }
}
