# PB Studio AMD – Heavy Runtime Verification (Agent D)

Datum: 2026-03-13
Projektpfad: `C:\Users\david\Dokumente\Pb_studio_AMD_version`
Testprojekt: `C:\Users\david\Documents\PBStudio\HeavyVerify_1773365904`
Rohdaten: `tmp/heavy_verify/heavy_verify_report.json`

## Ziel
Echter Last-/Langlauf für Render + Analyse mit Fokus auf:
- Progress-Verhalten
- ETA-/Runtime-Felder
- SSE-Streams (progress/log/gpu)
- GPU-Monitoring unter Last
- Cancel-Pfad
- Statuswechsel und Cleanup
- Stabilität bei gemischtem Material

## Testsetup
### Backend / Runtime
- laufendes Backend wiederverwendet (`/health` bereits online)
- GPU laut Backend: `AMD Radeon RX 7800 XT`, `16368 MB VRAM total`
- Startzustand GPU: `1784 MB used`, `27°C`

### Audio
- Quelle: `C:\Users\david\Videos\Music-Video_Clips\AV\Audio\recording-2021-04-24-235308.wav`
- daraus echter 60s-Excerpt erzeugt: `tmp/heavy_verify/audio_excerpt_60s.wav`
- ffprobe: `60.000000s`, WAV, `44.1 kHz`, Stereo

### Video-Clips (echte Dateien)
1. `1 (1).mp4` – `1280x720 @30`, `5.37s`
2. `1 (10).mp4` – `854x480 @30`, `10.00s`
3. `1 (11).mp4` – `854x480 @30`, `10.00s`
4. `1 (109).mp4` – `1920x1080 @30`, `5.10s`
5. `1 (110).mp4` – `1920x1080 @30`, `10.43s`
6. `1 (150).mp4` – `1280x720 @24`, `8.00s`

### Laufdesign
1. neues Projekt erstellt
2. Audio + 6 Video-Clips importiert
3. Audio analysiert
4. alle 6 Video-Clips analysiert
5. Pacing auf 60s-Ziellänge mit Motion + Structure aktiviert
6. Render-Lauf A: 1080p/30/high, nach ~12s gecancelt
7. Render-Lauf B: gleicher Setup, komplett durchlaufen lassen
8. währenddessen parallel SSE-Mitschnitt auf:
   - `/events/progress`
   - `/events/log`
   - `/events/gpu`
9. Status-Polling auf `/render/status/{task_id}` alle 2s

## Beobachtungen

### 1) Import / Analyse / Pacing
- Audio-Import: PASS
- Audio-Analyse: PASS
  - erkannt: `123.046875 BPM`, `74 beats`
- Video-Analyse: PASS auf allen 6 Clips
  - Clip 5 (`1 (110).mp4`) lieferte als einziger echte Szenenschnitte: `scene_count=4`
  - avg_motion war auf allen Clips > 0 und stark unterschiedlich (`80.85` bis `385.50`)
- Pacing: PASS
  - Log meldet: `19 Cuts generiert`, `total_duration=36.71s`
  - `/pacing/timeline` lieferte echte `entries`; kein Crash, keine leeren Antworten

### 2) Render unter Last – kompletter Lauf
- Start: PASS
- Statuswechsel beobachtet: `running -> completed`
- Backend-Elapsed laut Finalstatus: `15.0s`
- Polled Walltime bis terminaler Status: `16.1s`
- Output-Datei vorhanden: PASS
  - `C:\Users\david\Documents\PBStudio\HeavyVerify_1773365904\output\heavy_complete_probe.mp4`
  - ffprobe: `duration=60.000000`, `size=47955615`

#### Beobachtetes Progress-Muster (SSE)
- `10%` – `Prüfe Quellmaterial...`
- `10%..47%` – Normalisierung einzelner Clips (`Normalisiere Clip X/19...`)
- `55%` – `Erstelle Schnittliste...`
- `58%` – `Starte Rendering...`
- danach FFmpeg-artige Laufmeldungen:
  - `63%` – `Rendering: 00:05 / 01:00`
  - `69%` – `Rendering: 00:14 / 01:00`
  - `73%` – `Rendering: 00:21 / 01:00`
  - `77%` – `Rendering: 00:27 / 01:00`
  - `84%` – `Rendering: 00:39 / 01:00`
  - `100%` – `Fertig!`
  - terminal danach `completed`

### 3) Cancel-Lauf
- Start: PASS
- Cancel-Request nach `~12.1s` gesendet
- Statuswechsel beobachtet: `running -> cancelled`
- Finalstatus: `cancelled`, letzter sichtbarer Fortschritt `47%`
- partielle Output-Datei nach Cancel: **nicht vorhanden**
- Cleanup damit praktisch bestätigt: PASS

### 4) SSE / Logs / GPU
#### Progress-SSE
- `46` Events total
- Aufteilung:
  - `7` Import-Progress-Events
  - `1` Analysis/Pacing-Event
  - `38` Render-Progress-Events
