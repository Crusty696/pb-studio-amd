# Befund #2 und Brain-`weights.db` – Nachweis (2026-09-30)

## Befund #2 (98.982/98.984 Frames, fehlender 437,861-s-Beleg)
Historischer Lauf `d11dcd29` (2026-09-27) bleibt unwiederbringlich. Neu: ein vollständiger Lauf
mit **derselben Masterdatei** und **derselben Soll-Framezahl** und lückenloser Beweiskette.

- Master: `…\Psy-Set\Progressive Psy Summer Dream mix  by Crusty Free download.wav`,
  582.024.954 Bytes, 3299,456508 s (identisch mit dem Master des Vorfalls).
- Job `e78a7eeb-2ab7-490f-a3b5-4853e2f8538c`, Run `da8cf527afec4b0e9846ea70f141f328`, h264_amf, 1920×1080, 30 fps.
- `result.json`: `expected_frames 98984`, `frame 98984`, `exit_code 0`, `status completed`,
  Hashes für Timeline, Segmentmanifest (2889 Segmente), Concat-Eingabe, Progress- und Stderr-Log.
- `validation.json`: `status passed`, `decoded_frames 98984`, `true_peak_dbtp -3.58`, Endstille 0,0 s.
- Unabhängig heute: `ffprobe -count_packets` → `nb_read_packets=98984`, Dauer 3299,466667 s.
- Zeitfenster Manifest→Validierung: 01:51:47,613 → 01:59:04,823 = **437,2 s** (Encode 288,5 s + Validierung 148,7 s),
  also genau das Intervall, das beim Vorfall ohne Beleg war – jetzt vollständig belegt.
- Ursache des Frame-Defizits war der in T008 behobene `setpts`-Fehler; dieser Lauf ist der Volllängen-Beleg.

Status: **geschlossen durch Reproduktion in voller Länge**. Die historischen Belege von `d11dcd29`
bleiben verloren; das wird nicht als wiederhergestellt behauptet.

## Brain `weights.db`
Gemeldet war `database disk image is malformed` (qc-report, Teardown 2026-09-27/28).

- Backup (vorige Session, 06:59): `%APPDATA%\PB_Studio\brain_backup_20260930_0700\` –
  `weights.db` SHA-256 `616A63D6…D926`, `patterns.db` `9FA12BD7…2124` (+ `-shm`/`-wal`).
- Prüfung heute (read-only, `PRAGMA integrity_check` + `quick_check`) aller Kopien:
  aktive `brain\weights.db`, Backup von 06:59 und vier App-Backups von 05:10 → alle **`ok`**.
- Inhalt: Schema v2, `axis_weights` 0 Zeilen, `feedback_count 0`,
  `migration_reason = "v1 event log incomplete; neutral sparse-credit restart"`.
  `patterns.db` ok (0 Zeilen), `embedding_cache.db` ok (242 Einträge).
- Die beschädigte Fassung existiert nicht mehr: die Datei wurde am 30.09. 00:54 von der App neu
  angelegt/migriert (neutraler Neustart). Eine Reparatur war daher nicht nötig und wurde nicht ausgeführt.
- Folge: gelernte Brain-Gewichte aus der Zeit vor dem Neuaufbau sind nicht mehr vorhanden
  (rekursive Suche unter `%APPDATA%\PB_Studio` fand keine ältere `weights.db`-Kopie).
