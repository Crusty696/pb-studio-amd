# Audit: State + DB + Cache (Deep)

**Datum:** 2026-05-11
**Scope:** `backend/app_state.py`, `src/pb_studio/data/`, `src/pb_studio/storage/`, `src/pb_studio/brain/`, FAISS Vector-Store, sqlite-vec
**Modus:** Read-only Audit (kein Code-Fix in dieser Session).
**Trigger:** User-Auftrag nach State+DB+Cache Drift, Race-Conditions, Roundtrips.

---

## Kurz-Verdict

State-Layer ist solide thread-safe (RLock + Snapshot-Copies), aber an mehreren Stellen liegt **Cache↔DB-Drift**: 5 Audio-Felder werden persistiert ohne dass irgendwer sie nach Reload nutzt (siehe AUDIT_DATA_FLOW_2026-05-09), zusätzlich **3 Felder werden NIE persistiert** (stems_paths, thumbnail_available, audio_clip.beats key) und gehen beim Projektwechsel verloren. **VectorStore-Singleton-Design ist broken** — verschiedene `index_name` invalidieren sich gegenseitig. **FAISS-Tabelle `vector_map` existiert im Schema aber wird NIE beschrieben**. Brain-State-Connection wird beim Project-Close **nicht freigegeben** → Cross-Project-Leak.

Top 5 unten. Vollständige Liste: **17 Findings**.

---

## Top 5 (Severity)

### 1. **HIGH** — `stems_paths` verschwindet nach Reload (Cache-only Persistence)
**Datei:** `backend/routers/audio_router.py:495-506`, `backend/app_state.py:687-715`
```python
# audio_router.py — Stem-Separation läuft synchron, schreibt aber NUR in-memory:
if stems_paths:
    clip["stems_paths"] = stems_paths
    state.set_audio_clip(request.clip_id, clip)   # ← in-memory only
```
**Befund:** `set_audio_clip` aktualisiert NUR `state.audio_clips[id]`. Es gibt KEIN `persist_audio_clip`/`update_audio_analysis` für `stems_paths`. Nach Projekt-Close+Open ist `stems_paths` weg → User muss Demucs neu laufen lassen (mehrere Minuten + VRAM).

**Konsequenz:** `pacing_router.py:488` liest `ac_data.get("stems_paths")` — nach Reload immer `None` → `use_stem_pacing=True` Branch fällt zurück auf Standard-Pacing ohne Warnung an User.

**Symmetrie-Bug:** `persist_audio_clip` (Z. 706) baut `meta`-Dict ohne `stems_paths`-Key. `load_from_db` (Z. 825-840) baut Audio-Clip-Dict ohne `stems_paths`-Key.

---

### 2. **HIGH** — `vector_map`-Tabelle ist totes Schema (FAISS ↔ SQLite-Drift)
**Datei:** `src/pb_studio/data/database_core.py:59-66`, `backend/routers/video_router.py:751-758`
```sql
CREATE TABLE IF NOT EXISTS vector_map (
    faiss_id INTEGER PRIMARY KEY,
    media_id INTEGER,
    segment_start REAL, segment_end REAL,
    description TEXT,
    FOREIGN KEY(media_id) REFERENCES media(id) ON DELETE CASCADE
);
```
Kein einziger `INSERT INTO vector_map` im gesamten Code. FAISS-Metadata liegt komplett in `video_index_meta.json` (Plain JSON-File) — **kein Foreign-Key-Schutz beim Media-Delete**.

**Konsequenz beim Delete:** `state.delete_audio_clip` / `delete_video_clip` löscht Media-Row → CASCADE würde `vector_map`-Eintrag löschen, ABER FAISS-Index behält den embedding-Vector **dauerhaft** (FAISS-IDs sind monoton, kein Tombstone). Bei jedem Re-Import wachsen FAISS-Files unbegrenzt.

**Memory-Leak-Pfad:** Project-Delete via `ProjectRepository.delete_project` löscht Projects ON DELETE CASCADE → alle Media weg → FAISS bleibt voll mit Orphan-Vektoren. Search liefert dann Hits mit `clip_id`, die nicht mehr in der DB existieren.

---

### 3. **HIGH** — VectorStore-Singleton invalidiert sich selbst bei verschiedenen `index_name`
**Datei:** `src/pb_studio/data/vector_store.py:21-49`
```python
def __new__(cls, index_name: str = "main_index", dimension=None):
    with _vs_lock:
        if cls._instance is None or cls._instance_index_name != index_name:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instance = instance
            cls._instance_index_name = index_name
```
**Inkonsistente Index-Namen:**
- `video_router.py:751` → `VectorStore(index_name="video_index")`
- `semantic_matcher.py:162` → `VectorStore(index_name="main_index")`

