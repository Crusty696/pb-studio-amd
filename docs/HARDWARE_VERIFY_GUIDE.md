# Hardware-Verify-Guide — Brain-Modul

Hardware-Verifikation gemäß
[`specs/dod.md`](../specs/dod.md). Alle ausführbaren Prüfer sind im jeweiligen
Abschnitt benannt; nicht vorhandene historische Skripte sind kein Prüfpfad.

> **Status 2026-08-01:** Release-Gate T411 ist bestanden. RAFT, SigLIP,
> Moondream Vision, CLAP Audio/Text und Audio-MDX liefen im sauberen externen
> Checkout auf der AMD Radeon RX 7800 XT, DXGI-Index `1`, LUID
> `0x00000000_0x00012a2a`. Alle Sessions belegten `DmlExecutionProvider`,
> beide deaktivierten DirectML-Speicherflags und den gesperrten CPU-Fallback.
> H.264/HEVC-AMF liefen auf derselben LUID. Autoritativ ist
> [`T411-directml-amf-fresh-install.md`](../specs/00013-system-wide-bug-hunting-audit/evidence/T411-directml-amf-fresh-install.md).
> Moondream Vision ist bereit; Caption bleibt mangels vollständig
> DirectML-fähigem Decoder ausdrücklich `unavailable`.

## Freigegebene Modellherkunft

| Asset | Gepinnte Quelle | Lizenz |
|---|---|---|
| RAFT Small | `pytorch/vision@61943691d3390bd3148a7003b4a501f0e2b7ac6e` | BSD-3-Clause |
| SigLIP SO400M | `google/siglip-so400m-patch14-384@9fdffc58afc957d1a03a25b10dba0329ab15c2a3` | Apache-2.0 |
| CLAP Audio/Text | `ConceptualMachines/magda-sample-tagger@f24970352f239768aaad48cc8734fb298441a763` | BSD-3-Clause AND Apache-2.0 |
| CLAP Processor | `laion/clap-htsat-unfused@8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a` | Apache-2.0 |
| Audio-MDX | `TRvlvr/model_repo@356bbd334a0ebb8449c602503ac204a3c06df4f6` | MIT |
| Moondream Vision | `Heliosoph/moondream2-onnx@e48d8acc253b09d8f201206aa126388742298452` | Apache-2.0 |

Verbindlich sind die exakten Source-, Target-, Archiv- und Lizenzhashes in
[`config/directml-model-assets.json`](../config/directml-model-assets.json)
und
[`config/directml-asset-bundle.json`](../config/directml-asset-bundle.json).

## Setup einmalig

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
.\.venv\Scripts\Activate.ps1
```

Verbindliche Runtime: Projekt-`.venv` mit Python 3.11.x, NumPy 1.26.4 und
`onnxruntime-directml`. Keine Einzelinstallation oder Paketaktualisierung aus
diesem Guide. Modellassets werden nur über
[`scripts/provision_directml_assets.ps1`](../scripts/provision_directml_assets.ps1)
aus dem freigegebenen Archiv installiert.

## 1. CLAP auf DirectML (historischer Probe; superseded)

Der frühere Standalone-Verifier ist gesperrt und liefert absichtlich Exitcode
`2`; er kann weder Modellprovenienz noch den aktiven Registry-Vertrag belegen.
Die folgende Ausgabe ist ausschließlich historisch und darf nicht als
Releasebeleg zitiert werden:

**Historische Ausgabe:**
```
Audio: data\dummy_audio.wav
Device:     privateuseone:0
mix shape:  (512,)
elapsed:    ~5 s (erste Inferenz, model load eingeschlossen)
OK
```

**Historische Aussage:** Dieser Probe nutzte `torch-directml` und ist kein
Beleg für den aktuellen Vertrag. Aktuell ist semantisches Audio nur mit einem
registrierten CLAP-ONNX-Modell über `DmlExecutionProvider` verfügbar; fehlt es,
meldet die Pipeline `unavailable`.

## 2. SigLIP-2 Vision-Tower auf DirectML (historischer Probe; superseded)

Der frühere Standalone-Verifier ist gesperrt und liefert absichtlich Exitcode
`2`; SigLIP-Hardware-QC erfolgt erst über den registrierten T332-Testpfad.

**Historische Ausgabe:**
```
Device:     privateuseone:0
clip shape: (768,)
elapsed:    ~17 s (erste Inferenz)
OK
```

**Historische Aussage:** Die 768-Dimensionsannahme ist superseded. Der
kanonische SigLIP-SO400M-ONNX-Vertrag liefert 1152 Dimensionen und hat keinen
CPU-Fallback.

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
   .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
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

## 7. Recovery-Test (historisch; nur mit copy-aware Harness)

1. App schließen.
2. Eine verifizierte Kopie von `weights.db` in einem isolierten
   Rehearsal-Verzeichnis anlegen. Niemals die Produktionsdatei überschreiben.
3. Nur die Kopie mit 0-Bytes überschreiben:
   ```powershell
   Set-Content -Path ".\rehearsal\weights.db" -Value $null
   ```
4. Den Recovery-Pfad ausschließlich über ein Harness starten, das die
   isolierte Kopie explizit als Datenquelle bindet. Fehlt diese Bindung, ist
   der Probe BLOCKED und die App darf nicht gegen Produktionsdaten gestartet
   werden. Hash, Restore und Recovery-Artefakt im Rehearsal-Verzeichnis
   dokumentieren.

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
- **ML-Runtime:** ONNX DirectML-only. Fehlender DML-Provider ist ein
  expliziter Fehler; keine CPU-Ausweichroute.
- **Versionen:** Python 3.11.x und NumPy 1.26.4 sind fest. Abhängigkeiten
  dürfen nicht aus diesem Guide geändert werden.
- **Foote-SSM für 2h-Mix**: Chroma wird auf 1 Frame/Sekunde aggregiert (sonst 75 GB Speicher). Tradeoff: minimale Auflösungs-Reduktion bei sub-1s-Boundaries.
