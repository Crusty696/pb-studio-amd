# Befund #2 (437,861-s-Lücke) und Brain-weights.db – 2026-09-30

Parallel-Session-Notiz: Diese Datei stammt aus einer zweiten Claude-Sitzung, die
gleichzeitig mit der T013/T014-Sitzung lief. Sie ändert keine bestehende Datei.

## Befund #2 – Lücke reproduziert und erklärt

Quelle: Render-Lauf des Projekts `t013_psy_20260930` (DB-ID 10), derselbe
54:59-Master (3.299,4565 s, 98.984 erwartete Frames) wie der historische Vorfall
`d11dcd29`.

Evidence-Ordner:
`C:\Users\david\Documents\PBStudio\t013_psy_20260930\t013_psy_20260930\.render_evidence\e78a7eeb-2ab7-490f-a3b5-4853e2f8538c\da8cf527afec4b0e9846ea70f141f328\`

| Zeitpunkt (lokal) | Quelle | Ereignis |
|---|---|---|
| 01:51:47.613 | mtime `segments.json` / Backend-Log `Final Render Encoder: h264_amf` | letzte Backend-Logzeile vor dem Encode |
| 01:56:36.088 | `result.json.recorded_at_epoch` | Encode fertig: 98.984/98.984 Frames, `progress_end=true`, exit 0 |
| 01:59:04.823 | `validation.json.recorded_at_epoch` / Backend-Log `Render-Artefakt validiert` | Full-Decode 98.984/98.984, −3,58 dBTP, `passed` |

- Encode 288,475 s + Validierung (Probe + Full-Decode) 148,735 s = **437,209 s**
  ohne eine einzige Backend-Logzeile.
- Historisch gemeldete Lücke: 437,861 s. Differenz 0,65 s (0,15 %).

Schluss: Die „Lücke“ ist kein Datenverlust, sondern die erwartbare Stille des
Backend-Logs während Final-Encode plus Full-Decode-Validierung eines 55-Minuten-
Exports. Der Fortschritt dieser Phase steht heute in `ffmpeg.progress.log`
(blockweise geflusht, T015) und in `validation.json.history` (Eintrag `running`
beim Start der Validierung).

Grenze: Die Original-Belege von `d11dcd29` (`result.json`, `validation.json`)
fehlen weiterhin; die Zuordnung beruht auf der Dauergleichheit am selben Master,
nicht auf den Originaldateien. Der Frame-Verlust (98.982/98.984) ist mit dem
aktuellen Code am selben Master nicht mehr reproduzierbar: 98.984/98.984
encodiert und dekodiert.

## Brain-weights.db

- Backup vor jeder Prüfung: `%APPDATA%\PB_Studio\brain_backup_20260930_0700\`
  (`weights.db` SHA-256 `616A63D6498D1CD5DACB6528C680B4E57CF290E21964F10E02FF21C186D5D926`,
  dazu `patterns.db` und die `-shm/-wal`-Dateien).
- Live-Datei (mtime 2026-09-30 00:54:36): `PRAGMA quick_check` = `ok`,
  `PRAGMA integrity_check` = `ok`.
- Inhalt: `weight_semantics_version=2`, `feedback_count=0`,
  `axis_weights` 0 Zeilen, Archivtabelle 0 Zeilen.
- Die am 29.09. gemeldete beschädigte Datei ist also bereits ersetzt worden
  (neu angelegt um 00:54). Eine beschädigte Kopie wurde unter
  `%APPDATA%\PB_Studio` nicht gefunden. Reparatur war nicht nötig; es gab
  aber auch vorher keine gelernten Gewichte (0 Feedbacks), also nichts zu retten.

## T014 – zweiter, unabhängiger Caption-Lauf

Werkzeug `scripts/dev/t014_caption_eval.py` (read-only gegen die DB),
Lauf `%TEMP%\pb00035-t014-20260930_081253\` (`results.json` SHA-256
`20BA01F64F71A9DD3071ED0C4ED7E5C6A4D5DDE93F55A518CF0F5DDDEE1C2F2B`).

- Vor und nach dem Lauf geladen: nur `qwen3.5-9b` (LM Studio, `llama-server.exe`
  aus `llama.cpp-win-x86_64-vulkan-avx2-2.47.0`, 9.822 MB auf LUID `0x000116f2`).
- 12 Clips × 3 Bilder (20/50/80 %): 36/36 Bilder mit Tags, Median 1,94 s,
  Maximum 6,26 s, Modell jedes Mal `qwen3.5-9b`.
- Eigene Sichtprüfung je Bild: 33 plausibel, 2 mit einem falschen Merkmal
  (923: „dunkle haut“ bei hellhäutiger Figur unter violettem Licht), 1 unsicher
  (955, Bild 2: nur 4 dünne Tags). Deckt sich mit dem Muster der anderen
  Sitzung: Hautton wird unter Farblicht geraten.
- Kein menschliches Urteil; Vulkan ist nicht DirectML (Policy-Entscheid offen).
