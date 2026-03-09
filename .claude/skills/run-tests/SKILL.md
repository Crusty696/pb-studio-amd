---
name: run-tests
description: "PB Studio Testsuite ausfuehren mit korrektem PYTHONPATH und Ergebnis-Analyse"
---

# PB Studio Tests ausfuehren

Fuehre die komplette PB Studio Testsuite aus und analysiere die Ergebnisse.

## Ablauf

### 1. Venv und Umgebung pruefen
```bash
.venv/Scripts/python.exe --version
# Muss Python 3.11.x sein
```

### 2. Tests ausfuehren
```bash
cd C:\Users\david\Dokumente\Pb_studio_AMD_version
set PYTHONPATH=src
.venv\Scripts\python.exe -m pytest Tests/ -v --tb=short
```

**WICHTIG — Bekannte Fallen:**
- `testpaths = Tests` mit Grossbuchstabe T (Windows NTFS)
- `PYTHONPATH=src` ist PFLICHT (kein editable install)
- Patch-Pfade muessen `pb_studio.xxx` sein, NICHT `src.pb_studio.xxx`
- `AudioAnalyzer` via `__new__` braucht manuell `analyzer.ffmpeg_path = "ffmpeg"`
- `pacing_router._run_pacing_generation` hat 4 Parameter: `config, audio_clips, video_clips, cached_analysis`
- Backend-Tests brauchen gueltige Clip-IDs in `fresh_state` (BUG-027 Validierung)

### 3. Ergebnis auswerten

Erwartetes Ergebnis: **163+ Tests PASSED, 0 FAILED, ~9 SKIPPED**

Falls Failures auftreten:
1. Fehler-Traceback lesen
2. Pruefen ob es eine der bekannten Fallen ist (siehe oben)
3. Fix vorschlagen mit genauer Datei und Zeile
4. Nach Fix erneut ausfuehren

### 4. Ergebnis-Tabelle ausgeben

```
## Test-Ergebnis

| Metrik | Wert |
|--------|------|
| Passed | X |
| Failed | Y |
| Skipped | Z |
| Dauer | X.Xs |
| Status | ✅ GRUEN / ❌ ROT |
```

Falls FAILED > 0: Fehler-Details mit Datei, Zeile und Ursache auflisten.