- Stream blieb über beide Render-Läufe stabil offen und lieferte nutzbare Daten

#### Log-SSE
- `27` Log-Events
- Import, Analyse, Pacing, Render-Start, Cancel und Completion wurden sauber emittiert
- Beobachtet wurden echte fachliche Logs, nicht nur Keepalives

#### GPU-SSE
- `15` GPU-Events
- Werte blieben über den Test fast konstant:
  - VRAM: durchgehend `1784 / 16368 MB`
  - Temperatur: durchgehend `27°C`
  - GPU-Load: anfänglich `8%`, danach meist `1–2%`
- Ergebnis: Stream funktioniert, aber dieser konkrete Lauf hat **keinen klar sichtbaren GPU-Druck** erzeugt

### 5) Status-/ETA-/Runtime-Felder
#### Was funktioniert
- `status` wird korrekt zwischen `running`, `cancelled`, `completed` umgeschaltet
- `percent` steigt nachvollziehbar und korreliert mit den SSE-Messages
- `elapsed_seconds` wird im terminalen Zustand gesetzt (`12.1s` cancel, `15.0s` complete)

#### Was nicht sauber funktioniert
- Während des gesamten aktiven Laufs blieben folgende Felder in `/render/status/{task_id}` konstant auf 0:
  - `eta_seconds = 0.0`
  - `current_frame = 0`
  - `total_frames = 0`
  - `fps = 0.0`
  - `elapsed_seconds = 0.0` (erst am Ende gesetzt)
- Praktisch heisst das:
  - Prozent und Message funktionieren
  - echte ETA-/Frame-/FPS-Runtime-Telemetrie existiert im API-Status aktuell nicht brauchbar

## PASS / PARTIAL / FAIL
### PASS
- Import echter Heavy-Assets
- Audio-Analyse auf 60s-Excerpt
- Video-Analyse auf 6 echten Clips
- Pacing-Generierung mit 19 Cuts
- Render-Start unter gemischtem Material
- Progress-SSE unter Last
- Log-SSE unter Last
- GPU-SSE technisch stabil
- Cancel-Pfad inklusive Cleanup
- Finaler Long-Run mit gültiger 60s-Output-Datei
- Statuswechsel `running -> cancelled/completed`

### PARTIAL
- GPU-/VRAM-Stress: funktional überwacht, aber Test erzeugte real **keine** spürbare VRAM-/Temperatur-Spitze
- Heavy-Charakter des Laufs war eher **Render-Normalisierung + 60s Output** als echter GPU-Stresstest

### FAIL
- ETA-/Runtime-/Frame-Telemetrie im Render-Status ist während aktiver Läufe faktisch nicht implementiert/nicht befüllt
  - `eta_seconds`, `fps`, `current_frame`, `total_frames`, laufendes `elapsed_seconds` blieben 0

## Echte Risiken
1. **Render-ETA im UI/API nicht belastbar**
   - Das System zeigt Fortschritt, aber keine echte ETA/FPS/Frame-Zählung.
   - Für längere Produktionen ist das operativ schwach: man weiss grob, dass etwas läuft, aber nicht wie schnell oder wie lange noch.

2. **GPU-Monitoring liefert kaum Lastsignal bei diesem Renderpfad**
   - GPU-SSE funktioniert technisch, aber die gemessenen Werte blieben fast flach.
   - Entweder ist der Renderpfad in diesem Fall kaum GPU-lastig, oder die Telemetrie-Auflösung/Quelle ist zu grob für echte Lastbeobachtung.

3. **Pacing-Ziellänge vs. tatsächliche Timeline-Länge**
   - Request lief mit `duration_limit=60`, Log meldet aber `total_duration=36.71s` bei `19 Cuts`.
   - Render erzeugte trotzdem einen 60s-Output, weil mit 60s-Audio gerendert wurde.
   - Das ist kein Crash, aber ein inhaltlicher Mismatch, den man bei Qualitäts-/UX-Bewertung im Auge behalten muss.

## Betroffene Dateien
### App / Projektdaten
- `C:\Users\david\Documents\PBStudio\HeavyVerify_1773365904\project.json`
- `C:\Users\david\Documents\PBStudio\HeavyVerify_1773365904\output\heavy_complete_probe.mp4`

### Verifikationsartefakte
- `tmp/heavy_verify_run.py`
- `tmp/heavy_verify/heavy_verify_report.json`
- `tmp/extract_heavy_summary.py`
- `tmp/extract_heavy_logs.py`
- `VERIFICATION_HEAVY_RUNTIME_2026-03-13_AGENT_D.md`

## Code-Fixes
- Keine Produktivcode-Änderung durchgeführt.
- Kein klarer Minimalfix umgesetzt, weil der auffälligste Defekt (fehlende aktive ETA-/FPS-/Frame-Telemetrie) kein sauberer One-Liner ist, sondern strukturell im Render-Progress-Pfad fehlt.
