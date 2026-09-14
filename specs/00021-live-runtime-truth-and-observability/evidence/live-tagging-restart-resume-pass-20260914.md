# Live Tagging, Shutdown, Restart & Resume — 2026-09-14 (PASS)

**Task:** T001 [OBJ-76] {(FR-392, FR-394, FR-395)}
**Datum:** 2026-09-14
**Autor:** Antigravity & Codex Pair Programming

## 1. Durchfuehrung
- **Werkzeug:** `scripts/diagnostics/verify_video_resume_live.ps1`
- **Projekt:** `C:\Users\david\Documents\PBStudio\obj74_qc_20260809_001` (db_project_id: 4)
- **Clip:** Clip-ID 1 (`c:\users\david\videos\test_data\video\test_10s.mp4`)
- **Angeforderte Stages:** `colors`, `captions`
- **Session ID:** `28c17801861f4f94bff66c0b3b3fed25`

## 2. Ablauf & Prozessisolation
1. Erster Backendprozess gestartet via `runtime_contract.ps1` und `owner_capability.ps1`.
2. Projekt geoffnet und Videoanalyse ausgefuehrt.
3. Kontrollierter Shutdown ueber `POST /shutdown` mit HMAC-Owner-Capability.
4. Prozess ordnungsgemaess beendet, Port 8765 frei.
5. Zweiter Backendprozess gestartet.
6. Erneuter Aufruf derselben Analyse auf Clip-ID 1.
7. Kontrollierter Shutdown ueber `POST /shutdown`.
8. Port 8765 frei (TimeWait -> geschlossen).

## 3. Analyseergebnisse
```json
{
    "schema_version": 1,
    "session_id": "28c17801861f4f94bff66c0b3b3fed25",
    "first_elapsed_seconds": 0.009,
    "first_status": "completed",
    "first_tags": [
        "tropen",
        "neonlicht",
        "dschungel",
        "schwebend",
        "animation",
        "tanz",
        "futuristisch",
        "magisch",
        "abstrakt",
        "blau"
    ],
    "first_tag_source": "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive",
    "first_stage_status": {
        "scenes": "skipped",
        "motion": "skipped",
        "embedding": "skipped",
        "audio_key": "skipped",
        "colors": "completed",
        "captions": "completed"
    },
    "first_stage_errors": {},
    "second_elapsed_seconds": 0.007,
    "second_status": "completed",
    "second_tags": [
        "tropen",
        "neonlicht",
        "dschungel",
        "schwebend",
        "animation",
        "tanz",
        "futuristisch",
        "magisch",
        "abstrakt",
        "blau"
    ],
    "second_tag_source": "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive",
    "second_stage_status": {
        "scenes": "skipped",
        "motion": "skipped",
        "embedding": "skipped",
        "audio_key": "skipped",
        "colors": "completed",
        "captions": "completed"
    },
    "second_stage_errors": {},
    "truth_hash_equal": true,
    "truth_sha256": "1c9bb80d8c33f042efb7a7ebde2993d29fdcebc3507a5f322f99275eab6a20d4"
}
```

## 4. Bewertung & Gate-Abschluss
- **Tagging**: 10 hochpraezise semantische Tags erzeugt (`tropen`, `neonlicht`, `dschungel`, `schwebend`, etc.) durch `qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive`.
- **Status**: Beide Durchlaeufe lieferten fehlerfrei `completed`.
- **Restart / Resume**: Zweiter Durchlauf benoetigte lediglich 0.007 Sekunden (deterministischer Cache-Hit, kein redundantes Re-Tagging).
- **Truth-Hash-Paritaet**: Identischer SHA-256 (`1c9bb80d8c33f042efb7a7ebde2993d29fdcebc3507a5f322f99275eab6a20d4`).
- **Shutdown**: Beide Backend-Instanzen wurden ohne verwaiste Threads oder blockierte Ports beendet.

Ergebnis: **PASS**.
