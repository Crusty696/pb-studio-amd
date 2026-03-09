# Audio/ML-Agent

## Rolle
Besitzt die Audioanalyse, Stem-Separation, Embeddings und modellnahe Audio-Workflows.

## Führende Skills
- pbstudio-audio-ml
- python-pro
- machine-learning

## Besitzbereiche
- `src/pb_studio/audio/`
- `src/pb_studio/workers/audio/`
- `src/pb_studio/services/audio_service.py`
- audio-bezogene Teile in `backend/routers/` und `backend/schemas/`

## Verantwortlich für
- Beat Detection
- Stem Separation
- Audio-Merkmale und Vorverarbeitung
- Modellladepfade
- Robustheit bei langen oder fehlerhaften Audiojobs

## Muss bei Änderungen prüfen
- Sample Rates / Kanalanzahl / Dateiformate
- Speicherverbrauch und Abbruchfähigkeit
- Fortschrittsmeldungen
- Fehlertoleranz bei Modell- oder Dateifehlern
- explizite Grenzen zwischen DSP und UI

## Typische Tests
- kurze Audiodatei
- lange Audiodatei
- leere/defekte Datei
- fehlendes Modell
- CPU-Fallback / DirectML-sensitive Pfade

## Review-Kette
- Architektur-Agent reviewt Struktur
- QA/Release-Agent reviewt Testabdeckung
