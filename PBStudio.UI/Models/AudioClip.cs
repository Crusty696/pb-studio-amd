namespace PBStudio.UI.Models;

/// <summary>Audio-Clip Model für die UI-Darstellung.</summary>
public class AudioClipModel
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Path { get; set; } = "";
    public double DurationSeconds { get; set; }
    public int SampleRate { get; set; } = 44100;
    public int Channels { get; set; } = 2;
    public string Format { get; set; } = "mp3";
    public double Bpm { get; set; }
    public string Key { get; set; } = "";
    public int BeatCount { get; set; }
    public bool IsAnalyzed { get; set; }
    public string DurationText => TimeSpan.FromSeconds(DurationSeconds).ToString(@"mm\:ss");
}
