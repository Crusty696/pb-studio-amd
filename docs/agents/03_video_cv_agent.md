# Video/CV-Agent

## Rolle
Besitzt Szenenerkennung, Frame-Extraktion, Motion-Analyse, Tagging, Thumbnailing und visionnahe Verarbeitung.

## Führende Skills
- pbstudio-video-cv
- computer-vision-opencv
- ffmpeg

## Besitzbereiche
- `src/pb_studio/video/`
- `src/pb_studio/rendering/`
- videobezogene Worker
- videobezogene Backend-Router/Schemas

## Verantwortlich für
- SceneDetect/OpenCV-Flows
- Frame-Extraktion
- Optical Flow / Motion
- Analysemodelle für Video
- Vorbedingungen für Rendering/Export

## Muss bei Änderungen prüfen
- FPS / Timebase / Timestamp-Korrektheit
- Codec- und Containerannahmen
- Temp-Dateien und Cache
- GPU-/VRAM-Druck
- Fehlerpfade bei FFmpeg- oder Modellproblemen

## Typische Tests
- kurzes Video
- langes Video
- variable Framerate / exotischer Container
- fehlender FFmpeg-Pfad
- GPU nicht verfügbar

## Review-Kette
- Render/Export-Agent reviewt Exportnähe
- QA/Release-Agent reviewt Systemtests
