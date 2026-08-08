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
| **PythonBridgeService** | Startet/stoppt Python 3.11 + `uvicorn backend.main:app` auf `127.0.0.1:8765` mit Owner-Capability |
| **ApiClient** | REST-Kommunikation mit Python Backend (Port 8765) |
| **SSEClient** | Server-Sent Events für Echtzeit-Updates |
| **NavigationService** | Tab-Navigation und Dialog-Steuerung |
| **ProjectService** | Projekt-Lifecycle (Create/Load/Save) |

### ViewModels

- **MainViewModel** koordiniert Navigation und globalen Status.
- Die zwölf Produktbereiche werden durch Projekt, Import, Audio, Video,
  Anker, Director, Timeline, Produktion, Modelle, Brain, Chat und Terminal
  abgedeckt; Settings und VRAM-Telemetrie ergänzen die Laufzeitsteuerung.

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

`Services/ApiClient.cs` kapselt die typisierten Backend-Aufrufe. Destruktive
Loopback-Aufrufe wie Brain-Reset und Shutdown tragen zusätzlich die private
Owner-Capability.

### Server-Sent Events (SSE)

`SSEClient` konsumiert `/events/progress`, `/events/log` und `/events/gpu`
parallel und verteilt die typisierten Ereignisse an die ViewModels.

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
