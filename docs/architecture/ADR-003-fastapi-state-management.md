# ADR-003: FastAPI State-Management Strategie

**Status:** Proposed
**Datum:** 2026-03-04
**Entscheider:** David Lochmann (Owner) — Entscheidung ausstehend
**Kontext:** Ergebnis des Tech-Debt-Audits 2026-03-04 (Item #6)
**Dringlichkeit:** Mittel — Produktionsblocker, aktuell Single-User-Dev-Setup tolerierbar

---

## Kontext

Der Tech-Debt-Audit (2026-03-04) hat aufgedeckt, dass alle 4 FastAPI-Router **module-level Python-Dictionaries** als State-Speicher verwenden:

```python
# audio_router.py
_audio_clips: dict[str, AudioClipInfo] = {}

# video_router.py
_video_clips: dict[str, VideoClipInfo] = {}

# pacing_router.py
_current_timeline: list[dict] = []
_current_audio_path: str | None = None

# render_router.py
_render_tasks: dict[str, RenderTask] = {}
```

**Konsequenzen im aktuellen Zustand:**
1. **Datenverlust bei Prozess-Neustart:** Alle importierten Clips und Timelines sind verloren
2. **Single-User Only:** Kein Schutz gegen konkurrierende Requests (Race Conditions)
3. **Kein Crash-Recovery:** Laufende Renders werden bei Prozess-Absturz "vergessen"
4. **C#-Sicht:** Nach Python-Neustart "weiß" C# noch von alten Clips — State inkonsistent

**Aktuell tolerierbar weil:** Lokaler Entwicklungsserver, Ein-Benutzer-App, Python wird selten neu gestartet.

**Nicht tolerierbar sobald:** Docker-Deployment, automatische Prozess-Recovery, oder Multi-Session-Szenarien.

---

## Entscheidung (ausstehend — Optionen zur Auswahl)

---

## Optionen Evaluiert

### Option A: SQLite via bestehenden DatabaseManager (Empfohlen)

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Niedrig — SQLite bereits vorhanden |
| Datenpersistenz | ✅ Überlebt Prozess-Neustart |
| Aufwand | Mittel (3–5 Tage) |
| Abhängigkeiten | Keine neuen — SQLAlchemy bereits im Stack |
| Async-Kompatibilität | ✅ via asyncio.to_thread() oder aiosqlite |

**Vorteil:** SQLite ist bereits als `pb_studio/database/` im Stack. Alle Clip-Metadaten werden ohnehin in SQLite gespeichert. Die Router müssen nur auf den bestehenden `DatabaseManager` zugreifen anstatt eigene Dicts zu verwalten.

**Implementierungsansatz:**
```python
# Statt module-level dict:
_audio_clips: dict = {}  # ❌

# Router delegiert an DatabaseManager:
@router.post("/import")
async def import_audio(request: AudioImportRequest):
    result = await asyncio.to_thread(
        db_manager.save_audio_clips, request.paths
    )
    return result  # ✅ Persistiert in SQLite
```

**Cons:** Leicht höhere Latenz für einfache Operationen (DB statt RAM-Dict).

---

### Option B: UUID-Session-basierter In-Memory Store (Quick Fix)

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Sehr niedrig |
| Datenpersistenz | ❌ Verloren bei Neustart |
| Aufwand | 1 Tag |
| Abhängigkeiten | Keine |
| Problem gelöst | Nur Race-Conditions, nicht Persistenz |

**Ansatz:** Jede C#-Session bekommt eine UUID. Alle State-Dicts verwenden UUID als Key.

```python
_sessions: dict[str, SessionState] = {}

@dataclass
class SessionState:
    audio_clips: dict = field(default_factory=dict)
    video_clips: dict = field(default_factory=dict)
    timeline: list = field(default_factory=list)
```

**Vorteil:** Schnell umsetzbar. Verhindert State-Kollision bei parallelen Tests.
**Nachteil:** Löst das Datenverlust-Problem nicht. State bleibt nach Python-Neustart weg.

---

### Option C: Redis (Externe State-Store)

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Hoch |
| Datenpersistenz | ✅ (mit AOF/RDB) |
| Aufwand | 5–10 Tage |
| Abhängigkeiten | Redis-Server, redis-py |
| Skalierbarkeit | ✅ Multi-Process-fähig |

**Abgelehnt für jetzt:** Overkill für Single-User-Desktop-App. Redis als zusätzlicher Service erhöht Deployment-Komplexität massiv. Kein Mehrwert gegenüber SQLite.

---

### Option D: Status quo beibehalten (Explizite Entscheidung)

**Akzeptiert als temporär:** Für die Entwicklungsphase der WPF-Migration ist der aktuelle Zustand akzeptabel. Dokumentiertes Risiko, geplante Behebung nach Phase 1.

---

## Trade-off Analyse

**Option A (SQLite) vs. Option B (Session-Store):**

Option B ist schneller umsetzbar (1 Tag vs. 3–5 Tage) aber löst das eigentliche Problem nicht. Da SQLite bereits im Stack ist und alle Clip-Metadaten dort ohnehin landen sollten, ist Option A die architektonisch sauberere Lösung.

**Empfehlung: Option A** — nach Abschluss der WPF-Migration Phase 1.
**Interim: Option D** — bis zur WPF-Phase-2-Fertigstellung.

---

## Konsequenzen bei Wahl von Option A (SQLite)

### Was einfacher wird:
- Prozess-Restart ohne Datenverlust
- C# kann nach Python-Neustart State wiederherstellen (GET /clips gibt immer aktuellen DB-Stand zurück)
- Laufende Render-Tasks können nach Crash recovered werden

### Was schwieriger wird:
- Router-Code muss auf `DatabaseManager` zugreifen (Dependency Injection in FastAPI)
- `asyncio.to_thread()` für alle DB-Calls nötig (SQLAlchemy ist sync)
- Migration der bestehenden `_audio_clips`-Logik zu SQLite-Calls

### Neue Anforderungen:
- [ ] `DatabaseManager` in `backend/main.py` als FastAPI-Dependency initialisieren
- [ ] `audio_router.py`: `_audio_clips`-Dict durch DB-Calls ersetzen
- [ ] `video_router.py`: `_video_clips`-Dict durch DB-Calls ersetzen
- [ ] `pacing_router.py`: `_current_timeline` in SQLite-Session speichern
- [ ] `render_router.py`: `_render_tasks`-Dict durch DB-Calls ersetzen

---

## Phasenplan

### Phase 0 (Jetzt — keine Änderung):
Status quo dokumentiert. Risiko akzeptiert für Entwicklungsphase.

### Phase 1 (Nach WPF-Phase-1-Abschluss, ca. 2 Wochen):
Option B implementieren (UUID-Session-Store): verhindert Race-Conditions ohne Persistenz-Komplexität.

### Phase 2 (Vor erstem Release-Kandidaten):
Option A implementieren (SQLite-Persistenz via DatabaseManager): vollständige Lösung.

---

## Referenzen

- Tech-Debt-Report 2026-03-04, Item #6 (In-Memory Router State, Score 30)
- `pb_studio/database/` — bestehender DatabaseManager mit SQLAlchemy
- `backend/routers/` — alle 4 betroffenen Router

---

*ADR erstellt: 2026-03-04 | Review fällig: nach WPF-Migration Phase 1*
