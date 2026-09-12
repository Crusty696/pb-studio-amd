# Evidence: Unterscheidung audio_key unavailable vs. failed (T004)

Datum: 2026-09-12
Autor: Antigravity / Codex Pair Programming

## 1. Problemstellung
Bisher hat `detect_video_audio_key()` bei saemtlichen Fehlern (auch ffmpeg Crash, Timeout, defekte Dateien) stumm `None` zurueckgegeben.
Im `video_router.py` fuehrte `None` immer zu `stage_status["audio_key"] = "unavailable"`.
Ein echter Systemdefekt (ffmpeg Fehler, librosa Crash, Timeout) konnte dadurch nicht von einer tatsaechlich fehlenden Tonspur unterschieden werden. Echte Defekte wurden faelschlicherweise als fehlende Faehigkeit maskiert.

## 2. Loesung
1. **Faehigkeitspruefung via `has_video_audio_stream()`**:
   - Vor der Extraktion wird ueber `ffprobe -v error -select_streams a:0 -show_entries stream=codec_type` geprueft, ob ueberhaupt eine Audio-Spur im Container existiert.
   - Falls keine Audio-Spur existiert: Rueckgabe `None`. Der Router traegt wahrheitsgemaess `unavailable` ein (kein Fehler, keine Fehlermeldung).
2. **Defekterkennung bei vorhandener Tonspur**:
   - Falls eine Audio-Spur existiert, aber `ffmpeg` fehlschlaegt (Returncode != 0), ein Timeout auftritt (>30s) oder die extrahierte WAV unlesbar ist, wird eine explizite `RuntimeError`-Exception ausgeloest.
   - Der Router faengt diese Exception im `except Exception as e:`-Zweig und setzt:
     - `stage_status["audio_key"] = "failed"`
     - `stage_errors["audio_key"] = str(e)`
   - Dadurch bleibt der Task wiederholbar (retryable) und Pacing blockiert bei echten Fehlern, anstatt defekte Analysen stillschweigend zu ignorieren.

## 3. Verifikation
- **Unit Tests**: `pytest Tests/test_pacing_video_key.py` (11 von 11 bestanden).
  - `test_audio_key_no_audio_stream_returns_none_unavailable`: PASS
  - `test_audio_key_stream_present_but_ffmpeg_fails_raises_error`: PASS
  - `test_audio_key_stream_present_but_ffmpeg_times_out_raises_error`: PASS
- **Live-Pruefung**:
  - Reale KI-Clips unter `C:\Users\david\Videos\Video\Clips\images_1750892303155`: Enthalten keine Tonspur (`ffprobe` liefert leeren String). Werden korrekt als `unavailable` eingestuft.
  - Audio-Dateien / Videos mit Tonspur: Enthalten `audio`, werden extrahiert und analysiert.
