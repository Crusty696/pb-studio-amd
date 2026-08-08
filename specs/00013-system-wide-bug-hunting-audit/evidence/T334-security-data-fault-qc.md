# T334 – Security, Daten und Fault Injection

Status: CONFIRMED

## Rubrik

- [x] Pfad-/Status-Tampering erreicht keinen Datei- oder Weight-Sink.
- [x] Disk-/Replace-/Cancel-Fehler bewahren bestehende Artefakte und State.
- [x] SQLite-/FAISS-Fehler hinterlassen konsistente Generationen.
- [x] Brain-v2-Migration besteht Backup-Hash, Rehearsal und Restore-Probe.
- [x] Projekt-Restore scheitert atomar ohne Cross-Project-Leak.

## Dynamische Validierung

- 165/165 PASS in 36,69 Sekunden.
- Abgedeckt: FastAPI-Projektpfade, Medienpfad-Policy, Chat-Bestätigung und
  Replay-Schutz, unbekannte Brain-Cuts, Backup/Restore, Migrationslücken,
  SQLite-Locks, Vector-Outbox, FAISS-Snapshotfehler, Cache-/Render-Replace,
  Cancel und atomare Zielveröffentlichung.
- Log: `T334-security-data-fault-cluster.log`
  (SHA-256 `588C72B69F4D19127E5F9B4ABD5C6C68C1738EC920DCBC58FFC61C79B4BF822A`).

## Security-Closure

| Source | Control | Sink | Ergebnis |
|---|---|---|---|
| HTTP-/Timeline-/Design-System-Pfade | Auflösung, Katalogbindung und Containment vor Wirkung | Datei-/Projektzugriff | CONFIRMED fail-closed |
| Destruktive Chat-Toolargumente | kanonische Einmalbestätigung, Timeout und Replay-Sperre | mutierender Tool-Handler | CONFIRMED fail-closed |
| Brain-Feedback-ID | Cut-Existenz und Semantic-Availability vor Logging | Weight-/Outbox-Mutation | CONFIRMED fail-closed |
| Projekt-Open/Katalogfehler | isolierter Candidate-State plus Brain-Preflight | Live-State-/Brain-Swap | CONFIRMED atomar |
| Render-/Cache-/FAISS-Diskfehler | Staging, Journal, Restore und bestehendes Ziel | `os.replace`/Index-Publikation | CONFIRMED atomar |

Keine T334-Kandidaten überlebten als offenes Security-Finding.

## Kopie-QC

- Vor Kopie: kein Listener auf Port 8765, SQLite-WAL 0 Bytes.
- Evidence-Pfad:
  `evidence/T334-copy-qc-20260729T1115/`.
- Quell- und Kopie-Hashes waren vor Prüfung identisch.
- Hashmanifest:
  `hashes.sha256.log`
  (SHA-256 `FD3600F363F78F65CFBAE74644F4A7C319376FAD9F5556C7DED7BA2F3764179A`).
- Nach allen Prüfungen blieben sämtliche Live-Quellhashes unverändert:
  `source-unchanged.json`
  (SHA-256 `20A0C15445C9885303850BF464EA069EE6884A7E77ABB6563D40357E95FA2154`).

## SQLite und FAISS

- SQLite `integrity_check=ok`, 0 Foreign-Key-Probleme.
- 1782 Media-Zeilen, 791 `vector_map`-Zeilen, 0 Orphans.
- 6 abgeschlossene und 0 offene Vector-Outbox-Operationen.
- FAISS: Dimension 1152, `ntotal=904`, Metadaten 904.
- Tombstones 113; aktive IDs 791.
- Aktive FAISS-IDs entsprechen exakt allen `vector_map.faiss_id`.

## Brain-Migration und Restore

- Aktuelle Kopie: User-Version 2, Quick-Check `ok`, 102 archivierte
  v1-Zeilen, 0 aktive v2-Zeilen, `feedback_count=0`.
- v1-Backup: User-Version 1, Quick-Check `ok`, 102 aktive Zeilen.
- Restore-Probe ist bytegleich zum v1-Backup.
- Reale v1-Rehearsal-Kopie migrierte auf Version 2:
  Quick-Check `ok`, 102 archiviert, 0 aktiv, `feedback_count=0`.
- Rehearsal-SHA entspricht T324:
  `711769adc442180b840602aff308d0dfb514eba4cb0ece94f8cd53804df5fd2a`.
- Log:
  `integrity-migration-restore.log`
  (SHA-256 `A8ACFA3B553D52ED21CDD48F694EEC21C8E5EDD220477936C2687DD36989D272`).

## Gate

- T334: PASS / CONFIRMED.
- Keine Produktionsmigration und keine Live-Datenmutation ausgeführt.
- `.qc-passed` bleibt bis T338 unzulässig.