**Konsequenz A — Pacing findet keine Embeddings:** Video-Analyse schreibt in `video_index.faiss`. SemanticMatcher liest aus `main_index.faiss` → leerer Index → "VectorStore-Suche fehlgeschlagen / Zufallsauswahl". Das passt zum Audit-Data-Flow-Befund (Video-Embeddings nur bedingt genutzt).

**Konsequenz B — Singleton-Thrashing:** Wenn zwei verschiedene Module abwechselnd `VectorStore("video_index")` und `VectorStore("main_index")` aufrufen, wird der jeweils andere Index aus dem Speicher verdrängt + neu von Disk geladen. **atexit-Handler werden bei jedem `__new__` neu registriert** → bei intensiver Nutzung Memory-Leak im atexit-Stack.

**Konsequenz C — Singleton heißt Singleton ist aber keiner:** Tests, die parallel `VectorStore("test_index")` und Production-Code parallel laufen lassen, sehen sich gegenseitig. Im Test-Verzeichnis liegen `test_index.faiss` + `test_index_meta.pkl.bak` als Beweis dass das in der Vergangenheit passiert ist.

---

### 4. **HIGH** — Brain-State-Connection wird beim Project-Close NICHT geschlossen → Cross-Project-Leak
**Datei:** `backend/routers/project_router.py:306-321`, `backend/_brain_singleton.py`
```python
@router.post("/close")
async def close_project(state: AppState = Depends(get_app_state)) -> StatusResponse:
    state.reset()  # leert In-Memory, schließt aber Brain-state.db NICHT
```
Es gibt keinen Aufruf von `BrainService.get().bind_project_state(None)` oder `BrainService.reset_singleton()` beim Close. `BrainService.state_conn` bleibt auf `<old_project>/state.db` gebunden. Wenn der User danach `/brain/suggest` oder `/brain/feedback` schickt **ohne** ein neues Projekt zu öffnen, schreibt das Brain weiterhin in das **alte** state.db.

**Konsequenz:** Feedback-Events landen im falschen Projekt. WeightStore (global in `%APPDATA%/PB_Studio/brain/weights.db`) bleibt OK — der Leak ist lokal je Projekt-state.db. UI-Audit für Brain müsste auch verifizieren ob `current_project=None` Brain-Endpoints sauber blockt — `bind_project_state` mit `None` wirft `state_conn is None` 409, aber der Wechsel-Pfad fehlt.

**Sekundär:** `BrainService.bind_project_state` schließt zwar `self.state_conn` bevor es neu öffnet (Z. 59-63), aber nur wenn `bind_project_state` erneut aufgerufen wird. Bei Close ohne Folge-Open bleibt die Connection offen bis Prozess-Ende.

---

### 5. **MEDIUM** — Cache-Schema-Drift: `audio_analysis_cache["beats"]` vs `audio_analysis_cache["beats_json"]`
**Datei:** `backend/app_state.py:514` vs `:857`
```python
# update_audio_analysis schreibt nach Analyse:
cache_update["beats_json"] = ai_data["beats_json"]   # ← parsed beats-Liste

# load_from_db schreibt nach DB-Reload:
tmp_audio_analysis[clip_id] = {
    ...,
    "beats": beats,   # ← gleiche Daten, anderer Key
}
```
**Konsequenz:** Code, der `analysis.get("beats")` liest (`audio_router.py:381` `/audio/beats/{clip_id}`), funktioniert nur **nach Reload aus DB**. Direkt nach Live-Analyse fehlt der Key — fallback `[]` → leere Beat-Liste in der UI obwohl gerade analysiert.

Symmetrie-Lücke ist auch sichtbar in `update_audio_analysis`: `cache_update["beats_json"]` ist die Liste, der Key-Name suggeriert aber JSON-String. Nomenklatur-Bug + Funktional-Bug in einem.

---

## Vollständige Findings-Liste (17)

