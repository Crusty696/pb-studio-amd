# Cleanup-Checkliste

Nach JEDEM Test-Durchgang eines Bereichs müssen ALLE diese Punkte abgehakt werden.

## Datenbank

- [ ] SQLite `pb_studio.db` — Alle während des Tests erstellten Einträge gelöscht
- [ ] WAL-Checkpoint durchgeführt (`PRAGMA wal_checkpoint(TRUNCATE)`)
- [ ] SHM/WAL-Dateien bereinigt (werden durch Checkpoint aufgeräumt)
- [ ] Verifikation: Alle Tabellen auf erwarteten Stand geprüft

## Dateisystem

### Temp-Verzeichnisse
- [ ] `temp/` — Komplett geleert
- [ ] `data/temp/` — Komplett geleert
- [ ] Keine `.wav`, `.mp4`, `.png` Reste in temp

### Generierte Medien
- [ ] Stem-Separation Outputs entfernt (`*_(Vocals)_*`, `*_(Instrumental)_*`)
- [ ] Generierte Thumbnails entfernt
- [ ] Generierte Waveform-Caches entfernt
- [ ] Render-Outputs entfernt
- [ ] Preview-Dateien entfernt
- [ ] Proxy-Dateien entfernt

### Indizes
- [ ] FAISS-Indizes: Nur Test-generierte entfernt (VORSICHT: bestehende Indizes NICHT löschen!)

### Logs
- [ ] `logs/` Verzeichnis geleert
- [ ] Debug-Outputs entfernt

## Cache

- [ ] Waveform-Cache bereinigt
- [ ] Thumbnail-Cache bereinigt
- [ ] Kein CacheManager-State von Test-Daten übrig

## Verifikation

- [ ] DB-Tabellen geprüft (Cleanup-Script output)
- [ ] Temp-Verzeichnisse geprüft (0 Dateien)
- [ ] Keine Prozesse mehr laufend (Python Backend, WPF App)
- [ ] GPU-VRAM freigegeben (kein ONNX-Session-Leak)

## WICHTIG

- **Testdaten NICHT löschen**: `C:\Users\david\Videos\test_data\` bleibt IMMER unangetastet
- **Bestehende Indizes schützen**: Nur Test-generierte FAISS-Indizes entfernen
- **Kein blindes rm -rf**: Immer gezielt die Test-generierten Daten identifizieren
