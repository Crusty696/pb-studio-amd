# T408 — GUI-Wahrheit

Status: PASS
Datum: 2026-08-01
Ausgangs-SHA: `f05df00fa70f8fe52b950d990377eea1dfb6e6f5`
Release-Binary SHA-256: `6243cff3c190d20ee30446cdce043b83269bc6877b197fed894fcca93efb802a`

## Autoritative Matrix

- 56/56 Renderings PASS: 14 Views bei 1280×720 und 1400×900 effektiv,
  jeweils mit 96 und 144 DPI.
- 14/14 Renderings PASS: 14 Views bei 1280×720 effektiv mit 192 DPI.
- Null unbenannte sichtbare interaktive Controls, null erkannte Clippings,
  null flache/leere Renderings und vollständige Tab-Auswahl.
- Die Matrix emuliert den WPF-DPI-Wechsel per `WM_DPICHANGED`; physische
  Fenstergröße und effektive Größe sind je Lauf im JSON gespeichert.
- 1400×900 effektiv bei 192 DPI würde 2800×1800 physische Pixel benötigen
  und übersteigt den vorhandenen 2560×1440-Monitor. Deshalb wurde 200 % bei
  1280×720 geprüft; Auflösung und DPI sind vollständig als Achsen abgedeckt.

Belege: `T408-gui-authoritative-100-150/`,
`T408-gui-authoritative-200/`, `T408-T409-runtime-context.json`.

## Fehler- und destruktive Zustände

- Backend-Ausfall sichtbar: Warntext und Screenshot PASS; nach Neustart ist
  der Warntext nachweislich verschwunden.
- Neun destruktive UI-Aktionen besitzen eindeutige UIA-Namen; Hirn-Bestätigung
  und Anchor-Löschen sind ohne vorangehenden Zustand deaktiviert.
- Der echte kompilierte `DialogService` zeigte den Löschdialog mit exakter
  Anzahl, Ja/Nein, Standardfokus auf Nein. Nein schloss den Dialog; kein
  Datenmutationspfad wurde aufgerufen.

Belege: `T408-backend-error-state/`, `T408-backend-recovery/`,
`T408-destructive-ui-state-final.json`, `T408-delete-confirmation/`.

## Geschlossene visuelle Findings

- Anchor: Position/Dauer getrennt und Tabellenkopf „Zeit“ vollständig.
- Timeline: „Trigger“ und „Dauer“ vollständig.
- Export: „RENDER LOG“ und Eintragszahl getrennt.
- Autoritative Normal-, 200-%- und High-Contrast-Screenshots wurden nach der
  letzten Korrektur erneut erzeugt und visuell kontrolliert.

## Verifikation

- WPF Release: 0 Warnungen, 0 Fehler.
- 48/48 gezielte Python-Verträge PASS; ein genehmigter Umgebungsskip.
- 28/28 native C#-Tests PASS.
- Alle View-XAML-Dateien XML-valide; `git diff --check` PASS.
