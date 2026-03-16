# Agent 4 – Release / Packaging / Smoke Hardening Report

## Scope
Release-/Packaging-/Smoke-Härtung für PB Studio AMD: Publish-Scripts, Launch-Path, Smoke-Verifikation, Artefakt-Konsistenz, kleine robuste Fixes mit echtem Build/Publish/Smoke-Nachweis.

## Praktisch durchgeführt

### 1) Release Build / Publish verifiziert
- `dotnet build .\PBStudio.UI\PBStudio.UI.csproj -c Release` → **PASS**
- `./publish.ps1 -Mode framework -Configuration Release -Runtime win-x64 -VersionTag agent4-hardened-20260313` → **PASS**
- Verifiziertes Artefakt:
  - `C:\Users\david\Dokumente\Pb_studio_AMD_version\artifacts\publish\framework\Release\win-x64\agent4-hardened-20260313\PBStudio.UI.exe`

### 2) Release Smoke verifiziert
- `./verify_release_smoke.ps1` → **PASS**
- Frischer isolierter Smoke-Run erzeugte:
  - Projekt: `C:\Users\david\Documents\PBStudio\ReleaseSmoke_20260313_050912`
  - Render-Cancel-Output: `C:\Users\david\Documents\PBStudio\ReleaseSmoke_20260313_050912\output\release_smoke_render_20260313-050921.mp4`
- Verifizierte Schritte:
  - Backend startup / health
  - Projekt anlegen
  - Audio-/Video-Import
  - Audio-Analyse + Waveform + Beats
  - Pacing / Timeline-Generierung
  - Save
  - Render Start + Cancel

## Umgesetzte kleine, aber sinnvolle Härtungen

### A) `launch.ps1` deterministischer gemacht
Problem:
- Unter `artifacts\publish\<mode>` lagen neben versionierten Releases noch alte Flat-Artefakte direkt im Mode-Root.
- Der Launcher fiel rekursiv auf „irgendein EXE finden“ zurück. Das war funktional, aber für echten Ship-Betrieb unnötig fragil.

Fix:
- Launcher bevorzugt jetzt zuerst:
  1. `latest.txt`
  2. versionierte Releases unter `Release\<runtime>\<tag>\PBStudio.UI.exe`
  3. nur noch als letzter Fallback Flat-Root-EXE
- Beim Flat-Fallback wird explizit gewarnt.

Wirkung:
- Launch-Pfad ist deterministischer und weniger abhängig von Altlasten im Publish-Root.

### B) `publish.ps1` um Release-Metadaten ergänzt
Fix:
- `latest.json` wird jetzt geschrieben mit:
  - Mode
  - Configuration
  - Runtime
  - VersionTag
  - `flatOutput`
  - absolutem und relativem Output-/EXE-Pfad
  - UTC-Zeitstempel
- Zusätzlich Warnung, wenn Legacy-Flat-Artefakte im Mode-Root erkannt werden.

Verifiziert:
- `artifacts\publish\framework\latest.json` vorhanden und korrekt befüllt.

Wirkung:
- Artefakt-Auflösung wird nachvollziehbarer.
- Externe Tools / spätere Packaging-Schritte können stabil auf Metadaten zugreifen.

### C) `verify_release_smoke.ps1` isolierter und robuster gemacht
Problem:
- Ein Smoke-Run gegen einen bereits laufenden, fremd gestarteten Backend-Prozess schlug transient fehl (`connection closed` bei `/pacing/generate`).
- Das machte den Smoke-Run unnötig zustandsabhängig.

Fix:
- Smoke-Script startet standardmässig jetzt **einen isolierten eigenen Backend-Run**:
  - vorhandenes Backend wird zuerst sauber beendet
  - danach wird ein frischer Backend-Prozess für den Smoke gestartet
- `Post-Json(...)` retryt transiente POST-Fehler einmal und bricht klarer ab, wenn das Backend wirklich weg ist.
- Optional kann man mit `-ReuseExistingBackend` wieder das alte Verhalten erzwingen.

Wirkung:
- Smoke ist reproduzierbarer, weniger flakey und näher an einem echten Release-Gate.

### D) Realen Build-Blocker gefixt: `TimelineViewModel.cs`
Gefunden:
- Release-Build war zwischenzeitlich real rot wegen `CS1009 Nicht erkannte Escapesequenz`.
- Ursache: falsches Escape in TimeSpan-Formatstring innerhalb `SelectedPreviewRange`.

Fix:
- `mm\:ss` im interpolierten String korrekt escaped.

Verifikation:
- Rebuild danach wieder **0 Fehler / 0 Warnungen**.

## Artefakt-Konsistenz – aktueller Stand

### Gut
- Versionierte Framework-Releases funktionieren.
- `latest.txt` zeigt auf den aktuellen versionierten Build.
- `latest.json` dokumentiert den aktuellen Publish-Zustand maschinenlesbar.
- Launcher bevorzugt jetzt die versionierte Struktur.

### Noch unsauber
- Unter `artifacts\publish\framework` und teils anderen Modi liegen weiterhin alte Flat-Artefakte direkt im Mode-Root.
- Sie blockieren den Release nicht mehr direkt, weil der Launcher jetzt sauber priorisiert.
- Sauber wäre später ein expliziter Cleanup-/Archive-Schritt für Legacy-Flat-Outputs.

## Release-Empfehlung
**Empfehlung: GO für framework-dependent Windows Beta / internes Release.**

Begründung:
- Release-Build aktuell grün
- Framework-Publish frisch verifiziert
- Isolierter Release-Smoke frisch grün
- Launch-/Artifact-Auflösung robuster als vorher
- Keine neue kritische Packaging-Blockade gefunden

## Offene Risiken / Restarbeiten
1. **Legacy Flat Publish-Artefakte im Mode-Root**
   - jetzt technisch entschärft, aber noch Cleanup-Schuld
2. **Smoke hängt an lokal vorhandenen Sample-Assets**
   - aktuell okay für lokale Release-Verifikation, aber noch kein vollständig asset-unabhängiges CI-Szenario
3. **Nur Framework-Pfad frisch verifiziert**
   - self-contained / single-file wurden in diesem Lauf nicht neu hart nachverifiziert
4. **Backend-Isolation im Smoke stoppt vorhandenes Backend standardmässig**
   - für Release-Gate gut, aber man sollte das Verhalten kennen

## Kurzfazit
Der echte Ship-Zustand ist robuster als vor diesem Lauf:
- Build wieder grün
- Framework-Publish frisch grün
- Release-Smoke frisch grün
- Launch-Path nicht mehr unnötig abhängig von alten Flat-Artefakten
- Smoke-Script reproduzierbarer durch isolierten Backend-Start

Wenn heute ein Windows-Beta-Artefakt raus soll, ist der **framework-dependent Publish `agent4-hardened-20260313`** der belastbare Kandidat.
