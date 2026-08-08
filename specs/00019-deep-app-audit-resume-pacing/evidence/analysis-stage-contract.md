# Analysis Stage Contract — OBJ-74

## Statuswerte

| Status | Bedeutung | Retry ohne `force` |
|---|---|---|
| `completed` | Payload vorhanden und validiert | nein |
| `partial` | nutzbarer Teil, Stage nicht vollständig | ja |
| `failed` | Versuch terminal fehlgeschlagen | ja |
| `interrupted` | Request/Projekt wurde unterbrochen | ja |
| `unavailable` | Capability/Quelle ehrlich nicht verfügbar | nein; nur mit `force` |
| `skipped` | in diesem Request nicht angefordert | nein; bestehende Wahrheit bleibt |
| fehlend | nie belegt oder Legacy-Zustand ohne Payload | ja |

## Kanonische Stages

- Audio: `beats`, `structure`, `spectral`, `key`.
- Video: `scenes`, `motion`, `embedding`, `colors`, `captions`, `audio_key`.
- Long-Mix-Chunk-Evidenz bleibt innerhalb `beats`; per-Chunk-Resume ist noch
  offen und wird nicht als abgeschlossen ausgegeben.

## Planung

```text
planned = explicitly_requested AND (force OR NOT valid_completed)
```

`force` rechnet nur explizit aktivierte Stages neu. Deaktivierte Stages sind
kein Löschsignal. `unavailable` wird ohne `force` als terminale Wahrheit
wiederverwendet, damit fehlende Hardware/Quelle keine Endlosschleife erzeugt.

## Merge-Regel

- Merge-Basis ist Cache oder persistierte DB-Wahrheit.
- Nur eine tatsächlich ausgeführte Stage darf ihre Payload-, Status- und
  Fehlerfelder ändern.
- `skipped`, fehlende Keys, `None` und Default-Leerwerte anderer Stages dürfen
  keine bestehende Payload überschreiben.
- Persistenz erfolgt DB-first; erst danach werden RAM-/Clipzustand und SSE als
  erfolgreich publiziert.
- Missing-File bricht mit HTTP 422 ab und schreibt keine Defaultanalyse.

## Payloadvalidität

- Audio Beats: BPM/BeatCount plus Listen für Beats, Energie, Downbeats und
  Trigger sowie Downbeat-Provenienz.
- Audio Struktur: mindestens ein Segment.
- Audio Spektral: Times plus Banddaten.
- Audio Key: nichtleerer Wert ungleich `Unknown`.
- Video Scenes: `scene_count == len(scenes)`.
- Video Motion: nichtleere Motion-Kurve.
- Video Embedding: `has_embedding`, Dimension 1152 und Samplezahl > 0.
- Video Colors: mindestens eine dominante Farbe.
- Video Captions: Tags plus echte Quelle.
- Video Audio-Key: nichtleerer Key.

## Unterbruch

- Audio persistiert nach jeder terminalen Stage einen merge-only Checkpoint.
- Ein kooperatives Stop-Signal verhindert Checkpoints und finalen Commit eines
  spät weiterlaufenden `to_thread`-Workers.
- Video persistiert bereits abgeschlossene Stages; nur aktive Stages werden
  `interrupted`. Projektwechsel verwirft den alten Kontext.
- Beide Pfade senden best-effort ein terminales `analysis_progress`-Event.

## Pacing-Anforderungen

- immer: Audio `beats`.
- Structure-Modus: Audio `structure`.
- Key-Modus: Audio `key` plus Video `audio_key`.
- Motion-Modus: Video `motion`.
- Semantic-Modus: Video `embedding`.
- Brain-only: optionale Achsen dürfen degradieren.

Pacing prüft Status und Payload vor dem Worker und liefert HTTP 422 mit
Clip-ID, Stage-Status und Payloadgültigkeit.
