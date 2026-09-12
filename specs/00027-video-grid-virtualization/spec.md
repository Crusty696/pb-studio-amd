# Echte Virtualisierung des Video-Kachelrasters

**Status:** SPECIFIED, 2026-09-07. **Quelle:** Nutzerauftrag Punkt 15; specs/00023-backlog-completion.

## Ziel und Geltungsbereich
Den genannten Backlogpunkt vollständig im realen App-Pfad schließen. Die folgenden Designentscheidungen sind Vorschläge dieser Spezifikation, keine behaupteten früheren Beschlüsse. Keine Implementations- oder Live-Abnahme wird hier behauptet.

## Befund
`PBStudio.UI/Views/VideoLibraryView.xaml` verwendet `ListBox VideoClipList` mit `WrapPanel` als ItemsPanel. Das vorhandene zweidimensionale Kachelraster muss erhalten bleiben. Brain-ADR `2026-04-24-timeline-architecture.md` befürwortet Virtualisierung für die Timeline, entscheidet aber nicht dieses Video-Grid.
## Anforderungen
- FR-001: Das Video-Grid bleibt ein automatisch umbrechendes mehrspaltiges Kachelraster mit bisherigen Thumbnails, Aktionen und Auswahl. Ein eindimensionaler Listen-Ersatz erfüllt die Aufgabe nicht.
- FR-002: Nur sichtbare Zeilen plus höchstens je zwei Pufferzeilen realisieren Container. Bei 1000 und 10000 Items bleibt Containerzahl bei gleicher Viewportgröße gleich begrenzt; Scrollen recycelt Container.
- FR-003: Resize, DPI-Wechsel (100/150/200 Prozent), leeres Grid, sehr schmale Breite und Start/Ende funktionieren ohne endlose Measure-Schleife oder abgeschnittene Zeilen.
- FR-004: Selection, Keyboard-/Page-Navigation, ScrollIntoView, Mehrfachauswahl und bestehende Drag/Context-Aktionen bleiben korrekt nach Sortieren/Filtern/Collection-Wechsel. Recycelte Kacheln zeigen keine alten Thumbnails oder Auswahlzustände.
- TR-001: Vorgeschlagene Entscheidung: eigener kleiner `VirtualizingPanel` mit `IScrollInfo` und `IRecyclingItemContainerGenerator`, feste vorhandene Kachelmaße; keine neue NuGet-Abhängigkeit. Eine paketbasierte Alternative braucht separate dokumentierte Entscheidung vor Installation.
## Abnahme
STA-Layouttests zählen realisierte Container und prüfen Indizes/Scrollgrenzen sowie Entfernen/Einfügen. Sichtbarer WPF-Lauf mit echtem Backend belegt Raster, Auswahl und ScrollIntoView; großer isolierter UI-Datensatz belegt Begrenzung (kein Import von 10000 produktiven Medien). Release-Build und Binding-Gate grün.

## Gates
Getrenntes Feature gemäß specs/00020-obj75-open-bug-fixes/residual-remediation-plan.md. Dessen OBJ-75-Release-Vorbedingung vor Implementierung anhand aktueller Marker prüfen; fehlendes Gate explizit beim Parent behandeln. Spec → Plan → Tasks → Implement → QC. Keine .completed/.qc-passed ohne reale Belege. Python 3.11/NumPy 1.26.4, DirectML/AMF und bestehende Recovery-Grenzen gelten.
