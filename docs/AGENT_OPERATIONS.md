# PB Studio AMD – Agent Operations

Stand: 2026-03-09

## Ziel
Dieses Dokument definiert, welcher Spezialagent in welchem Bereich führt.

## Architektur-Prämisse
PB Studio AMD wird als **native Windows-Hybrid-App** geführt:
- **C#/.NET (`PBStudio.UI/`)** ist das führende Produkt-Frontend
- **Python (`backend/`, `src/pb_studio/`)** ist Backend-, Engine- und GPU-nahe Verarbeitungsschicht
- **PyQt (`src/pb_studio/ui/`)** ist aktuell Legacy-, Dev- oder Fallback-UI und nicht die primäre Produktoberfläche

## Führungsregel
Bei jeder Aufgabe zuerst festlegen:
1. welcher Bereich primär betroffen ist,
2. welcher Agent führt,
3. welche Agenten reviewen,
4. welche Tests Pflicht sind.

## Standard-Zuordnung nach Bereich
- Architekturfragen → Architektur-Agent
- Audioanalyse / Stem Separation / Audio-Features → Audio/ML-Agent
- Szenenerkennung / Frames / Vision / Motion → Video/CV-Agent
- Router / Schemas / API / SSE → Backend/API-Agent
- C#/.NET UI / WPF / UX / ViewModels / Desktop-Workflows → Desktop-UI-Agent
- PyQt6-Legacy-/Fallback-Fragen → Desktop-UI-Agent + Architektur-Agent
- SQLite / Restore / Repository / Vector Store → Daten-Agent
- Export / Rendering / FFmpeg / AMF → Render/Export-Agent
- Tests / Verify / Release-Freigabe → QA/Release-Agent

## Review-Matrix
- Architekturänderung → Architektur-Agent + betroffener Domänenagent + QA
- C#-UI-Änderung → Desktop-UI-Agent + Architektur-Agent
- PyQt-Legacy-Änderung → Desktop-UI-Agent + Architektur-Agent, mit Prüfung ob dieselbe Logik ins C#-Frontend gehört
- Backend-Vertragsänderung → Backend/API-Agent + Desktop-UI-Agent + QA
- Audio-Pipeline → Audio/ML-Agent + Architektur-Agent + QA
- Video-/Render-Pipeline → Video/CV-Agent + Render/Export-Agent + QA
- Datenmodelländerung → Daten-Agent + Backend/API-Agent + QA

## Pflicht-Testpfade je Änderung
- kleine UI-Änderung:
  - Starttest
  - betroffener Widget-/Workflowtest
- Backend-Änderung:
  - Routertest
  - Schema-/Fehlerfalltest
- Audio-Änderung:
  - kurze Datei
  - fehlerhafte Datei
  - Langlauf-/Abbruchpfad
- Video-Änderung:
  - kurzes Video
  - FFmpeg-/Fallbackpfad
- Daten-Änderung:
  - Save/Load
  - Restore nach Neustart
- Export-Änderung:
  - Preview + Final Export
  - Fehlerpfad bei ungültigen Einstellungen

## Empfohlene erste Arbeitsreihenfolge im Projekt
1. Architektur-Agent erstellt Sollbild
2. Backend/API-Agent kartiert reale Verträge
3. Desktop-UI-Agent kartiert reale Start- und Bedienpfade
4. Audio/ML-Agent prüft Audio-Stack
5. Video/CV-Agent prüft Video-Stack
6. Daten-Agent prüft Persistenz/Restore
7. Render/Export-Agent prüft Exportpfad
8. QA/Release-Agent definiert die verlässliche Minimal-Freigabe
