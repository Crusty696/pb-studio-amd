# PBStudio.UI – C# WPF Frontend

Moderne WPF-basierte Desktop-Anwendung für PB Studio AMD.

## Architektur

### Struktur

- **App.xaml / App.xaml.cs**: Startup, DI-Container, Backend-Lifecycle
- **MainWindow.xaml / MainWindow.xaml.cs**: Root-Window mit Tab-Navigation
- **Services/**: HTTP-Kommunikation, SSE-Streaming, Projektverwaltung
- **ViewModels/**: MVVM mit CommunityToolkit.Mvvm
- **Views/**: XAML-UI mit Material Design 3

### Services

| Service | Aufgabe |
|---------|---------|
| **PythonBridgeService** | Startet/Stoppt Python Backend (server.py) |
| **ApiClient** | REST-Kommunikation mit Python Backend (Port 8765) |
| **SSEClient** | Server-Sent Events für Echtzeit-Updates |
| **NavigationService** | Tab-Navigation und Dialog-Steuerung |
| **ProjectService** | Projekt-Lifecycle (Create/Load/Save) |

### ViewModels

- **MainViewModel**: Zentrale Koordination, Backend-Status, GPU-Monitoring
- **MediaIngestViewModel**: Audio/Video-Import
- **AudioLibraryViewModel**: Audio-Analyse und -Verwaltung
- **VideoLibraryViewModel**: Video-Analyse und -Verwaltung
- **AnchorViewModel**: Synchronisationspunkte
- **DirectorViewModel**: KI-gesteuerte Automatisierung
- **TimelineViewModel**: Timeline-Editor
- **ProductionViewModel**: Rendering und Export
- **SettingsViewModel**: Anwendungseinstellungen

## Requirements

- **.NET 9.0** SDK (oder höher)
- **Visual Studio 2022+** oder **JetBrains Rider**
- Python Backend aktiv (PB Studio Python FastAPI)

## Setup

```powershell
# Clone & Restore
cd PBStudio.UI
dotnet restore

# Build
dotnet build

# Run
dotnet run
```

## Kommunikation mit Backend

### HTTP/REST
```csharp
// Services/ApiClient.cs
var result = await _apiClient.PostAsync<ImportResult>("/api/media/import", payload);
```

### Server-Sent Events (SSE)
```csharp
// Echtzeit-Updates (GPU-Status, Progress, Errors)
await _sseClient.StartStreamingAsync("/api/events");
```

## Styling

- **Material Design 3** (MaterialDesignThemes.Wpf)
- **Material Icons** (MahApps.Metro.IconPacks.Material)
- **Dark Theme** mit DeepPurple Primary + Lime Secondary

## NuGet Dependencies

```xml
CommunityToolkit.Mvvm (8.4.0)
MaterialDesignThemes (5.1.0)
MahApps.Metro.IconPacks.Material (5.0.0)
Microsoft.Xaml.Behaviors.Wpf (1.1.135)
Microsoft.Extensions.DependencyInjection (9.0.0)
Microsoft.Extensions.Logging (9.0.0)
```

## Entwicklung

### Code-Style
- **XAML**: Minimal Code-Behind, Logik im ViewModel
- **ViewModels**: Nutze `[ObservableProperty]` und `[RelayCommand]`
- **Services**: Dependency Injection via Constructor

### Debugging
- Visual Studio: F5 zum Starten
- Konsole-Logs der Python Backend erscheinen in Ausgabe-Fenster
- SSE-Events sind im MainViewModel sichtbar

## Lizenz & Autor

PB Studio AMD | 2026
