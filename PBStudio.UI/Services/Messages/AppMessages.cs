namespace PBStudio.UI.Services.Messages;

// Audit F4: Strongly-typed Messages fuer WeakReferenceMessenger statt string-keys.
// Jeder record ist eine reine Notification ohne Payload. Vorher wurden alle
// Notifications via ValueChangedMessage<string>("audio-imported"), etc. verschickt
// — Typo-Risiko + kein IDE-Autocomplete + kein Compile-Time-Check.
//
// BrainFeedbackAppliedMessage existiert separat in ../BrainFeedbackAppliedMessage.cs
// (mit CutId payload) und ist bereits typed.

// Audio-Library
public sealed record AudioImportedMessage;
public sealed record AudioLibraryRefreshMessage;

// Video-Library
public sealed record VideoImportedMessage;
public sealed record VideoLibraryRefreshMessage;

// Media-Library (sammel-refresh — Audio + Video Aenderungen kombiniert)
public sealed record MediaLibraryRefreshMessage;

// Project Lifecycle
public sealed record ProjectOpenedMessage;
public sealed record ProjectClosingMessage;
public sealed record ProjectClosedMessage;

// App Lifecycle
public sealed record AppShutdownMessage;
public sealed record BackendReadyMessage;

// Timeline / Director
public sealed record TimelineRefreshMessage;
public sealed record NavigateDirectorMessage;

// AI / Model-Manager Mode Sync
public sealed record KiModeChangedMessage;
