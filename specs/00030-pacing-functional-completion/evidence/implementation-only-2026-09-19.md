# Pacing Implementation Receipt — Tests gesperrt

## Scope

- Produktiver KI-Regie-Pfad F-6.1 bis F-6.36
- Timeline-Grenze F-7.1 bis F-7.5
- Legacy `SyncMode`/`plan_cuts` unverändert ausgeschlossen

## Behobene Engine- und Servicefehler

- Nicht-endliche Zeitwerte werden vor Timeline-Commit abgelehnt.
- Effektive Min-/Max-Intervalle bleiben auch mit Clip-Variation hart begrenzt.
- Gültige Schnitte unter 0,5 Sekunden werden nicht mehr pauschal verworfen.
- `duration_limit` kann die echte Audiodauer nur kürzen, nie verlängern.
- Motion-Matching besitzt einen echten Ein/Aus-Schalter im Selector.
- Persistierte RAFT-Motionwerte werden konsistent auf 0..1 normalisiert.
- Brain-Fallback behält Zeitposition und Audiozustand.
- Canvas unterstützt 4-Stunden-Zeitmarken und registrierte Nicht-MP4-Clips.
- Zeitraster-Fallback respektiert Min/Max-Länge und Source-Dauer.
- Leere Generation überschreibt keine gültige Timeline.
- Engine-Zeitraster-, Canvas-, Key-, Stem-, Semantic- und Brain-Degradation werden sichtbar gemeldet.

## Behobene API- und Lifecyclefehler

- Pacing-Progress nutzt request-eindeutige IDs; fremde/stale Events werden ignoriert.
- Preview nutzt Projektkontext, reale Restdauer und hält den GPU-Lock bis Worker-Ende.
- Fehlgeschlagene Preview-Segmente führen nicht mehr zu irreführenden Teilvideos.
- Timeline-GET liest Timeline und Audio-Pfad atomar.
- Timeline-Validierung lehnt Startlücken, interne Lücken und negative Starts ab.
- Timeline-Update liest den Audio-Pfad atomar und bewahrt Projektisolation.
- Fehlgeschlagene Neugenerierung bewahrt die letzte gültige Cut-Liste.

## Behobene WPF-Fehler

- Generierte `clip_<id>`-IDs laden Motion- und Assetdaten korrekt.
- Brain-Vorschläge verwerfen stale Projektresultate und zeigen HTTP-Fehler statt falscher Leermeldung.
- Preview speichert lokale Timeline-Edits vor dem Renderauftrag.
- Backend-Ablehnungsgründe bleiben bei Timeline-Save und Preview sichtbar.
- Composite-Preview besitzt Start/Ende, Playback-Timer und korrekte Endbehandlung.
- Composite-Playback wird nicht beim ersten Playhead-Tick durch Einzelclip-Playback ersetzt.
- Timeline wird beim Edit sofort als unpersistiert markiert.
- Produktionsrender blockiert bei offenem, laufendem oder fehlgeschlagenem Timeline-Save.

## Verifikationsstatus

- Keine Tests ausgeführt nach Nutzeranweisung vom 2026-09-19.
- Kein Build ausgeführt.
- Kein GUI-/API-Live-Test ausgeführt.
- Zwei vom zuvor abgebrochenen Volltest übrig gebliebene pytest-Prozesse wurden gezielt beendet.
- T010 bis T014 bleiben offen; `.completed` und `.qc-passed` wurden nicht erzeugt.
