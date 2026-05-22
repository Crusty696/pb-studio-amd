namespace PBStudio.UI.Models;

/// <summary>Einfaches Modell für einen Wellenform-Balken in der Timeline.</summary>
public class WaveformBarModel
{
    public double X { get; set; }      // Zeit in Sekunden (wird vom Converter in Pixel gewandelt)
    public double Y { get; set; }      // Vertikale Position im Canvas
    public double Width { get; set; }  // Breite in Sekunden
    public double Height { get; set; } // Höhe in Pixel
}
