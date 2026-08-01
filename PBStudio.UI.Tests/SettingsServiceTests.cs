using System.IO;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Services;

namespace PBStudio.UI.Tests;

[TestClass]
[DoNotParallelize]
public sealed class SettingsServiceTests
{
    [TestMethod]
    public void Load_MissingFileIsSuccessfulFirstStart()
    {
        using var temp = new TemporaryDirectory();
        var service = new SettingsService(
            System.IO.Path.Combine(temp.Path, "settings.json"));

        var result = service.Load();

        Assert.IsTrue(result.Succeeded);
        Assert.IsFalse(result.LoadedFromDisk);
        Assert.AreEqual(SettingsPersistenceFailure.None, result.Failure);
        Assert.AreEqual(8192, service.Current.VramCapMb);
    }

    [TestMethod]
    public void Load_MalformedJsonReturnsTypedFailureAndDefaults()
    {
        using var temp = new TemporaryDirectory();
        var settingsPath = System.IO.Path.Combine(temp.Path, "settings.json");
        File.WriteAllText(settingsPath, """{"vram_cap_mb":""");
        var service = new SettingsService(settingsPath);

        var result = service.Load();

        Assert.IsFalse(result.Succeeded);
        Assert.AreEqual(SettingsPersistenceFailure.MalformedJson, result.Failure);
        Assert.IsFalse(string.IsNullOrWhiteSpace(result.ErrorMessage));
        Assert.AreEqual(8192, service.Current.VramCapMb);
    }

    [TestMethod]
    public void Save_AtomicallyPersistsAndVerifiesCurrentSettings()
    {
        using var temp = new TemporaryDirectory();
        var settingsPath = System.IO.Path.Combine(temp.Path, "settings.json");
        var service = new SettingsService(settingsPath);
        service.Current.FfmpegPath = @"C:\PBStudio\ffmpeg.exe";
        service.Current.VramCapMb = 12288;
        service.Current.ForcedVramMb = 8192;
        service.Current.KiMode = "quality";

        var save = service.Save();
        var reloaded = new SettingsService(settingsPath);
        var load = reloaded.Load();

        Assert.IsTrue(save.Succeeded);
        Assert.AreEqual(SettingsPersistenceFailure.None, save.Failure);
        Assert.IsTrue(load.Succeeded);
        Assert.IsTrue(load.LoadedFromDisk);
        Assert.AreEqual(@"C:\PBStudio\ffmpeg.exe", reloaded.Current.FfmpegPath);
        Assert.AreEqual(12288, reloaded.Current.VramCapMb);
        Assert.AreEqual(8192, reloaded.Current.ForcedVramMb);
        Assert.AreEqual("quality", reloaded.Current.KiMode);
        Assert.AreEqual(0, Directory.GetFiles(temp.Path, "*.tmp").Length);
    }

    [TestMethod]
    public void Save_WhenParentIsAFileReturnsWriteFailureWithoutFalseSuccess()
    {
        using var temp = new TemporaryDirectory();
        var blockingPath = System.IO.Path.Combine(temp.Path, "not-a-directory");
        File.WriteAllText(blockingPath, "block");
        var service = new SettingsService(
            System.IO.Path.Combine(blockingPath, "settings.json"));

        var result = service.Save();

        Assert.IsFalse(result.Succeeded);
        Assert.AreEqual(SettingsPersistenceFailure.WriteFailed, result.Failure);
        Assert.IsFalse(string.IsNullOrWhiteSpace(result.ErrorMessage));
    }
}
