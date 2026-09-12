# Plan: Echte Virtualisierung des Video-Kachelrasters

**Status:** PLANNED, 2026-09-07. **Basis:** spec.md.

## Voraussetzungen und Clarify
Spec gelesen; Umfang durch FR/TR-IDs begrenzt. Konkrete vorgeschlagene Entscheidungen stehen in spec.md. Kein Nutzerwunsch wird als bereits getestet ausgegeben. Vor Implementation prüft Parent das vorgelagerte OBJ-75-Gate sowie neue Architektur-/API-Entscheidungen; keine stillschweigende Umgehung.

## Architektur und Umsetzung
Vorhandene Kachelmaße und ListBox-Interaktionen erfassen. Panel berechnet Spalten aus verfügbarer Breite, Extent aus Gesamtzahl, sichtbaren Indexbereich aus Offset/Viewport. Nur diesen Bereich mit Puffern via ItemContainerGenerator realisieren, übrige Container recyclen. IScrollInfo implementiert Line/Page/Wheel/MakeVisible; BringIndexIntoView berücksichtigt Zeilenumbruch. Collection-/Breitenänderung invalidiert Extent und korrigiert Offset. Bestehende ListBox und Templates weiterverwenden.

## Dateien und Ownership
PBStudio.UI/Controls/VirtualizingWrapPanel.cs (neu); PBStudio.UI/Views/VideoLibraryView.xaml; PBStudio.UI.Tests (neue fokussierte STA-Tests). Der Implementierer besitzt nur ausdrücklich vom Parent zugewiesene Dateien. Tests erhalten eigene eindeutige Pfade; bestehende Änderungen anderer Agenten bleiben erhalten. Shared-Zonen und C#-Builds sequenziell, keine parallele Vollsuite.

## Verifikation
Realisierungsgrenze, Resize/DPI/Scroll/Selection/Mutation in STA; sichtbare echte Bibliothek plus isolierte 10000-Item-UI-Probe. Zuerst sinnvolle Regressionen, dann fokussierte Tests. Parent führt finale Python-Vollsuite und C#-Builds gemäß tatsächlich betroffenen Bereichen sowie sichtbare Live-QC aus. Test- und Live-Belege getrennt mit Laufzeit, Versionen und Resultaten speichern.

## Risiken und Rückkehrpfad
Unvollständige Consumer-Inventare, Nebenläufigkeit und Wire-Compatibility explizit prüfen. Änderungen in klaren Feature-Diffs reviewen; keine Produktionsdatenmigration. Bei Livefehlern Originalkonfiguration/Runtime geordnet wiederherstellen, Fehlerbeleg erhalten und Gate offen lassen. Rollback bedeutet gezielten Review des Feature-Diffs, niemals blindes Reset fremder Änderungen.

## Fertigstellung
Tasks erst nach belegter Umsetzung abhaken. .completed erst nach vollständiger Implementation, qc-report.md und .qc-passed erst nach bestandener tatsächlicher QC. Brain-Log durch Parent aktualisieren.