### State-Management (`app_state.py`)
| # | Severity | Befund |
|---|---|---|
| 1 | HIGH | `stems_paths` nur in-memory, nie in DB (siehe Top 5 #1) |
| 2 | MEDIUM | `audio_analysis_cache` Key-Drift `beats` vs `beats_json` (Top 5 #5) |
| 3 | MEDIUM | `thumbnail_available` bei `load_from_db` immer `False` (Z. 875) — kommentiert als bewusst, aber UI muss explizit reagieren; aktuell kein Trigger sichtbar |
| 4 | LOW | `video_clips["tags"]: []` bei Reload (Z. 876) während `video_analysis_cache["tags"]` die echten Tags hat → zwei Quellen für dasselbe Feld |
| 5 | LOW | `update_video_clip` (Z. 120-137) nicht-persistent, kein DB-Sync (dokumentiert) — aber UI ruft `/video/thumbnails/{id}` immer, riskiert nichts. |
| 6 | LOW | `register_video_clip` setzt `_video_next_id` zweimal (Z. 395 + 410). Redundant, harmlos. |
| 7 | LOW | `state._state_lock` wird in `render_router.py:225` + `project_router.py:314` direkt vom Router benutzt → Leaky Abstraction. Sollten public methods sein. |
| 8 | LOW | `delete_audio_clip` / `delete_video_clip` machen DB-Delete **außerhalb** des state-locks (Z. 162-173) → race-window: ein paralleler Reader kann ein in-memory bereits gelöschtes clip noch in der DB sehen. Praktisch unkritisch (single-user), strukturell suboptimal. |

### DB-Layer (`database_core.py`, `repositories/*`)
| # | Severity | Befund |
|---|---|---|
| 9 | HIGH | `vector_map`-Tabelle ist totes Schema, FAISS-Drift (Top 5 #2) |
| 10 | MEDIUM | Zwei parallele Migrations-Frameworks: (a) `SCHEMA_MIGRATIONS`-Tuple in `database_core.py` (versioniert via `schema_migrations`-Tabelle), (b) `render_queue.py:177` macht `CREATE TABLE IF NOT EXISTS` **direkt im `_ensure_schema`** ohne Eintrag in den Migrations-Tracker. Bei Schema-Änderungen Risk of split-brain. Empfehlung: render_queue als Migration `3` registrieren. |
| 11 | MEDIUM | `ConfigManager._instance` ist Singleton, aber `_config` und `_instance` sind Class-Attributes (Z. 12-13). Bei zwei Threads, die parallel `ConfigManager()` instanziieren **bevor** `_instance` gesetzt ist, gibt es eine race (kein Lock). Für Desktop-App akzeptabel, aber kein Standard-Singleton. |
| 12 | LOW | `_apply_migrations` ruft `with conn:` (implicit transaction) + danach `conn.execute("INSERT INTO schema_migrations ...")` innerhalb derselben transaction. Atomicity ✅ — explicit comment im Code dokumentiert das. |
| 13 | LOW | `MediaRepository._retry_on_database_lock`: sehr saubere Implementierung — 5 retries, exponential backoff, getrennte Behandlung von `IntegrityError` vs `OperationalError`. Audit-positiv. |

### Vector Store + Brain Stores
| # | Severity | Befund |
|---|---|---|
| 14 | HIGH | VectorStore-Singleton-Thrash + zwei Index-Names (Top 5 #3) |
| 15 | HIGH | Brain-state.db bleibt nach Close gebunden (Top 5 #4) |
| 16 | MEDIUM | `EmbeddingCache.store()` (`embedding_cache.py:87-120`) speichert `.npy`-File **außerhalb** der SQLite-Transaction. Bei Crash zwischen `np.save` und `INSERT OR REPLACE` → orphan-File auf Disk ohne DB-Eintrag. Bei Crash umgekehrt: DB-Eintrag zeigt auf nicht-existente File (mitigiert durch `lookup()`-Check `if not path.is_file(): return None`). |
| 17 | MEDIUM | Brain `embeddings.db` Schema (`migrations/embeddings/001_initial.sql`) hat **audio_embeddings DIM=512** und **video_embeddings DIM=768** — aber `vector_store.py` (FAISS) nutzt **DIM=1152 (SigLIP SO400M)**. Zwei separate Embedding-Stacks mit verschiedenen Dimensionen, kein gemeinsamer Konsument-Path. Audit-positiv: `EmbeddingRepository._coerce_embedding` validiert dim und wirft `ValueError` — keine Silent-Drift möglich. Aber: ist beabsichtigt? In `embeddings.db` sieht es nach SigLIP-1 (768) vs neuem SigLIP-2 SO400M (1152) aus. **Möglicher Code-Path-Mismatch**, sollte verifiziert werden. |

---

## Antworten auf die Audit-Fragen

### app_state
- **Thread-Safety:** Alle `set_*` / `update_*` / `get_*` Methoden nutzen `_state_lock` (RLock). ✅ Sauber. Nur die internen DB-Calls in `delete_audio_clip` / `delete_video_clip` laufen außerhalb des Locks (Finding #8).
- **Caches:** `audio_clips`, `audio_analysis_cache`, `video_clips`, `video_analysis_cache`, `current_timeline`, `render_tasks`, `cancel_flags`. Konsistenz: gemischt — analysis_cache ist **read-after-write** konsistent, aber `cache["beats_json"]` vs `cache["beats"]` (Finding #2).
- **Partial vs Full Update:** `update_audio_analysis` / `update_video_analysis` machen sauberes partial-update (nur `None`-Felder bleiben). ✅ Dokumentiert.
- **dict-keys int vs str:** Alle Clip-Caches verwenden `int`-Keys konsistent. FAISS-`metadata.json` wird beim Load explizit int-konvertiert (`vector_store.py:67-70`). ✅
- **Memory-Leaks:** `render_tasks` wird auf 50 Tasks gecappt (Finding #7 verweis), `cancel_flags` werden in render_router gepoppt. `audio_clips`/`video_clips` wachsen pro Projekt — `reset()` leert sie bei `close()`. ✅ Beschränkt.

### DB
- **SQLAlchemy:** ❌ NICHT verwendet. Raw `sqlite3` mit Custom-Migration-Tracker. (Anders als CLAUDE.md "SQLite (SQLAlchemy)" — Brain-Status ist veraltet.)
- **Alembic:** ❌ Nein. Eigenes `SCHEMA_MIGRATIONS`-Tuple (Finding #10).
- **Felder im Memory aber nicht in DB:** `stems_paths` (Finding #1), `thumbnail_available` (bewusst, Finding #3), Audio `beats`-Cache-Key (Finding #2 partial).
- **JSON-Spalten vs separate Tabellen:** Heavy JSON-Use — `media.metadata_json`, `media.ai_data_json`, `projects.json_data`. Pro Reload muss alles geparst werden. Vorteile (Schema-Flex) vs Nachteile (keine Indexes auf JSON-Inhalt) — für Desktop-App OK.
- **Foreign Keys + CASCADE:** Aktiv (`PRAGMA foreign_keys=ON`). `projects→media→vector_map` Kaskade definiert. Aber `vector_map` bleibt leer (Finding #9) → CASCADE läuft auf leere Tabelle.
- **Transactions:** `transaction(immediate=False)` Default in `DatabaseCore`, mit `BEGIN IMMEDIATE` Option für Write-Heavy-Pfade. `add_media` nutzt explizit `immediate=True`. Rollback bei Exception verifiziert.

### Vector Store
- **FAISS Index-Location:** `<data_dir>/<index_name>.faiss` + `<index_name>_meta.json`. `<data_dir>` aus `paths.db_path.parent` (config_manager). Aktuell `./data/`.
- **Rebuild bei Changes:** ❌ Kein Rebuild. Append-only. Delete einer Media-Row entfernt Vektor NICHT (Finding #9).
- **Embedding-Dim:** Default 1152 (SigLIP SO400M) ✅. Auto-detect bei leerem Index, Hard-Fail bei nicht-leerem Index mit Mismatch. Saubere Logik.
- **sqlite-vec:** Ja, separater Stack in `EmbeddingRepository` für Brain-Embeddings (DIM 512 + 768). Nicht verbunden mit FAISS-Stack. Finding #17.

### Cache vs DB pro Feld
| Feld | Memory→DB | DB→Cache (Reload) | Project-Switch geleert |
|---|---|---|---|
| bpm | sync (update_audio_analysis) | ✅ | ✅ via reset() |
| key | sync | ✅ | ✅ |
| beats | sync (key=`beats_json`) | ✅ (key=`beats`) | ✅ — aber Key-Drift Finding #2 |
| energy_curve | sync | ✅ | ✅ |
| structure_segments | sync | ✅ | ✅ |
| spectral_data | sync | ✅ | ✅ |
| subtrack_segments | sync | ❌ NICHT in load_from_db | ✅ — verloren bei Reload |
| tempo_curve | sync | ❌ NICHT in load_from_db | ✅ — verloren bei Reload |
| stems_paths | ❌ NIE sync | ❌ | verloren bei Reload (Finding #1) |
| scene_count | sync | ✅ | ✅ |
| avg_motion | sync | ✅ | ✅ |
| scenes, motion, dominant_colors, tags | sync | ✅ via video_analysis_cache | ✅ |
| embedding_dim, embedding_samples | sync | ✅ | ✅ |
| thumbnail_available | nie persistent | reset to False | ✅ (bewusst) |
| audio_hash | sync (meta+file_hash) | ✅ | ✅ |

**Persistenz-Lücken-Total:** `subtrack_segments`, `tempo_curve`, `stems_paths` werden nicht aus DB nach Reload restored.

### Brain-Modul
- **3-DB Hirn-Store DBs:** ✅ `weights.db` + `patterns.db` + `embedding_cache.db` unter `%APPDATA%\PB_Studio\brain\` (global). Plus pro Projekt: `state.db` mit `timelines + timeline_cuts + feedback_events` (`storage/migrations/state/`).
- **Beta-Bernoulli Persistence:** `axis_weights`-Tabelle mit `(axis, context_level, context_key) PRIMARY KEY` + `positive_count, negative_count`. WeightStore in-memory Cache (8000 slots LRU) wird auf `update()`/`reset()` invalidiert via version-bump. ✅ Robust.
- **WeightStore Schema:** OK, sehr clean. Atomic-Updates via `ON CONFLICT DO UPDATE`. FeedbackLogger nutzt explizite `BEGIN`/`COMMIT` für Multi-Bucket-Atomicity (85 Updates pro Klick).

---

## Memory-Cache vs DB-Drift — Zusammenfassung

**Drift-Felder:** 3 nicht persistent (stems_paths, subtrack_segments, tempo_curve in load_from_db)
**Tot-Felder (in DB ohne Konsument):** 5 audio + 3 video (siehe AUDIT_DATA_FLOW_2026-05-09).
**Schema-Mismatch:** vector_map (tote Tabelle), FAISS index_name (Pacing↔Video uneinig), beats vs beats_json (Key-Drift im Cache).

---

## Race-Conditions — Status

Insgesamt **akzeptabel** für Single-User-Desktop:
- `_state_lock: RLock` schützt alle in-memory mutations.
- `_lock: RLock` extra für ID-counters.
- DB-Layer: thread-local connections (`threading.local()`).
- FAISS: eigenes `_lock` + atomic `os.replace`.
- WeightStore: lock + version-counter.

**Schwachstellen:**
- `delete_*_clip` releast lock vor DB-Call (Finding #8).
- VectorStore-Singleton-Thrash (Finding #14) hat impliziten race auf `cls._instance_index_name`.
- ConfigManager Singleton ohne Lock (Finding #11).

---

## Empfohlene Fixes (priorisiert, NICHT angewendet — Audit-only)

1. **stems_paths in update_audio_analysis aufnehmen** + `persist_audio_clip` meta-Feld + `load_from_db` Rück-Konstrukt.
2. **VectorStore-Singleton** durch dict `{index_name → instance}` ersetzen, atexit-Registration mit `weakref.finalize` einmalig.
3. **video_router** auf `index_name="main_index"` umschalten ODER semantic_matcher auf `"video_index"` — eine konsistente Wahl.
4. **vector_map** populieren bei `add_embedding` (mit CASCADE-Cleanup-Logik) ODER FAISS-Vektor-Tombstone bei delete_media schreiben.
5. **Brain-State-Unbind** in close_project ergänzen: `BrainService.get().state_conn.close(); BrainService.get().state_conn = None`.
6. **audio_analysis_cache "beats" vs "beats_json"** vereinheitlichen (z.B. immer "beats").
7. **subtrack_segments + tempo_curve** in `load_from_db` einlesen (Persistenz-Symmetrie).
8. **render_queue.py** Schema in `SCHEMA_MIGRATIONS` aufnehmen.

---

## Sourcen / Files

- `backend/app_state.py:51-957`
- `src/pb_studio/data/database_core.py:34-341`
- `src/pb_studio/data/vector_store.py:17-219`
- `src/pb_studio/data/repositories/media_repository.py:85-285`
- `src/pb_studio/data/repositories/project_repository.py:8-127`
- `src/pb_studio/storage/brain_store.py:38-89`
- `src/pb_studio/storage/embedding_cache.py:36-124`
- `src/pb_studio/storage/embedding_repository.py:66-288`
- `src/pb_studio/storage/migrations/{embedding_cache,embeddings,patterns,state,weights}/001_initial.sql`
- `src/pb_studio/storage/sqlite_init.py:10-30`
- `src/pb_studio/brain/brain_service.py:30-101`
- `src/pb_studio/brain/weight_store.py:40-234`
- `src/pb_studio/brain/feedback_logger.py:28-80`
- `src/pb_studio/rendering/render_queue.py:70-186`
- `src/pb_studio/config_manager.py:11-115`
- `backend/routers/project_router.py:306-321`
- `backend/routers/audio_router.py:495-506`
- `backend/routers/video_router.py:744-769`
- `backend/_brain_singleton.py`

---

**Stand:** 17 Findings dokumentiert. Top 5 + Severity-Matrix oben. Auditmodus: read-only. Keine Code-Änderungen.
