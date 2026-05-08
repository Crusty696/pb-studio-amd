# Obsidian-Export für PB Studio

> Dieser Ordner enthält Obsidian-fertige Notizen für deinen Vault `C:\Users\david\Brain`.

## Schnellster Weg (1 PowerShell-Befehl)

```powershell
xcopy "C:\Users\david\Documents\Pb_studio_AMD_version\obsidian-export\PB Studio" "C:\Users\david\Brain\PB Studio" /E /I /Y
```

Das kopiert die komplette Struktur in deinen Vault. Bestehende Dateien werden überschrieben (`/Y`).

## Was ist drin

```
PB Studio/
├── PB Studio - Status Dashboard.md     ← Map-of-Content (MoC), Hub für alle Snapshots
└── Status Reports/
    └── 2026-05-08 Gesamtstatus.md      ← Aktueller Pipeline-Audit
```

## Features

- ✅ Vollständiges Frontmatter (title, date, tags, aliases, cssclasses)
- ✅ Wikilinks zwischen Dashboard und Snapshot
- ✅ Mermaid-Diagramme für Architektur, Audio-, Video-, Pacing- und Render-Pipelines
- ✅ Obsidian-Callouts (`> [!success]`, `> [!example]`, `> [!todo]`, `> [!info]`, `> [!note]`)
- ✅ Tags: `#pbstudio`, `#status`, `#audit`, `#amd`, `#directml`, `#fastapi`, `#wpf`, `#dashboard`, `#moc`
- ✅ Tabellen für Router, IRON-Rules, VRAM-Budget, Views

## Nach dem Kopieren

In Obsidian öffnest du den Brain-Vault und siehst:
- Im Graph: das Dashboard ist als zentraler Hub mit Verbindung zum Snapshot sichtbar
- In Tags: `#pbstudio` listet beide Notizen
- Im Dashboard: Schnellzugriff-Tabelle, Status-pro-Bereich, IRON-Rules-Tracker, Snapshot-Historie

## Künftige Updates

Wenn ich später einen weiteren Snapshot erstelle (z.B. `2026-06-XX Gesamtstatus.md`), füge ich ihn:
1. Unter `Status Reports/` ein
2. Im Dashboard in der **Snapshot-Historie**-Tabelle ergänzt
3. Im Schnellzugriff verlinke ich den neuesten

So bleibt das Dashboard die einzige Notiz, die du dir merken musst.
