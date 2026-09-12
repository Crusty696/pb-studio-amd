# Evidence: Pacing-Degradation ohne Video-Audio-Key (T003)

Datum: 2026-09-12
Autor: Antigravity / Codex Pair Programming

## 1. Problemstellung
Wenn `use_key_matching: True` in der Pacing-Konfiguration aktiviert ist, aber die Video-Clips (z.B. KI-generierte MP4-Dateien aus Wan / LTX) keine Tonspur besitzen (`audio_key: unavailable` / `audio_key=None`), darf das Pacing-System:
1. Weder abstuerzen noch Fehler werfen.
2. Keine willkuerliche oder verzerrte Clip-Bewertung durchfuehren.
3. Die Sortierung nicht invertieren oder blockieren.

## 2. Implementierungsnachweis
1. **Neutrale Bewertung**:
   - In `advanced_pacing_engine.py::_key_compatibility_score(audio_key, video_key)`:
     ```python
     if not audio_key or not video_key:
         return 0.5  # Neutral, kein Penalty
     ```
2. **Monotone Skalierung**:
   - In `clip_selector.py`:
     ```python
     if total_score >= 0:
         total_score *= key_score
     else:
         total_score /= max(key_score, 1e-6)
     ```
     Da alle Clips ohne Tonspur denselben Faktor (0.5) erhalten, bleibt die Rangfolge der Kandidaten zu 100% identisch zur reinen Motion-/Energy-/Semantic-Sortierung.
3. **Beobachtbarkeit**:
   - `pacing_service.py` loggt transparent:
     `use_key_matching ohne Wirkung: audio_key=..., 0/X video_keys verfuegbar — jeder Clip erhaelt denselben neutralen Faktor`

## 3. Verifikation
- **Unit Test**: `Tests/test_pacing_video_key.py::test_pacing_degradation_without_video_audio_key_neutral_score`
  - Getestet mit 2 Clips ohne Audio-Key (`None`), einer mit Motion 0.8 (Target 0.8) und einer mit Motion 0.3.
  - Ergebnis: Clip 201 gewinnt zuverlaessig und deterministisch anhand Motion-Matching.
- **Suite-Status**: 12 von 12 Tests in `test_pacing_video_key.py` erfolgreich (100% gruen).

Status: **VERIFIED**.
