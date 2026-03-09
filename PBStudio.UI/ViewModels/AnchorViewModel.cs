using System.Collections.ObjectModel;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using PBStudio.UI.Services;

namespace PBStudio.UI.ViewModels;

/// <summary>ViewModel für die Anchor-Bearbeitung (Beat-Marker + Video-Zuordnung).</summary>
public partial class AnchorViewModel : ObservableObject
{
    private readonly IApiClient _api;

    [ObservableProperty] private string _statusText = "Anchors werden hier definiert";
    [ObservableProperty] private double _currentPosition;
    [ObservableProperty] private AnchorPoint? _selectedAnchor;

    public ObservableCollection<AnchorPoint> Anchors { get; } = [];

    public AnchorViewModel(IApiClient api)
    {
        _api = api;
    }

    [RelayCommand]
    private void AddAnchor()
    {
        Anchors.Add(new AnchorPoint
        {
            Time = CurrentPosition,
            Label = $"Anchor {Anchors.Count + 1}",
        });
        StatusText = $"Anchor bei {CurrentPosition:F2}s hinzugefügt";
    }

    [RelayCommand]
    private void RemoveAnchor(AnchorPoint? anchor)
    {
        if (anchor != null)
        {
            Anchors.Remove(anchor);
            StatusText = "Anchor entfernt";
        }
    }
}

public class AnchorPoint
{
    public double Time { get; set; }
    public string Label { get; set; } = "";
    public int? VideoClipId { get; set; }
    public string TimeText => TimeSpan.FromSeconds(Time).ToString(@"mm\:ss\.ff");
}
