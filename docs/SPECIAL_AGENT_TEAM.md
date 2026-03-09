# PB Studio AMD – Spezial-Agenten-Team

Stand: 2026-03-09

Dieses Team ist auf die aktuelle Projektstruktur zugeschnitten.

## Zielbild
PB Studio AMD wird als **C#-/Python-Hybrid-App** gedacht:
- **Frontend:** `PBStudio.UI/` in C#/.NET als native Windows-Desktop-Oberfläche
- **Backend/Engine:** Python (`backend/`, `src/pb_studio/`) für Audio, Video, AI, Rendering und AMD-nahe Verarbeitung
- **PyQt:** `src/pb_studio/ui/` ist derzeit Legacy-, Dev- oder Fallback-UI, aber nicht das langfristige Produkt-Frontend

## Installierte externe Skills
- `fastapi`
- `pytest`
- `computer-vision-opencv`
- `pyside6-mvc`
- `ui-ux-designer`

## Eigene projektspezifische Skills
- `pbstudio-architecture-guard`
- `pbstudio-audio-ml`
- `pbstudio-video-cv`
- `pbstudio-fastapi-contracts`
- `pbstudio-desktop-ui`
- `pbstudio-data-persistence`
- `pbstudio-render-pipeline`
- `pbstudio-qa-release`

## Spezialagenten nach Bereich

### 1. Architektur-Agent
**Skills:** `pbstudio-architecture-guard`, `python-design-patterns`, `fastapi`
**Zuständig für:** Schichten, Verantwortlichkeiten und das Zielbild **C#-Frontend + Python-Engine**, inklusive Drift zwischen Legacy-PyQt, C# und FastAPI.

### 2. Audio/ML-Agent
**Skills:** `pbstudio-audio-ml`, `python-pro`, `machine-learning`
**Zuständig für:** Beat Detection, Stem Separation, Audio-Features, AMD-sichere Modellintegration.

### 3. Video/CV-Agent
**Skills:** `pbstudio-video-cv`, `computer-vision-opencv`, `ffmpeg`
**Zuständig für:** Szenenerkennung, Frames, Optical Flow, Thumbnails, Videoanalyse.

### 4. Backend/API-Agent
**Skills:** `pbstudio-fastapi-contracts`, `fastapi`, `python-pro`
**Zuständig für:** Router, Schemas, SSE/Events, lokale API-Verträge.

### 5. Desktop-UI-Agent
**Skills:** `pbstudio-desktop-ui`, `pyside6-mvc`, `ui-ux-designer`
**Zuständig für:** das native C#-Frontend, klare UI-Grenzen zur Python-Engine und den kontrollierten Umgang mit Legacy-/Dev-PyQt.

### 6. Daten-Agent
**Skills:** `pbstudio-data-persistence`, `SQLite Database Expert`, `memory`
**Zuständig für:** SQLite, Repositories, State-Restore, Vektorspeicher.

### 7. Render/Export-Agent
**Skills:** `pbstudio-render-pipeline`, `ffmpeg`, `media-processing`
**Zuständig für:** FFmpeg/AMF, Export, Concat, Recovery bei langen Jobs.

### 8. QA/Release-Agent
**Skills:** `pbstudio-qa-release`, `pytest`, `test-gap-analyzer`
**Zuständig für:** Smoke-Tests, Integrationspfade, GPU-sensitive Tests, Release-Checks.

## Einsatzregel
Vor jeder größeren Änderung zuerst klären:
1. welcher Bereich betroffen ist,
2. welcher Spezialagent führt,
3. welche anderen Agenten reviewen müssen.

## Priorisierte Reihenfolge für die nächsten Schritte
1. Architektur-Agent
2. Backend/API-Agent
3. Desktop-UI-Agent
4. Audio/ML-Agent
5. Video/CV-Agent
6. Daten-Agent
7. Render/Export-Agent
8. QA/Release-Agent
