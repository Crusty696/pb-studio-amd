namespace PBStudio.UI.Services;

/// <summary>
/// Cross-VM Notification: Ein 4-Klick-Feedback wurde fuer einen Cut akzeptiert
/// (BrainViewModel.SendFeedbackAsync oder LearningSessionViewModel.RateAsync).
/// TimelineViewModel reagiert darauf, indem es die Confidence (BrainConfidence)
/// und den Tooltip-Cache (BrainExplain) fuer genau diesen Cut invalidiert
/// und neu nachlaedt.
///
/// Wird via WeakReferenceMessenger.Default.Send(...) verschickt.
/// </summary>
public sealed class BrainFeedbackAppliedMessage
{
    public int CutId { get; }

    public BrainFeedbackAppliedMessage(int cutId)
    {
        CutId = cutId;
    }
}
