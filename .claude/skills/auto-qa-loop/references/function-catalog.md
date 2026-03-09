# Funktionskatalog-Template für PB Studio

Dieses Template wird in Phase 1 ausgefüllt. Lies den tatsächlichen Quellcode um die Funktionen zu identifizieren.

## Testdaten

| Typ | Pfad | Hinweis |
|-----|------|---------|
| Audio | `C:\Users\david\Videos\test_data\audio` | Nur diese Dateien verwenden |
| Video | `C:\Users\david\Videos\test_data\video` | Nur diese Dateien verwenden |

## Bereich 1: Projekt-Management

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-1.1 | Neues Projekt erstellen | MainViewModel → NewProjectCommand | POST /api/project/create | Projekt-Ordner erstellt, DB initialisiert |
| F-1.2 | Projekt laden | MainViewModel → LoadProjectCommand | POST /api/project/load | Projekt geladen, State aktualisiert |
| F-1.3 | Projekt speichern | MainViewModel → SaveProjectCommand | POST /api/project/save | Änderungen persistiert |

## Bereich 2: Media Import

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-2.1 | Audio-Datei importieren | MediaIngestView → ImportAudioCommand | POST /api/audio/import | Datei registriert, in DB eingetragen |
| F-2.2 | Video-Datei importieren | MediaIngestView → ImportVideoCommand | POST /api/video/import | Datei registriert, Thumbnail generiert |
| F-2.3 | Batch-Import | MediaIngestView → BatchImportCommand | POST /api/media/batch | Mehrere Dateien auf einmal |

## Bereich 3: Audio-Bibliothek & Analyse

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-3.1 | Audio-Liste anzeigen | AudioLibraryView Laden | GET /api/audio/clips | Liste aller Audio-Clips |
| F-3.2 | Audio analysieren (komplett) | AudioLibraryVM → AnalyzeCommand | POST /api/audio/analyze | BPM, Key, Waveform, Spektral, Struktur |
| F-3.3 | Beat-Detection | (Teil von F-3.2) | — | Korrekte BPM-Erkennung |
| F-3.4 | Key-Detection | (Teil von F-3.2) | — | Korrekte Tonart |
| F-3.5 | Waveform-3-Band | AudioLibraryVM | GET /api/audio/waveform/{id} | 3-Band Waveform-Daten |
| F-3.6 | Spektral-Analyse | (Teil von F-3.2) | — | Spektral-Daten vorhanden |
| F-3.7 | Struktur-Erkennung | (Teil von F-3.2) | — | Segmente (Intro, Verse, etc.) |
| F-3.8 | Stem-Separation | AudioLibraryVM → SeparateCommand | POST /api/audio/separate | Vocals + Instrumental getrennt |
| F-3.9 | SSE Progress bei Analyse | — | GET /api/events/stream | Echtzeit-Fortschritt |

## Bereich 4: Video-Bibliothek & Analyse

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-4.1 | Video-Liste anzeigen | VideoLibraryView Laden | GET /api/video/clips | Liste aller Video-Clips |
| F-4.2 | Video analysieren (komplett) | VideoLibraryVM → AnalyzeCommand | POST /api/video/analyze | Szenen, Embeddings, Motion |
| F-4.3 | Scene-Detection | (Teil von F-4.2) | — | Szenen-Grenzen erkannt |
| F-4.4 | SigLIP Embeddings | (Teil von F-4.2) | — | 1152-dim Vektoren in FAISS |
| F-4.5 | Motion-Analyse (RAFT) | (Teil von F-4.2) | — | Motion-Scores pro Szene |
| F-4.6 | Thumbnail-Generierung | VideoLibraryVM | GET /api/video/thumbnails/{id} | Thumbnails vorhanden |
| F-4.7 | SSE Progress bei Analyse | — | GET /api/events/stream | Echtzeit-Fortschritt |

## Bereich 5: Anchor/Beats

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-5.1 | Beat-Anchors anzeigen | AnchorView Laden | GET /api/audio/beats/{id} | Beat-Positionen visualisiert |
| F-5.2 | Anchor hinzufügen | AnchorVM → AddAnchorCommand | POST /api/audio/anchors | Neuer Anchor gespeichert |
| F-5.3 | Anchor entfernen | AnchorVM → RemoveAnchorCommand | DELETE /api/audio/anchors/{id} | Anchor gelöscht |

## Bereich 6: Pacing/Director

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-6.1 | Pacing generieren | DirectorVM → GenerateCommand | POST /api/pacing/generate | Cut-List erstellt |
| F-6.2 | Audio-Clip wählen | DirectorVM → SelectAudioCommand | — | Audio für Pacing ausgewählt |
| F-6.3 | Video-Clips wählen | DirectorVM → AddVideoCommand | — | Videos für Pacing hinzugefügt |
| F-6.4 | Pacing-Preview | DirectorVM → PreviewCommand | POST /api/pacing/preview | Preview gerendert |
| F-6.5 | SSE Progress | — | GET /api/events/stream | Echtzeit-Fortschritt |

## Bereich 7: Timeline

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-7.1 | Timeline anzeigen | TimelineView Laden | GET /api/pacing/timeline | Timeline-Einträge visualisiert |
| F-7.2 | Clip verschieben | TimelineVM → MoveClipCommand | PUT /api/pacing/timeline | Position aktualisiert |

## Bereich 8: Rendering

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-8.1 | Render starten | ProductionVM → RenderCommand | POST /api/render/start | Rendering beginnt |
| F-8.2 | Render-Status | ProductionVM | GET /api/render/status | Progress-Updates |
| F-8.3 | Render abbrechen | ProductionVM → CancelCommand | POST /api/render/cancel | Rendering gestoppt |
| F-8.4 | Output-Datei prüfen | — | — | Gültiges MP4 erzeugt |

## Bereich 9: Einstellungen

| ID | Funktion | Einstiegspunkt (UI) | API-Endpoint | Erwartung |
|----|----------|---------------------|--------------|-----------|
| F-9.1 | GPU-Status anzeigen | SettingsView Laden | GET /api/gpu/status | VRAM, Temperatur, Auslastung |
| F-9.2 | Cache leeren | SettingsVM → ClearCacheCommand | POST /api/settings/clear-cache | Cache bereinigt |
| F-9.3 | GPU Cleanup | SettingsVM → CleanupGpuCommand | POST /api/gpu/cleanup | VRAM freigegeben |
