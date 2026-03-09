namespace PBStudio.UI.Models;

/// <summary>Render-Konfiguration für UI-Darstellung.</summary>
public class RenderConfigModel
{
    public string OutputPath { get; set; } = "";
    public string AudioPath { get; set; } = "";
    public string Quality { get; set; } = "high";
    public string? Encoder { get; set; }
    public int Width { get; set; } = 1920;
    public int Height { get; set; } = 1080;
    public double Fps { get; set; } = 30.0;
    public double BitrateMbps { get; set; } = 12.0;
    public bool IncludeAudio { get; set; } = true;
}
