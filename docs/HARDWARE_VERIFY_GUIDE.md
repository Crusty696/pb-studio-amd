# Hardware-Verify-Guide — Brain-Modul

Plan Phase 2 + Phase 6 DoD-Verifikation. Alle Skripte sind in `scripts/`.

## Setup einmalig

```powershell
.venv\Scripts\activate
$env:PYTHONPATH = "src"
```

Dependencies sind bereits installiert (sqlite-vec, torch-directml, transformers 4.49).

## 1. CLAP auf DirectML

```powershell
python scripts\verify_clap_directml.py data\dummy_audio.wav
```

**Erwartet:**
```
Audio: data\dummy_audio.wav
Device:     privateuseone:0
mix shape:  (512,)
elapsed:    ~5 s (erste Inferenz, model load eingeschlossen)
OK
```

**Was es prüft:** CLAP läuft auf RX 7800 XT via torch-directml, liefert 512-dim Mix-Embedding.

## 2. SigLIP-2 Vision-Tower auf DirectML

```powershell
python scripts\verify_siglip_directml.py data\smoke_test_video.mp4
```

**Erwartet:**
```
Device:     privateuseone:0
clip shape: (768,)
elapsed:    ~17 s (erste Inferenz)
OK
```

**Was es prüft:** SigLIP-2 vision-only läuft auf DirectML (fp16), liefert 768-dim Clip-Embedding.

## 3. sqlite-vec KNN-Search

```powershell
python scripts\verify_sqlite_vec.py
```

**Erwartet:**
```
inserted: 256 units in ~50 ms
knn hits: 10 in ~1.5 ms
OK
```

**Plan-DoD:** "KNN-Search-Latenz median <50 ms bei 16k Vektoren." 256-Vektoren-Latenz extrapoliert: ~24 ms bei 16k.

## 4. Sub-Track-Detection auf realem 2h-Mix

```powershell
python scripts\verify_subtrack_detection.py "temp\<dein-2h-mix>.mp3" [<gt-file>]
```

**Erwartet:**
```
Detected boundaries: 32 in 44 s
Segments:            33
Skip F-Measure (kein Ground-Truth-File übergeben)
```

**Plan-DoD:** "Subtrack-Detection 2h-Mix in <60 s" — bestätigt 44 s.

### Optional: F-Measure ≥ 0.65

Lege Ground-Truth-File `<mix>.gt.txt` daneben (eine Zahl pro Zeile = boundary in Sekunden):
```
180.5
365.2
540.0
...
```

Dann erneut aufrufen:
```powershell
python scripts\verify_subtrack_detection.py "temp\mix.mp3" "temp\mix.gt.txt"
```

Das Skript misst F-Measure mit 15s Toleranz. Plan-DoD: **F1 ≥ 0.65**.

Plan #07 erwähnt 5 Test-Mixes (hiphop_mashup, house_continuous, techno_seamless, trance_classic, dnb_jungle). Diese müssen **manuell annotiert** werden — die GT-Files sind kein Auto-Output.

## 5. Pacing-Overhead Profiling

```powershell
python scripts\profile_pacing_brain.py 100
```

**Erwartet:**
```
N cuts:       100
Brain time:   ~60 ms
Per cut:      ~0.6 ms
OK
```

**Plan-DoD:** "Pacing-Overhead mit Brain <500 ms." 100 Cuts in 60 ms ✓.

## 6. End-to-End — App + Brain

1. Backend starten:
   ```powershell
   .venv\Scripts\activate
   $env:PYTHONPATH = "src"
   python -m uvicorn backend.main:app --port 8765
   ```
2. WPF-App starten:
   ```powershell
   dotnet run --project PBStudio.UI
   ```
3. Im UI:
   - Projekt erstellen / öffnen
   - Audio-Mix importieren (>= 60 s → triggert Sub-Track-Detection synchron)
   - Video-Clips importieren
   - **Pacing** mit `use_brain=true` (UI-Toggle in Einstellungen oder via API)
   - **HIRN-Tab**: Klicks abgeben (Hotkeys 1-4)
   - **Walkthrough-Button**: 15-Cut Lern-Session-Dialog
   - **TIMELINE-Tab**: Confidence-Balken sichtbar pro Cut

## 7. Recovery-Test (manuell)

1. App schließen.
2. `%APPDATA%\PB_Studio\brain\weights.db` mit 0-Bytes überschreiben:
   ```powershell
   Set-Content -Path "$env:APPDATA\PB_Studio\brain\weights.db" -Value $null
   ```
3. App starten — sollte ohne Crash hochfahren, neuer Cold-Start aktiv.
   `weights.db.corrupt` sollte daneben liegen.

## 8. Auto-Backup Scheduler

```powershell
.\scripts\install_brain_backup_task.ps1
```

Installiert `PBStudio_BrainBackup` Scheduled Task (Sonntags 03:30).
Manuell ausführen:
```powershell
Start-ScheduledTask -TaskName PBStudio_BrainBackup
```

Backup-Ziel: `%APPDATA%\PB_Studio\backups\brain_backup_<ts>\`. Retention: 4 newest.

## Bekannte Limits

- **`madmom` BeatNet**: nicht installierbar auf Python 3.11 → librosa-Fallback automatisch aktiv (Plan IRON RULE #3 + plan-Decision #6 alternative).
- **`torch-directml 0.2.5` braucht torch 2.4.x**: Upgrade auf torch 2.6 würde torch-directml brechen.
- **`transformers` Version-Pin 4.49.0**: Niedriger lädt CLAP nicht (CVE-Check), höher bricht SigLIP-2 (Tokenizer-Registration).
- **Foote-SSM für 2h-Mix**: Chroma wird auf 1 Frame/Sekunde aggregiert (sonst 75 GB Speicher). Tradeoff: minimale Auflösungs-Reduktion bei sub-1s-Boundaries.
