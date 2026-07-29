# PBStudio.UI – Projektstruktur

```
PBStudio.UI/
├── PBStudio.UI.csproj              # Projekt-Definition (.NET 9.0, WPF)
├── App.xaml                         # XAML Application Root
├── App.xaml.cs                      # DI-Setup, Backend-Lifecycle
├── MainWindow.xaml                  # Haupt-UI mit Tab-Navigation
├── MainWindow.xaml.cs               # Code-Behind (minimal)
│
├── Services/                        # Kommunikation & Geschäftslogik
│   ├── PythonBridgeService.cs       # Backend-Prozess-Verwaltung
│   ├── ApiClient.cs                 # HTTP/REST Client
│   ├── SSEClient.cs                 # Server-Sent Events Listener
│   ├── NavigationService.cs         # Tab-Navigation
│   └── ProjectService.cs            # Projekt-Lifecycle
│
├── ViewModels/                      # MVVM (CommunityToolkit.Mvvm)
│   ├── MainViewModel.cs             # Root-ViewModel
│   ├── MediaIngestViewModel.cs      # Import-Dialog
│   ├── AudioLibraryViewModel.cs     # Audio-Tab
│   ├── VideoLibraryViewModel.cs     # Video-Tab
│   ├── AnchorViewModel.cs           # Ankerpunkte-Tab
│   ├── DirectorViewModel.cs         # KI-Automation-Tab
│   ├── TimelineViewModel.cs         # Timeline-Tab
│   ├── ProductionViewModel.cs       # Rendering-Tab
│   ├── SettingsViewModel.cs         # Einstellungen-Tab
│   ├── ModelManagerViewModel.cs     # Modelle-Tab
│   ├── BrainViewModel.cs            # Brain-Tab
│   ├── ChatViewModel.cs             # Chat-Tab
│   └── TerminalViewModel.cs         # Terminal-Tab
│
├── Views/                           # XAML User Controls (Material Design)
│   ├── MediaIngestView.xaml         # Import-Interface
│   ├── MediaIngestView.xaml.cs
│   ├── AudioLibraryView.xaml        # Audio-Bibliothek
│   ├── AudioLibraryView.xaml.cs
│   ├── VideoLibraryView.xaml        # Video-Bibliothek
│   ├── VideoLibraryView.xaml.cs
│   ├── AnchorView.xaml              # Anker-Verwaltung
│   ├── AnchorView.xaml.cs
│   ├── DirectorView.xaml            # Director-Engine
│   ├── DirectorView.xaml.cs
│   ├── TimelineView.xaml            # Timeline-Editor
│   ├── TimelineView.xaml.cs
│   ├── ProductionView.xaml          # Produktion & Export
│   ├── ProductionView.xaml.cs
│   ├── SettingsView.xaml            # Einstellungen
│   └── SettingsView.xaml.cs
│
├── Models/                          # Daten-Klassen
│   └── Audio/Video/Timeline/Brain/Model-/Chat-DTOs
│
├── Converters/                      # XAML Wert-Konverter
│   └── Visibility, Status, Confidence, Waveform und Timeline
│
├── Properties/                      # .NET Metadaten
│   └── (generiert)
│
├── Resources/                       # Icons, Assets
│   └── app.ico
│
├── .gitignore                       # Git-Ausschlüsse
├── README.md                        # Übersicht & Setup
└── STRUCTURE.md                     # Diese Datei
```

## DI-Container (App.xaml.cs)

```
Services (Singleton für Desktop-App):
- PythonBridgeService    → Backend-Lifecycle
- ApiClient              → REST-Client
- SSEClient              → Event-Stream
- NavigationService      → Tab-Navigation
- ProjectService         → Projekt-Management

ViewModels (Transient):
- MainViewModel
- MediaIngestViewModel
- AudioLibraryViewModel
- VideoLibraryViewModel
- AnchorViewModel
- DirectorViewModel
- TimelineViewModel
- ProductionViewModel
- SettingsViewModel

Windows (Transient):
- MainWindow
```

## Event-Flow

```
MainWindow
  └─ MainViewModel
      ├─ PythonBridgeService.StartAsync()
      │   └─ Startet kanonisches Python 3.11 + uvicorn auf 127.0.0.1:8765
      │
      ├─ SSEClient.StartAsync()
      │   └─ Hört auf /events/progress, /events/log und /events/gpu
      │       ├─ GPU-Status
      │       ├─ Progress
      │       ├─ Errors
      │       └─ Status-Changes
      │
      ├─ TabControl (SelectedTabIndex)
      │   ├─ MediaIngestView
      │   ├─ AudioLibraryView
      │   ├─ VideoLibraryView
      │   ├─ AnchorView
      │   ├─ DirectorView
      │   ├─ TimelineView
      │   ├─ ProductionView
      │   └─ SettingsView
      │
      └─ StatusBar
          ├─ StatusMessage
          ├─ GlobalProgress
          └─ BackendStatus
```

## Tech Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| .NET SDK | 9.0+ | Windows Zielplattform |
| WPF | .NET 9.0 | Desktop-UI-Framework |
| CommunityToolkit.Mvvm | 8.4.0 | MVVM Patterns |
| MaterialDesignThemes | 5.1.0 | Material Design 3 UI |
| MahApps.Metro.IconPacks | 5.0.0 | Material-Icons |
| Microsoft.Xaml.Behaviors | 1.1.135 | Event-to-Command |
| Microsoft.Extensions.* | 9.0.0 | DI, Logging, HTTP |

## Verifikation

Die verbindlichen Release-Gates stehen im aktiven Spec-Workspace
`specs/00013-system-wide-bug-hunting-audit/`. Ein erfolgreicher Build allein
belegt weder Backend-Laufzeit noch GUI- oder E2E-Funktion.
