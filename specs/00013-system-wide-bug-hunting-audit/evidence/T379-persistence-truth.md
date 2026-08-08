# T379 – Persistenzwahrheit

Status: PASS
Datum: 2026-07-31
Requirement: FR-338

## Implementierung

- `PersistenceError` vereinheitlicht persistente Fehler und veröffentlicht redigierte Persistenzfehler über SSE.
- Audio-, Video-, Projekt- und Render-Mutationen bestätigen Erfolg erst nach erfolgreichem DB-/Datei-/Queue-Commit; RAM-Zustand wird danach aktualisiert.
- Repository-Updates und -Deletes verlangen exakt eine betroffene Zeile und behandeln No-op/Missing-Row als Fehler.
- Render-Resume und Queue-Lifecycle melden keinen RAM-/HTTP-Erfolg, wenn die Queue-Persistenz fehlschlägt.
- Video-Embeddings werden erst im synchronen Projekt-Commit geschrieben; Fehlschläge kompensieren ausschließlich die neue FAISS-ID, danach werden ältere Vektoren unter Erhalt der neuen ID bereinigt.

## Unabhängiger Review

Drei begrenzte Review-Runden wurden durchgeführt. Gefundene Probleme und Korrekturen:

1. Fehlende Rowcount-Prüfungen bei Update/Delete: korrigiert.
2. Falsche Alt-/Neuvektor-Reihenfolge und ungenaue Kompensation: auf exakte neue FAISS-ID umgestellt.
3. Render-Resume setzte RAM vor bestätigter Queue-Persistenz: Reihenfolge korrigiert.
4. Cancellation konnte zwischen Vector-Add und kanonischem Commit einen Ghost-Vektor hinterlassen: GPU-Worker liefert nur noch ein Pending-Embedding; Vector- und Analyse-Commit laufen ohne Await-Grenze im Projekt-Commit.

Finaler Review: PASS – kein bekannter Scheinerfolg und kein ungebundener neuer Video-Vektor im geprüften Ablauf.

## Verifikation

- Python-Compile-Sweep der neun geänderten Python-Dateien: PASS.
- `git diff --check`: PASS.
- Funktionale Fault-Injection-, Integrations- und Gesamttests sind planmäßig in T404–T410 gebündelt.

## SHA-256-Implementierungssnapshot

| Datei | SHA-256 |
|---|---|
| `backend/app_state.py` | `1f80ce5c880d12181998e06f6ac05bd7ed94530ca44267b7dd84a709fcf433ea` |
| `backend/routers/audio_router.py` | `c3146c026fe84c298908869051e48efe6928df21d967e827150b6f695451dd4f` |
| `backend/routers/video_router.py` | `f325202db08770ecbf2466adab34dc80d39e3e36e9844424d1794fa712f072ad` |
| `backend/routers/project_router.py` | `611c13d4a1d78427cbb67defc0ceba6e144884082f4af14525f1a7568da05012` |
| `backend/routers/render_router.py` | `19833b818801151efd31beb3eead2c7bfedecd6deec44aeadfe64a1ee217ca17` |
| `src/pb_studio/data/repositories/media_repository.py` | `e2e47d52b0d88908ddf87e7d6444473830a1bb111ca74e7d35d4439bf4e4c998` |
| `src/pb_studio/data/repositories/project_repository.py` | `d7595a7f9b9297ca9aaab5c10bbe5ed54a3b61fe3e7af27a02713dd8aa3082eb` |
| `src/pb_studio/data/vector_operation_outbox.py` | `1262011dee3bb1cd756a74282c83409b9fcc4c068cbf31266fd749ec2e2cffa2` |
| `src/pb_studio/rendering/render_queue.py` | `3a20e0f38f593f2bdac33d04cac9d7af93c0fde039736ea9186706be3a5b262a` |
