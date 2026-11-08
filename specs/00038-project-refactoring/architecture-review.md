# Architekturprüfung — 2026-10-30

## Methode

Drei unabhängige lesende Analysen: WPF, Backend/Core/Persistenz, Medienpipeline. Direkte Aufrufer und vorhandene Tests geprüft. Größenangaben und Kopplung sind Wartbarkeitssignale, keine Laufzeitmessungen.

## Umgesetzte Schnitte

| Grenze | Vorher | Nachher |
|---|---|---|
| API | ApiClient.cs: 1618 Zeilen inklusive DTOs | Zentraler Transport: 351 Zeilen; sieben Domänen-Partials und getrennte Response-Modelle |
| Audio-Refresh | Clear und Neuerzeugung aller Modelle | ID-basierter Abgleich innerhalb desselben Projektkontexts |
| Timelineabschluss | Export instanziiert PacingService für private Methode | Gemeinsamer Finalizer mit injizierter Dauerprobe; kompatibler Service-Delegator |
| Anchor-Lesen | Pacing-Router importiert Projekt-Router | Gemeinsames backend/project_anchors.py; bisheriger Import bleibt verfügbar |

## Weitere Kandidaten und Grenzen

| Bereich | Befund | Nächste sichere Grenze / Risiko |
|---|---|---|
| Audio | streaming_analyzer.py: Checkpointidentität/Validierung/Serialisierung vermischt mit DSP | Checkpointvertrag separat charakterisieren; Chunkzeit und Energy-only-Status bewahren |
| Audio-Router | Stemmarker und Teilfortschritt im HTTP-Router | Artefaktverwaltung mit identischem Lock/atomarer Veröffentlichung; separator.py geschützt |
| Pacing | Cached/frische Trigger duplizieren Gewichtung und Energie-Peak-Gruppierung | Zeitbasen unterscheiden sich bereits; keine naive Zusammenlegung |
| Rendering | Belegwriter, Segmentmanifest und Prozessablauf vermischt | Receiptimmutabilität, Run-/Jobidentität und Fortschrittsjournal getrennt testen |
| Timeline-UI | Bearbeitung, Persistenz, Brain-Erklärung in großem VM | Partialaufteilung möglich; Selektionsidentität und Persistence-Gate erhalten |
| Video-UI | Analyse, Import und Bibliotheksladung im VM | Erst partielle Ergebnisse und verspätete SSE-Ereignisse charakterisieren |
| AppState | Lifecycle, Locks, Persistenz und Rehydrierung kombiniert | Hohe Zustandskopplung; kein mechanischer Split ohne Recovery-/Projektwechselbelege |
| Chat | Toolregistry vereint Schemas, Transport und Backend-Authkopplung | Authänderung getrennte Sicherheitsentscheidung; Patchstellen erhalten |
| Vision/Embeddings | Umfangreiche bereits vorhandene lokale Änderungen | Nicht durch diese Refaktorierung überschreiben; Spec 00037 bleibt eigenständig |

Diese Kandidaten sind nicht umgesetzt. Die vier aktuellen Schnitte sind keine Behauptung einer abgeschlossenen Gesamtmodernisierung.

## Laufzeitgrenze

Am 30.10.2026: kein PBStudio.UI-Prozess und kein Listener auf 8765 beobachtet. Produktions-Recovery: CURRENT und RUNTIME_DIRTY referenzieren dieselbe Generation vom 25.09.2026; Journal restore/COMMITTED. backend/recovery_bootstrap.py ruft für diesen Fall _recover_generation auf. Produktionsstart deshalb nicht als harmlose GUI-Prüfung behandelt; keine Markeränderung oder Datenwiederherstellung ausgeführt.
