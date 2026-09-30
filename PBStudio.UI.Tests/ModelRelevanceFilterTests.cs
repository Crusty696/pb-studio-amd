using System.Collections.Generic;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using PBStudio.UI.Models;
using PBStudio.UI.ViewModels;

namespace PBStudio.UI.Tests;

// Installed-model entries as reported live on 2026-09-30 (28 models, most unusable here).
[TestClass]
public sealed class ModelRelevanceFilterTests
{
    private static ModelListEntry E(string name, double gb, string? arch, bool vision, params string[] caps)
        => new(name, SizeGb: gb, Architecture: arch, Vision: vision, Capabilities: new List<string>(caps));

    [TestMethod]
    public void VisionAndToolModelsStayVisible()
    {
        Assert.IsTrue(ModelManagerViewModel.IsAppRelevant(E("qwen2.5-vl-7b-instruct", 6.0, "qwen2vl", true, "chat", "vision")));
        Assert.IsTrue(ModelManagerViewModel.IsAppRelevant(E("qwen3.5:latest", 6.6, null, true, "chat", "tool_calls", "vision")));
        Assert.IsTrue(ModelManagerViewModel.IsAppRelevant(E("ornith-coderx", 14, null, false, "chat", "tool_calls")));
    }

    [TestMethod]
    public void UnsuitableModelsAreHidden()
    {
        Assert.IsFalse(ModelManagerViewModel.IsAppRelevant(E("ltx-2.5", 11.8, "ltxv", false, "chat")));
        Assert.IsFalse(ModelManagerViewModel.IsAppRelevant(E("ltx-2.3-uncensored-v1.4", 6.8, "gemma3", false, "chat")));
        Assert.IsFalse(ModelManagerViewModel.IsAppRelevant(E("qwen2-audio-7b", 4.3, "qwen2", false, "chat")));
        Assert.IsFalse(ModelManagerViewModel.IsAppRelevant(E("qwen3.8-27b-uncensored-vision", 0.9, "clip", false, "chat")));
        Assert.IsFalse(ModelManagerViewModel.IsAppRelevant(E("text-embedding-nomic", 0.1, "nomic-bert", false, "embedding")));
        Assert.IsFalse(ModelManagerViewModel.IsAppRelevant(E("qwen3.5-moe-0.87b-d0.8b", 0.9, "qwen35moe", false, "chat")));
        Assert.IsFalse(ModelManagerViewModel.IsAppRelevant(E("granite-4.0-h-tiny", 3.9, "granitehybrid", false, "chat")));
    }

    [TestMethod]
    public void ModelAssignedToATaskIsNeverHidden()
    {
        var m = E("granite-4.0-h-tiny", 3.9, "granitehybrid", false, "chat") with { ActiveTasks = new List<string> { "Chat" } };
        Assert.IsTrue(ModelManagerViewModel.IsAppRelevant(m));
    }
}
