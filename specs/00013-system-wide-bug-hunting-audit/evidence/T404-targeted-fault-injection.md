# T404 — Gezielte Fault-Injection

Status: PASS
Ausgangs-SHA: `c8c39cf7569128e3f2fff3948e91aed89c46f965`
Datum: 2026-08-01

## Ausgeführte Verträge

- Projektwechsel und Projektbindung: isolierte Katalogladung, Brain-Bind-Rollback, Generation-/Cache-Guards.
- Persistenz: fehlgeschlagener DB-Sync stellt `project.json` und `timeline.json` wieder her und liefert HTTP 500.
- Settings: malformed JSON, atomarer Write, blockierter Zielpfad und UI-Fehlerwahrheit.
- QueueFull: deterministisches Drop-Oldest, neuestes Event bleibt erhalten, Drop-Metrik steigt exakt einmal; gefilterte Events verbrauchen keine Queue-Kapazität.
- Render-Retry: aktive Attempts werden dedupliziert, terminale Attempts erhalten neue IDs, Shutdown bleibt restartfähig, Nutzerabbruch wird terminal.

## Gefundene und geschlossene Abweichungen

1. `sync_project_db_record() == False` wurde als erfolgreicher Save behandelt. Behoben: expliziter Fehler mit Datei-Rollback.
2. Paralleles Projekt-Anlegen lieferte unter Windows bei atomarem Publish `500`. Behoben: nach erfolgreicher Eigen-Kompensation deterministisches `409 Conflict`.
3. Lokale ignorierte NSwag-Altdatei wurde zusammen mit `obj/Generated/ApiTypes.g.cs` kompiliert. Behoben: `Generated/*.g.cs` explizit aus `Compile` entfernt.
4. Zwei Timeline-XAML-Verträge kompilierten nicht (`Border.IsTabStop`, statischer Focus-Handler). Behoben.
5. Native Tests verließen sich auf nicht erzeugte implizite `System.IO`-Usings. Behoben.
6. Render-Tests wurden an den bereits dokumentierten aktiven/terminalen Attempt-Vertrag und die unveränderliche Queue-ID-Signatur angepasst.

## Endbelege

- Python: 48/48 PASS, `T404-python-fault-injection.xml`, SHA256 `004818C5F43312A9E17E8E739B13AF390463ABEC562C52FDE6180BA285018D94`.
- Native WPF/Settings/Projekt: 9/9 PASS, `T404-settings-project-fault-injection.trx`, SHA256 `FBF321956F9CFC024B9F2BF271411ED5210540FF91DE5FF829F22F5E0B10E715`.
- Release-Build wurde im nativen Lauf bis zur erfolgreichen Erzeugung von `PBStudio.UI.dll` ausgeführt.
