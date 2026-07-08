# Review-Fixes Commits 2026-07-08/09 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alle 4 HIGH-, 8 MEDIUM- und relevanten LOW-Findings aus dem 4-Experten-Review der Commits `cee505d..ec44e38` fixen, testen und verifizieren.

**Architecture:** Der Kern-Fix ist ein thread-sicherer SSE-Publish-Pfad (`publish_event_threadsafe` in `backend/dependencies.py`) plus ein injizierbarer Status-Publisher-Hook in `lmstudio_vision_wrapper.py` (löst Cross-Thread-Race UND Layering-Inversion gleichzeitig). Daneben punktuelle Fixes in WPF (AutomationPeer, Selektions-Erhalt), Storage (Lock-Sharing, Conn-Pruning, Migration-Warnings), Pacing (atomic save hardening) und PowerShell-Smoke-Script.

**Tech Stack:** Python 3.11 / FastAPI / asyncio · C# WPF .NET 9.0 (CommunityToolkit.Mvvm) · pytest (`PYTHONPATH=src`, `pytest Tests/ -x -q`) · PowerShell 5.1.

**Projekt-Regeln (bindend):**
- Jede C#-Änderung → `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` (Launcher lädt Release-DLL).
- Jede `.ps1`-Änderung → `script-validator`-Skill/Subagent bis 3× clean Run (IRON Rule 10).
- Python-Tests: PowerShell `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest ...`.
- Commits klein, pro Task einer.

**Bewusst NICHT gefixt (mit Begründung, im Abschlussbericht erwähnen):**
- Doppel-Send `VideoLibraryRefreshMessage`+`MediaLibraryRefreshMessage` (LOW): Empfängerkreise unterscheiden sich (AudioLibrary/ProjectOverview hören nur MediaLibrary); Reload-Storm ist durch `_loadGate`+`_reloadQueued` gedeckelt. Entfernen würde Verhalten ändern.
- CORS `http://127.0.0.1` ohne Port (LOW, pre-existing): nur relevant falls Browser-Tooling geplant.
- `vram_budget_manager` Lock-über-Init-Fragilität (LOW): kein aktiver Bug, Umbau = Risiko ohne Nutzen.
- `MediaIngestViewModel` Line-Ending-Rewrite (LOW): Commit-History nicht umschreibbar; Task 12 verhindert Wiederholung via `.gitattributes`.
- Beat-Dedup Chained-Grouping (LOW): 150ms-Ketten-Kollaps erst ab effektiv >400 BPM relevant; Task 12 dokumentiert das Verhalten im Code-Kommentar statt Logik-Umbau.

---

## Task 1: `publish_event_threadsafe` in backend/dependencies.py (HIGH-1, Teil A)

**Problem:** `publish_event` macht `put_nowait` auf `asyncio.Queue`s des uvicorn-Main-Loops. Aus fremden Threads/Loops (z.B. `asyncio.to_thread`-Worker) fehlt der Selector-Wakeup → Events bis 15s verspätet; Race mit `wait_for`-Cancel → `InvalidStateError`.

**Files:**
- Modify: `backend/dependencies.py:160-194`
- Modify: `backend/main.py` (lifespan, ab Zeile 96)
- Test: `Tests/test_publish_event_threadsafe.py` (neu)

- [ ] **Step 1: Failing Test schreiben**

```python
"""Tests fuer publish_event_threadsafe (Review-Fix HIGH-1 2026-07-09)."""
import asyncio
import threading

from backend import dependencies as deps


def test_threadsafe_publish_from_worker_thread_wakes_main_loop():
    async def main():
        deps.set_main_loop(asyncio.get_running_loop())
        queue = deps.get_event_queue("test_ts")
        try:
            def worker():
                deps.publish_event_threadsafe("llm_status", {"status": "active"})

            t = threading.Thread(target=worker)
            t.start()
            t.join()
            # Muss OHNE Keepalive-Timeout ankommen (<1s statt 15s)
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            assert event["event"] == "llm_status"
            assert event["data"]["status"] == "active"
        finally:
            deps._event_queues.pop("test_ts", None)
            deps.set_main_loop(None)

    asyncio.run(main())


def test_threadsafe_publish_without_loop_is_noop():
    deps.set_main_loop(None)
    # darf nicht werfen, auch ohne registrierte Queues/Loop
    deps.publish_event_threadsafe("llm_status", {"status": "failed"})


def test_threadsafe_publish_same_loop_direct():
    async def main():
        deps.set_main_loop(asyncio.get_running_loop())
        queue = deps.get_event_queue("test_direct")
        try:
            deps.publish_event_threadsafe("llm_status", {"status": "loading"})
            event = queue.get_nowait()
            assert event["data"]["status"] == "loading"
        finally:
            deps._event_queues.pop("test_direct", None)
            deps.set_main_loop(None)

    asyncio.run(main())
```

- [ ] **Step 2: Test laufen lassen — muss failen**

Run (PowerShell): `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_publish_event_threadsafe.py -v`
Expected: FAIL — `AttributeError: module 'backend.dependencies' has no attribute 'set_main_loop'`

- [ ] **Step 3: Implementierung in dependencies.py**

Fan-out-Logik aus `publish_event` in eine synchrone Hilfsfunktion ziehen, Loop-Referenz + threadsafe-Variante ergänzen. Bestehenden Block Zeile 160-194 so umbauen:

```python
# SSE Event Queue für Progress-Updates
_event_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}

# Review-Fix HIGH-1 (2026-07-09): Referenz auf den uvicorn-Main-Loop, damit
# Worker-Threads (asyncio.to_thread + eigener Loop) Events thread-safe via
# call_soon_threadsafe einspeisen können. put_nowait aus fremdem Thread weckt
# den Selector nicht -> Events kamen bis zu 15s verspätet (Keepalive-Timeout).
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """Wird im Lifespan-Startup gesetzt (und in Tests)."""
    global _main_loop
    _main_loop = loop


def get_event_queue(client_id: str = "default") -> asyncio.Queue[dict[str, Any]]:
    """Gibt die Event-Queue für einen Client zurück (per-Client Queue)."""
    if client_id not in _event_queues:
        _event_queues[client_id] = asyncio.Queue(maxsize=500)
    return _event_queues[client_id]


def _fanout_event(event: dict[str, Any]) -> None:
    """Synchroner Fan-out an alle Queues. NUR im Main-Loop-Thread aufrufen."""
    for queue in list(_event_queues.values()):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                f"Event-Queue voll (maxsize=500) — ältestes Event wird verworfen. "
                f"Event-Typ: {event['event']}"
            )
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            queue.put_nowait(event)


async def publish_event(event_type: str, data: dict[str, Any], client_id: str = "default") -> None:
    """Publiziert ein Event an alle verbundenen SSE-Clients (Fan-out).

    BUG-028 Fix: Fan-out an alle registrierten Queues, damit /events/progress und
    /events/log gleichzeitig betrieben werden können ohne sich Events zu stehlen.
    """
    if not _event_queues:
        return
    _fanout_event({"event": event_type, "data": data})


def publish_event_threadsafe(event_type: str, data: dict[str, Any]) -> None:
    """Thread-sichere Variante für Worker-Threads/-Loops (Review-Fix HIGH-1).

    Best-effort: ohne gesetzten Main-Loop oder ohne Queues wird still verworfen
    (Status-Events sind rein kosmetisch, dürfen nie Inferenz abbrechen).
    """
    loop = _main_loop
    if loop is None or loop.is_closed() or not _event_queues:
        return
    event = {"event": event_type, "data": data}
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    try:
        if running is loop:
            _fanout_event(event)
        else:
            loop.call_soon_threadsafe(_fanout_event, event)
    except RuntimeError:
        # Loop wird gerade heruntergefahren — Event verwerfen
        pass
```

- [ ] **Step 4: Loop-Capture im Lifespan (backend/main.py)**

In `async def lifespan(...)` (Zeile 96ff) direkt nach den Start-Logs einfügen:

```python
    # Review-Fix HIGH-1 (2026-07-09): Main-Loop für thread-sichere SSE-Publishes
    from backend.dependencies import set_main_loop
    set_main_loop(asyncio.get_running_loop())
```

Und im Shutdown-Teil des Lifespans (nach dem `yield`) ergänzen:

```python
    set_main_loop(None)
```

Prüfen ob `import asyncio` in main.py vorhanden ist (sehr wahrscheinlich); sonst ergänzen.

- [ ] **Step 5: Tests laufen lassen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_publish_event_threadsafe.py Tests/test_events*.py -v`
Expected: alle PASS

- [ ] **Step 6: Commit**

```bash
git add backend/dependencies.py backend/main.py Tests/test_publish_event_threadsafe.py
git commit -m "fix(backend): add thread-safe SSE publish path via main-loop capture"
```

---

## Task 2: Status-Publisher-Hook in lmstudio_vision_wrapper.py (HIGH-1 Teil B, MEDIUM Layering + sleep, LOW Cache-Flicker/Provider-down/Ollama-Heuristik)

**Problem:** Wrapper importiert `backend.dependencies` (Layering-Inversion), awaited `publish_event` cross-loop (Race), schläft 100ms pro Frame vor dem Cache-Lookup, sendet loading-Events auch bei Cache-Hits und meldet Provider-down gar nicht.

**Files:**
- Modify: `src/pb_studio/video/lmstudio_vision_wrapper.py:174-290`
- Modify: `backend/main.py` (lifespan, Wiring)
- Test: `Tests/test_lmstudio_vision_wrapper_status.py` (neu)

- [ ] **Step 1: Failing Test schreiben**

```python
"""Tests fuer den Status-Publisher-Hook im Vision-Wrapper (Review-Fix 2026-07-09)."""
import pb_studio.video.lmstudio_vision_wrapper as w


def test_set_status_publisher_roundtrip():
    events = []
    w.set_status_publisher(lambda et, data: events.append((et, data)))
    try:
        w._publish_status("m1", "LM Studio", "loading", 25.0)
        assert events == [("llm_status", {
            "model": "m1", "provider": "LM Studio",
            "status": "loading", "percent": 25.0,
        })]
    finally:
        w.set_status_publisher(None)


def test_publish_status_without_publisher_is_noop():
    w.set_status_publisher(None)
    w._publish_status("m1", "LM Studio", "active", 100.0)  # darf nicht werfen


def test_publish_status_swallows_publisher_errors():
    def boom(et, data):
        raise RuntimeError("kaputt")
    w.set_status_publisher(boom)
    try:
        w._publish_status("m1", "Ollama", "failed", 0.0)  # darf nicht werfen
    finally:
        w.set_status_publisher(None)
```

- [ ] **Step 2: Test laufen lassen — muss failen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_lmstudio_vision_wrapper_status.py -v`
Expected: FAIL — `AttributeError: ... has no attribute 'set_status_publisher'`

- [ ] **Step 3: Hook implementieren + alle publish_event-Stellen ersetzen**

Auf Modulebene (bei den anderen Modul-Globals, vor `_async_extract_tags`):

```python
# Review-Fix 2026-07-09: injizierbarer Status-Publisher statt Direktimport von
# backend.dependencies (Layering-Inversion). Backend wired beim Startup
# publish_event_threadsafe hier ein; ohne Wiring (pytest, CLI) -> no-op.
from typing import Callable

_status_publisher: Callable[[str, dict[str, Any]], None] | None = None


def set_status_publisher(fn: Callable[[str, dict[str, Any]], None] | None) -> None:
    global _status_publisher
    _status_publisher = fn


def _publish_status(model: str, provider: str, status: str, percent: float) -> None:
    """Best-effort llm_status-Event. Darf NIE die Tag-Extraktion abbrechen."""
    fn = _status_publisher
    if fn is None:
        return
    try:
        fn("llm_status", {
            "model": model,
            "provider": provider,
            "status": status,
            "percent": percent,
        })
    except Exception as exc:  # noqa: BLE001 - Status ist rein kosmetisch
        logger.debug("llm_status publish fehlgeschlagen: %s", exc)
```

In `_async_extract_tags` dann:

1. Den Block `try: from backend.dependencies import publish_event / except ImportError: ...` (Zeilen 182-186) **komplett löschen**.
2. Provider-Heuristik (Zeile 192) angleichen an `lmstudio_client.py:383`:
```python
        base_url_lower = client.base_url.lower()
        is_ollama = "11434" in base_url_lower or "ollama" in base_url_lower
        provider_name = "Ollama" if is_ollama else "LM Studio"
```
3. **Provider-down-Fall** (LOW): im bestehenden `except LMStudioError`-Block nach `registry.refresh()` (Zeile 178-180) VOR dem `return [], "none"` einfügen — dazu `provider_name` VOR den `registry.refresh()`-Try ziehen (Client existiert dort schon):
```python
            _publish_status("none", provider_name, "failed", 0.0)
```
4. Jede der 7 `await publish_event("llm_status", {...})`-Stellen ersetzen durch den synchronen Aufruf, z.B.:
```python
            _publish_status(model, provider_name, "failed", 0.0)
```
5. `await asyncio.sleep(0.1)` (nach dem 25%-loading-Event) **löschen**.
6. **Cache-Hit-Reihenfolge** (LOW): Cache-Lookup VOR die loading-Events ziehen. Zielstruktur im Loop:
```python
            cache_key = (_frame_hash(frame_rgb), model, mode)
            cached = _cache_get(cache_key)
            if cached is not None:
                _publish_status(model, provider_name, "active", 100.0)
                return list(cached), model

            _publish_status(model, provider_name, "loading", 25.0)

            try:
                # C-F3: Hard 15s timeout wrapper ... (bestehender Code)
```
Das 75%-loading-Event (vorher zwischen Cache-Check und Chat-Call) ersatzlos streichen — mit nur einem loading-Event vor dem Chat-Call gibt es keinen Flicker und keine Doppel-Publishes.

- [ ] **Step 4: Wiring im Backend-Lifespan (backend/main.py)**

Direkt nach dem `set_main_loop(...)`-Aufruf aus Task 1:

```python
    # Review-Fix 2026-07-09: llm_status-Publisher in den Vision-Wrapper injizieren
    from backend.dependencies import publish_event_threadsafe
    from pb_studio.video.lmstudio_vision_wrapper import set_status_publisher
    set_status_publisher(publish_event_threadsafe)
```

Im Shutdown-Teil (nach `yield`, vor `set_main_loop(None)`):

```python
    set_status_publisher(None)
```

- [ ] **Step 5: Tests laufen lassen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_lmstudio_vision_wrapper_status.py Tests/test_lmstudio*.py Tests/test_video*.py -v`
Expected: alle PASS (bestehende Wrapper-Tests dürfen nicht brechen — kein backend-Import mehr als Seiteneffekt)

- [ ] **Step 6: Commit**

```bash
git add src/pb_studio/video/lmstudio_vision_wrapper.py backend/main.py Tests/test_lmstudio_vision_wrapper_status.py
git commit -m "fix(video): thread-safe injectable llm_status publisher, drop backend import + per-frame sleep"
```

---

## Task 3: llm_status-Hygiene in backend/routers/video_router.py (MEDIUM Terminal-State, LOW Import-Duplikate/Log-Reihenfolge)

**Problem:** Moondream-Pfad publiziert `llm_status` ohne Terminal-/Idle-Event und ohne `clip_id`; lokale Duplikat-Imports; im Except-Pfad steht `await publish_event` VOR `logger.warning` (Publish-Fehler maskiert Root-Cause).

**Files:**
- Modify: `backend/routers/video_router.py:1030-1075`

**Hinweis Frontend:** `MainViewModel.OnLlmStatusReceived` behandelt unbekannte Status im else-Zweig als "Bereit"/Grau — ein `"idle"`-Event braucht KEINE C#-Änderung.

- [ ] **Step 1: Umbau des Moondream-Blocks**

Die beiden lokalen `from backend.dependencies import publish_event`-Imports (Zeile ~1033 und ~1064) löschen — `publish_event` ist bereits auf Modulebene importiert (Zeile 23, `from ..dependencies import ...`; falls dort nicht enthalten, dort ergänzen statt lokal). `await asyncio.sleep(0.1)` löschen. Zielstruktur:

```python
            # Moondream Fallback falls LM Studio keine Tags geliefert hat (GPU)
            if moondream_frames_to_run:
                try:
                    await publish_event("llm_status", {
                        "model": "Moondream2 (ONNX)",
                        "provider": "Local GPU (DirectML)",
                        "status": "loading",
                        "percent": 50.0,
                        "clip_id": clip_id,
                    })

                    moondream_tags_list = await with_gpu_task(
                        _run_moondream_inference_on_frames, moondream_frames_to_run,
                        model_id="moondream_fp16"
                    )
                    used_model = "moondream"

                    await publish_event("llm_status", {
                        "model": "Moondream2 (ONNX)",
                        "provider": "Local GPU (DirectML)",
                        "status": "active",
                        "percent": 100.0,
                        "clip_id": clip_id,
                    })

                    for tags in moondream_tags_list:
                        ...  # bestehender Code unverändert
                except Exception as moondream_err:
                    # Log ZUERST — publish darf die Root-Cause nie maskieren
                    logger.warning(f"Moondream Fallback GPU-Inferenz fehlgeschlagen: {moondream_err}")
                    try:
                        await publish_event("llm_status", {
                            "model": "Moondream2 (ONNX)",
                            "provider": "Local GPU (DirectML)",
                            "status": "failed",
                            "percent": 0.0,
                            "clip_id": clip_id,
                        })
                    except Exception:
                        logger.debug("llm_status publish nach Moondream-Fehler fehlgeschlagen")
                finally:
                    # Review-Fix MEDIUM (2026-07-09): Terminal-State, damit das
                    # Widget nach der Analyse nicht dauerhaft "Aktiv" zeigt.
                    try:
                        await publish_event("llm_status", {
                            "model": "none",
                            "provider": "Local GPU (DirectML)",
                            "status": "idle",
                            "percent": 0.0,
                            "clip_id": clip_id,
                        })
                    except Exception:
                        pass
```

`clip_id`: die in `_run_color_and_caption_analysis` verfügbare Clip-Identifikation verwenden (Funktions-Signatur prüfen — Parameter heißt dort `clip_id` oder ist über den umgebenden Kontext verfügbar; exakten Namen aus der Signatur übernehmen, notfalls weglassen statt raten).

- [ ] **Step 2: Kompilat + relevante Tests**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m py_compile backend/routers/video_router.py; .venv\Scripts\python.exe -m pytest Tests/test_video*.py -q`
Expected: kein Fehler, Tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/routers/video_router.py
git commit -m "fix(video): llm_status terminal idle state, clip_id payload, log-before-publish"
```

---

## Task 4: CachedTabControl AutomationPeer-Fallback (HIGH-2, LOW ResetChildrenCache)

**Problem:** `CreatePeerForElement(ContentPresenter)` liefert null (ContentPresenter hat keinen Default-Peer) → UIA-Fix ist No-Op, pywinauto sieht Tab-Content weiterhin nicht. Zusätzlich: bei Tab-Wechsel wird der Peer-Children-Cache nicht invalidiert.

**Files:**
- Modify: `PBStudio.UI/Controls/CachedTabControl.cs:187-235`

- [ ] **Step 1: GetChildrenCore fixen**

In `CachedTabControlAutomationPeer.GetChildrenCore()`:

```csharp
    protected override List<AutomationPeer> GetChildrenCore()
    {
        var children = base.GetChildrenCore() ?? new List<AutomationPeer>();

        var activePresenter = _control.GetActiveContentPresenter();
        if (activePresenter != null)
        {
            // Review-Fix HIGH-2 (2026-07-09): ContentPresenter hat keinen
            // Default-AutomationPeer (CreatePeerForElement liefert null).
            // FrameworkElementAutomationPeer walkt den Visual Tree und sammelt
            // die Descendant-Peers (Buttons, Lists, ...) fuer UIA ein.
            var peer = CreatePeerForElement(activePresenter)
                       ?? new FrameworkElementAutomationPeer(activePresenter);
            children.Add(peer);
        }

        return children;
    }
```

- [ ] **Step 2: Peer-Cache bei Tab-Wechsel invalidieren**

In der Klasse `CachedTabControl` die bestehende `OnSelectionChanged`-Override suchen (Selektions-Logik fürs Presenter-Caching existiert bereits). Am Ende der Methode ergänzen — falls keine Override existiert, eine anlegen:

```csharp
    protected override void OnSelectionChanged(SelectionChangedEventArgs e)
    {
        base.OnSelectionChanged(e);
        // ... bestehende Caching-Logik unverändert ...

        // Review-Fix (2026-07-09): UIA-Clients mit gecachtem Tree sehen den
        // neuen Tab-Content sonst erst beim naechsten Re-Walk.
        if (AutomationPeer.ListenerExists(AutomationEvents.StructureChanged))
        {
            UIElementAutomationPeer.FromElement(this)?.ResetChildrenCache();
        }
    }
```

- [ ] **Step 3: Release-Build**

Run: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
Expected: 0 Fehler, 0 Warnungen

- [ ] **Step 4: Runtime-Verify (pywinauto)**

App starten (run-pb-studio-Skill bzw. Launcher), dann:

```powershell
.venv\Scripts\python.exe -c "from pywinauto import Desktop; w = Desktop(backend='uia').window(title_re='.*PB Studio.*'); w.print_control_identifiers(depth=6)"
```

Expected: Controls des aktiven Tabs (z.B. Buttons der Video-Library) erscheinen im UIA-Tree. Ergebnis im Commit-Text festhalten (verifiziert vs. nicht ausführbar).

- [ ] **Step 5: Commit**

```bash
git add PBStudio.UI/Controls/CachedTabControl.cs
git commit -m "fix(ui): fallback FrameworkElementAutomationPeer so cached tab content reaches UIA tree"
```

---

## Task 5: brain_store Close-vs-Query-Race real fixen (HIGH-3)

**Problem:** `_weights_lock`/`_patterns_lock` werden nur in `close()` genommen; `WeightStore` (einziger externer Consumer, `brain_service.py:43`) queried `weights_conn` mit eigenem privatem Lock → `close()` kann die Connection unter laufendem Statement schließen. Der AP5.5-Kommentar behauptet eine Serialisierung, die nicht existiert.

**Files:**
- Modify: `src/pb_studio/brain/weight_store.py:43-60`
- Modify: `src/pb_studio/brain/brain_service.py:43`
- Modify: `src/pb_studio/storage/brain_store.py:59-70` (Kommentar korrigieren)
- Test: `Tests/test_brain_recovery.py` (erweitern)

- [ ] **Step 1: Failing Test schreiben** (an bestehende Tests in `Tests/test_brain_recovery.py` anhängen)

```python
def test_weight_store_shares_brain_store_lock(tmp_path):
    """Review-Fix HIGH-3 (2026-07-09): WeightStore muss denselben Lock nutzen
    wie BrainStore.close(), sonst Race close-vs-query."""
    from pb_studio.storage.brain_store import BrainStore
    from pb_studio.brain.weight_store import WeightStore

    store = BrainStore(tmp_path)
    try:
        ws = WeightStore(store.weights_conn, lock=store._weights_lock)
        assert ws._lock is store._weights_lock
    finally:
        store.close()
```

Hinweis: `BrainStore`-Konstruktor-Signatur aus dem File übernehmen (bestehende Tests in `test_brain_recovery.py` zeigen die korrekte Instanziierung — deren Pattern kopieren).

- [ ] **Step 2: Test laufen lassen — muss failen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_brain_recovery.py -k shares -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'lock'`

- [ ] **Step 3: WeightStore Lock injizierbar machen + ALLE conn-Zugriffe unter Lock**

`weight_store.py` `__init__` erweitern:

```python
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        cold_start_defaults: Optional[dict[str, float]] = None,
        cache_max: int = _DEFAULT_CACHE_MAX,
        lock: Optional[threading.Lock] = None,
    ):
        self.conn = conn
        self.defaults = dict(cold_start_defaults or COLD_START_DEFAULTS)
        # R-Brain-08 caching
        self._version: int = 0
        # Review-Fix HIGH-3 (2026-07-09): Lock kann von BrainStore geteilt
        # werden, damit close() nicht unter laufenden Queries zuschlaegt.
        self._lock = lock if lock is not None else threading.Lock()
        ...
```

Dann in `weight_store.py` JEDEN `self.conn.execute(...)`/Cursor-Zugriff prüfen (`grep -n "self.conn" src/pb_studio/brain/weight_store.py`): Zugriffe, die noch nicht innerhalb `with self._lock:` laufen (insbesondere die Read-Pfade des SQL-Lookups), nach diesem Muster wrappen — Logik unverändert lassen, nur den Lock-Scope um den conn-Zugriff legen:

```python
        with self._lock:
            row = self.conn.execute(sql, params).fetchone()
```

Achtung: kein verschachteltes `with self._lock` in Methoden, die einander aufrufen (Lock ist nicht reentrant) — wo eine gelockte Methode eine andere gelockte aufruft, den Lock nur an der äußeren Stelle nehmen und die innere als `_..._locked`-Variante ohne Lock aufrufen.

- [ ] **Step 4: brain_service.py Wiring**

Zeile 43 ändern:

```python
        self.weights = WeightStore(self.brain.weights_conn, lock=self.brain._weights_lock)
```

- [ ] **Step 5: brain_store.py Kommentar ehrlich machen**

Kommentar Zeile 67-70 ersetzen:

```python
        # AP5.5 (Audit 2026-06-10) + Review-Fix HIGH-3 (2026-07-09):
        # Locks serialisieren close() gegen Queries. _weights_lock wird an
        # WeightStore durchgereicht (brain_service.py); patterns_conn hat
        # aktuell keine externen Query-Consumer.
```

- [ ] **Step 6: Tests laufen lassen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_brain_recovery.py Tests/test_brain*.py Tests/test_weight*.py -v`
Expected: alle PASS

- [ ] **Step 7: Commit**

```bash
git add src/pb_studio/brain/weight_store.py src/pb_studio/brain/brain_service.py src/pb_studio/storage/brain_store.py Tests/test_brain_recovery.py
git commit -m "fix(brain): share close-lock with WeightStore so close cannot race live queries"
```

---

## Task 6: verify_release_smoke.ps1 Dummy + Kill-Pfad (HIGH-4, MEDIUM toter Fallback)

**Problem:** Dummy `time.sleep(60)` endet natürlich vor Script-Ende (Lauf > 60s) → `HasExited`-Check meldet False-FAIL. Und: `Stop-Process -ErrorAction SilentlyContinue` wirft nie → `catch { taskkill }` ist toter Code, außerdem killt `Stop-Process` keine Kind-Prozesse (ffmpeg-Waisen).

**Files:**
- Modify: `verify_release_smoke.ps1:221-225` und `verify_release_smoke.ps1:440-464`

**PFLICHT:** `script-validator`-Subagent dispatchen (IRON Rule 10) — 3× clean Run vor Abschluss.

- [ ] **Step 1: Dummy-Lebensdauer fixen (Zeile 223)**

```powershell
    Step 'Start dummy Python process for PID isolation verification' {
        $pythonExe = Resolve-PythonExe
        # Review-Fix HIGH-4 (2026-07-09): sleep(3600) statt sleep(60) — der
        # Smoke-Lauf dauert regulaer >60s; ein natuerlich beendeter Dummy
        # wurde als Fremd-Termination fehlinterpretiert (False-FAIL).
        $script:DummyProcess = Start-Process -FilePath $pythonExe -ArgumentList '-c', '"import time; time.sleep(3600)"' -WindowStyle Minimized -PassThru
        Write-Host "  dummy process started with PID $($script:DummyProcess.Id)"
    }
```

- [ ] **Step 2: Backend-Kill mit Prozessbaum + Dummy-Stop immer (finally-Block, Zeilen 440-464)**

```powershell
        Write-Host "[SMOKE] Terminating backend process PID $($script:BackendProcess.Id)..."
        try {
            $script:BackendProcess.Refresh()
            if (-not $script:BackendProcess.HasExited) {
                # Review-Fix MEDIUM (2026-07-09): taskkill /T killt den ganzen
                # Prozessbaum (uvicorn kann ffmpeg-Kinder offen haben);
                # Stop-Process traf nur den Parent und der catch-Fallback war
                # toter Code (SilentlyContinue wirft nie).
                taskkill /PID $script:BackendProcess.Id /T /F 2>$null | Out-Null
                if (-not $?) {
                    Stop-Process -Id $script:BackendProcess.Id -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {
            Stop-Process -Id $script:BackendProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }

    # Verify dummy process is still alive, then ALWAYS stop it
    if ($script:DummyProcess) {
        $script:DummyProcess.Refresh()
        if ($script:DummyProcess.HasExited) {
            Write-Host "[SMOKE] FAIL: Dummy Python process (PID $($script:DummyProcess.Id)) was terminated!" -ForegroundColor Red
            $script:SmokeExitCode = 1
        } else {
            Write-Host "[SMOKE] PASS: Dummy Python process is still alive." -ForegroundColor Green
        }
        try {
            Stop-Process -Id $script:DummyProcess.Id -Force -ErrorAction SilentlyContinue
        } catch {}
    }
    exit $script:SmokeExitCode
```

(Das `Stop-Process` für den Dummy wandert aus dem else-Zweig hinter die if/else — läuft damit in JEDEM Fall.)

- [ ] **Step 3: script-validator dispatchen**

Subagent `script-validator` mit Auftrag: `verify_release_smoke.ps1` Parse-Check (`[System.Management.Automation.PSParser]::Tokenize`), PSScriptAnalyzer falls vorhanden, Smoke-Run-Simulation der geänderten Blöcke — bis 3× fehlerfrei in Folge.

- [ ] **Step 4: Commit**

```bash
git add verify_release_smoke.ps1
git commit -m "fix(infra): dummy 1h lifetime, tree-kill backend, always stop dummy in smoke script"
```

---

## Task 7: anchor_manager Save-Härtung (MEDIUM os.replace/tmp-Clobber, LOW fsync)

**Problem:** Fixer `.tmp`-Name → parallele Saves clobbern sich (korruptes JSON kann promoted werden); `os.replace` wirft auf Windows `PermissionError` wenn das Ziel gerade gelesen wird; `return False` wird von Callern ignoriert; kein fsync (Durability).

**Files:**
- Modify: `src/pb_studio/pacing/anchor_manager.py:163-181`
- Test: `Tests/test_anchor_manager.py` (erweitern)

- [ ] **Step 1: Failing Test schreiben** (an `Tests/test_anchor_manager.py` anhängen; Instanziierungs-Pattern der bestehenden Tests im File übernehmen)

```python
def test_concurrent_saves_produce_valid_json(tmp_path):
    """Review-Fix MEDIUM (2026-07-09): eindeutige Temp-Namen — parallele
    Saves duerfen sich nicht denselben .tmp teilen (Korruptions-Risiko)."""
    import json
    import threading
    mgr = _make_manager(tmp_path)  # Helper analog zu bestehenden Tests aufbauen

    errors = []

    def do_save():
        try:
            assert mgr._save_anchors() is True
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=do_save) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    anchor_file = mgr._get_anchor_file()
    data = json.loads(anchor_file.read_text(encoding="utf-8"))
    assert data["project_id"] == mgr.project_id
    # keine liegengebliebenen tmp-Dateien
    assert list(anchor_file.parent.glob("*.tmp*")) == []
```

(Methodenname der Save-Funktion aus dem File übernehmen — der Diff zeigte die Save-Logik ab Zeile 140; falls sie `save_anchors`/`_save` heißt, Testaufruf anpassen.)

- [ ] **Step 2: Test laufen lassen — muss failen oder flaken**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_anchor_manager.py -k concurrent -v`
Expected: FAIL/Flake (tmp-Clobber) — falls er zufällig durchläuft: trotzdem weiter, Fix ist deterministisch besser.

- [ ] **Step 3: Save-Block härten (Zeilen 163-176)**

```python
            import os
            import tempfile
            anchor_file = self._get_anchor_file()
            # Review-Fix MEDIUM (2026-07-09): eindeutiger Temp-Name via mkstemp
            # (fixer .tmp-Name clobberte bei parallelen Saves) + fsync
            # (Atomicity ohne Durability: Crash konnte leere Datei promoten)
            # + Retry bei PermissionError (Windows: os.replace schlaegt fehl,
            # wenn ein Reader die Ziel-Datei gerade offen hat).
            fd, tmp_name = tempfile.mkstemp(
                dir=str(anchor_file.parent),
                prefix=anchor_file.name + ".",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                last_err: Exception | None = None
                for attempt in range(3):
                    try:
                        os.replace(tmp_name, anchor_file)
                        break
                    except PermissionError as e:
                        last_err = e
                        time.sleep(0.1 * (attempt + 1))
                else:
                    raise last_err  # type: ignore[misc]
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise

            return True
```

`import time` am Dateianfang sicherstellen (nicht inline).

- [ ] **Step 4: Caller-Ignoranz beheben**

`grep -n "save_anchors\|_save_anchors" src/pb_studio/pacing/anchor_manager.py backend/` — an den drei Aufrufstellen (~Zeile 248/260/270), die den Rückgabewert wegwerfen, mindestens loggen:

```python
        if not self._save_anchors():
            logger.error("Anchor-Save fehlgeschlagen — Aenderung ist NICHT persistiert (project_id=%s)", self.project_id)
```

- [ ] **Step 5: Tests laufen lassen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_anchor_manager.py -v`
Expected: alle PASS

- [ ] **Step 6: Commit**

```bash
git add src/pb_studio/pacing/anchor_manager.py Tests/test_anchor_manager.py
git commit -m "fix(pacing): unique temp names, fsync, replace-retry and logged save failures"
```

---

## Task 8: DirectorViewModel Selektion über Reloads erhalten (MEDIUM)

**Problem:** `LoadClipsAsync` setzt bei JEDEM Refresh (`Audio/Video/MediaLibraryRefreshMessage` → jeder Import/jede Analyse) alle Video-Checkboxen zurück auf `IsSelected = true` — User-Deselektionen gehen verloren.

**Files:**
- Modify: `PBStudio.UI/ViewModels/DirectorViewModel.cs:114-131`

- [ ] **Step 1: Selektions-Snapshot einbauen**

```csharp
            var videoClips = await _videoLibraryState.RefreshAsync();
            if (videoClips != null && version == _loadVersion)
            {
                await Application.Current.Dispatcher.InvokeAsync(() =>
                {
                    // Review-Fix MEDIUM (2026-07-09): User-Deselektionen ueber
                    // Library-Refreshes erhalten — nur NEUE Clips defaulten auf true.
                    var previousSelection = AvailableVideoClips.ToDictionary(c => c.Id, c => c.IsSelected);
                    AvailableVideoClips.Clear();
                    foreach (var clip in videoClips)
                    {
                        AvailableVideoClips.Add(new SelectableVideoClip
                        {
                            Id = clip.Id,
                            Name = clip.Name,
                            DurationSeconds = clip.DurationSeconds,
                            IsSelected = previousSelection.TryGetValue(clip.Id, out var wasSelected) ? wasSelected : true
                        });
                    }
                });
            }
```

`using System.Linq;` prüfen (für `ToDictionary`).

- [ ] **Step 2: Release-Build**

Run: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
Expected: 0 Fehler

- [ ] **Step 3: Commit**

```bash
git add PBStudio.UI/ViewModels/DirectorViewModel.cs
git commit -m "fix(ui): preserve director clip selection across library refreshes"
```

---

## Task 9: VideoLibraryViewModel SelectedClip + IsMarked über Self-Refresh retten (MEDIUM)

**Problem:** Nach Einzel-Analyse sendet der VM `VideoLibraryRefreshMessage`, die er selbst empfängt → `LoadClipsAsync` cleart + rebuildet die Liste → `SelectedClip` wird null (`SelectedClipScenes` geleert, L-M6-Auto-Reload zunichte), `IsMarked`-Flags verloren.

**Files:**
- Modify: `PBStudio.UI/ViewModels/VideoLibraryViewModel.cs` (LoadClipsAsync — Clear/Rebuild-Block; Zeilen via `grep -n "VideoClips.Clear" PBStudio.UI/ViewModels/VideoLibraryViewModel.cs` lokalisieren)

- [ ] **Step 1: Snapshot + Restore in LoadClipsAsync**

Im Dispatcher-Block, der `VideoClips.Clear()` + Rebuild macht, VOR dem Clear:

```csharp
                    // Review-Fix MEDIUM (2026-07-09): Selektion + Markierungen
                    // ueberleben den Self-Refresh nach Analyse (L-M6-Erhalt).
                    var previousSelectedId = SelectedClip?.Id;
                    var previousMarked = VideoClips.Where(c => c.IsMarked).Select(c => c.Id).ToHashSet();
```

NACH dem Rebuild-foreach:

```csharp
                    foreach (var clip in VideoClips)
                    {
                        if (previousMarked.Contains(clip.Id)) clip.IsMarked = true;
                    }
                    if (previousSelectedId.HasValue)
                    {
                        SelectedClip = VideoClips.FirstOrDefault(c => c.Id == previousSelectedId.Value);
                    }
```

Typ von `Id` prüfen (int vs. string) — `previousSelectedId.HasValue`/`.Value` nur bei Nullable-Werttyp, bei string stattdessen `if (previousSelectedId != null)`. `using System.Linq;` prüfen.

- [ ] **Step 2: Release-Build**

Run: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
Expected: 0 Fehler

- [ ] **Step 3: Commit**

```bash
git add PBStudio.UI/ViewModels/VideoLibraryViewModel.cs
git commit -m "fix(ui): restore selected clip and marked flags after library self-refresh"
```

---

## Task 10: EmbeddingRepository tote Thread-Connections prunen (MEDIUM)

**Problem:** Jede Thread-Connection landet in `_all_conns` und wird nie entfernt — bei Thread-Churn akkumulieren offene SQLite-Handles bis `close()`.

**Files:**
- Modify: `src/pb_studio/storage/embedding_repository.py:70-97`
- Test: `Tests/test_storage_layer.py` (erweitern)

- [ ] **Step 1: Failing Test schreiben** (an `Tests/test_storage_layer.py` anhängen; Fixture-Pattern der bestehenden EmbeddingRepository-Tests übernehmen)

```python
def test_dead_thread_connections_are_pruned(tmp_path):
    """Review-Fix MEDIUM (2026-07-09): Conns toter Threads werden beim
    naechsten Conn-Aufbau geschlossen und aus _all_conns entfernt."""
    import threading
    from pb_studio.storage.embedding_repository import EmbeddingRepository

    repo = EmbeddingRepository(tmp_path / "emb.db")
    try:
        def use_repo():
            _ = repo.conn  # erzeugt Thread-Conn

        for _ in range(5):
            t = threading.Thread(target=use_repo)
            t.start()
            t.join()

        _ = repo.conn  # Main-Thread-Conn -> triggert Pruning
        assert len(repo._all_conns) <= 2  # main + max. 1 Nachzuegler
    finally:
        repo.close()
```

- [ ] **Step 2: Test laufen lassen — muss failen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_storage_layer.py -k pruned -v`
Expected: FAIL — `assert 6 <= 2`

- [ ] **Step 3: Pruning implementieren**

`_all_conns` auf `(thread_ident, conn)`-Tupel umstellen:

```python
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._ensure_schema()
        self._local = threading.local()
        # Review-Fix MEDIUM (2026-07-09): (thread_ident, conn)-Paare, damit
        # Conns toter Threads beim naechsten Zugriff geprunt werden koennen.
        self._all_conns: list[tuple[int, sqlite3.Connection]] = []
        self._conns_lock = threading.Lock()

    def _prune_dead_locked(self) -> None:
        """Schliesst Conns toter Threads. Caller haelt _conns_lock."""
        alive = {t.ident for t in threading.enumerate()}
        survivors: list[tuple[int, sqlite3.Connection]] = []
        for ident, conn in self._all_conns:
            if ident in alive:
                survivors.append((ident, conn))
            else:
                try:
                    conn.close()
                except Exception:
                    pass
        self._all_conns = survivors

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(
                str(self.db_path), isolation_level=None, check_same_thread=False
            )
            init_connection(conn)
            self._load_vec(conn)
            with self._conns_lock:
                self._prune_dead_locked()
                self._all_conns.append((threading.get_ident(), conn))
            self._local.conn = conn
        return self._local.conn

    def close(self) -> None:
        with self._conns_lock:
            for _ident, conn in self._all_conns:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_conns.clear()
        self._local = threading.local()
```

- [ ] **Step 4: Tests laufen lassen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_storage_layer.py -v`
Expected: alle PASS (bestehende Tests, die `_all_conns` direkt prüfen, ggf. auf Tupel-Format anpassen)

- [ ] **Step 5: Commit**

```bash
git add src/pb_studio/storage/embedding_repository.py Tests/test_storage_layer.py
git commit -m "fix(storage): prune sqlite connections of dead threads on next acquire"
```

---

## Task 11: Migration-Parsing laut machen (MEDIUM)

**Problem:** SQL-Files ohne numerischen Präfix werden seit dem Umbau SILENT ignoriert; doppelte Versions-Präfixe überschreiben sich still.

**Files:**
- Modify: `src/pb_studio/storage/migration_runner.py:86-93`
- Modify: `src/pb_studio/storage/embedding_repository.py:117-126`
- Test: `Tests/test_storage_layer.py` (erweitern)

- [ ] **Step 1: Failing Tests schreiben**

```python
def test_migration_unparsable_name_warns(tmp_path, caplog):
    """Review-Fix MEDIUM (2026-07-09): nicht-numerische Praefixe -> Warning statt silent skip."""
    import logging
    from pb_studio.storage.migration_runner import migrate

    mig = tmp_path / "migs"
    mig.mkdir()
    (mig / "001_ok.sql").write_text("CREATE TABLE a (x INT);", encoding="utf-8")
    (mig / "notes.sql").write_text("CREATE TABLE b (x INT);", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        migrate(tmp_path / "m.db", mig)
    assert any("notes.sql" in r.message for r in caplog.records)


def test_migration_duplicate_prefix_raises(tmp_path):
    """Review-Fix MEDIUM (2026-07-09): doppelter Versions-Praefix -> harter Fehler."""
    import pytest
    from pb_studio.storage.migration_runner import migrate

    mig = tmp_path / "migs"
    mig.mkdir()
    (mig / "001_a.sql").write_text("CREATE TABLE a (x INT);", encoding="utf-8")
    (mig / "001_b.sql").write_text("CREATE TABLE b (x INT);", encoding="utf-8")

    with pytest.raises(ValueError, match="[Dd]uplicate|doppelt"):
        migrate(tmp_path / "m.db", mig)
```

- [ ] **Step 2: Tests laufen lassen — müssen failen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_storage_layer.py -k "unparsable or duplicate" -v`
Expected: beide FAIL

- [ ] **Step 3: Parse-Block härten (in BEIDEN Files identisch)**

```python
        parsed_scripts = []
        seen_versions: dict[int, str] = {}
        for script in scripts:
            m = re.match(r"^(\d+)", script.name)
            if not m:
                # Review-Fix MEDIUM (2026-07-09): vorher silent skip
                logger.warning(
                    "Migration %s hat keinen numerischen Praefix und wird IGNORIERT",
                    script.name,
                )
                continue
            version = int(m.group(1))
            if version in seen_versions:
                raise ValueError(
                    f"Doppelter Migrations-Praefix {version}: "
                    f"{seen_versions[version]} vs {script.name}"
                )
            seen_versions[version] = script.name
            parsed_scripts.append((version, script))
        parsed_scripts.sort(key=lambda x: x[0])
```

- [ ] **Step 4: Tests laufen lassen**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_storage_layer.py -v`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add src/pb_studio/storage/migration_runner.py src/pb_studio/storage/embedding_repository.py Tests/test_storage_layer.py
git commit -m "fix(storage): warn on unparsable migration names, fail on duplicate version prefixes"
```

---

## Task 12: LOW-Paket (Docstrings, Imports, Brushes, .gitattributes, Beat-Kommentar)

**Files:**
- Modify: `backend/routers/chat_router.py:46` (Docstring)
- Modify: `backend/routers/brain_router.py:30` (`import time` an Dateianfang)
- Modify: `PBStudio.UI/ViewModels/MainViewModel.cs:228-260` (statische frozen Brushes)
- Modify: `src/pb_studio/audio/streaming_analyzer.py:88-96` (Kommentar)
- Create: `.gitattributes`

- [ ] **Step 1: chat_router.py Docstring**

Klassen-Docstring Zeile ~46: Erwähnung von "tiktoken (cl100k_base...)" ersetzen durch:

```python
    """Token-Zaehlung via Zeichen-Heuristik (~3 Zeichen/Token, max(1, len//3)).

    tiktoken wurde 2026-07-08 entfernt (Offline-Robustheit, Latenz) — die
    Heuristik ist der primaere und einzige Zaehler.
    """
```

(Exakten bestehenden Docstring-Wortlaut im File prüfen und nur die tiktoken-Behauptung ersetzen.)

- [ ] **Step 2: brain_router.py Import**

`import time` von Zeile ~30 in den Import-Block am Dateianfang verschieben (alphabetisch bei den stdlib-Imports).

- [ ] **Step 3: MainViewModel statische Brushes**

In `MainViewModel` Klassenebene:

```csharp
    // Review-Fix LOW (2026-07-09): frozen statt pro Event neu allokiert (GC-Churn)
    private static readonly SolidColorBrush LlmLoadingBrush = CreateFrozen(Color.FromRgb(255, 110, 0));

    private static SolidColorBrush CreateFrozen(Color color)
    {
        var brush = new SolidColorBrush(color);
        brush.Freeze();
        return brush;
    }
```

In `OnLlmStatusReceived`: `LlmStatusColor = new SolidColorBrush(Color.FromRgb(255, 110, 0));` → `LlmStatusColor = LlmLoadingBrush;` (die `Brushes.LimeGreen`/`Red`/`Gray`-Zuweisungen sind System-Brushes, bereits frozen — unverändert lassen).

- [ ] **Step 4: streaming_analyzer Verhaltens-Kommentar**

Über dem Grouping-Loop (Zeile ~88):

```python
        # Hinweis (Review 2026-07-09): Chained Grouping — Vergleich gegen das
        # LETZTE Element der Gruppe. Ketten mit je <=150ms Abstand kollabieren
        # zu EINEM Beat; erst ab effektiv >400 BPM relevant, fuer Overlap-
        # Jitter-Dedup gewollt. Bei Problemen: gegen current_group[0] vergleichen.
```

- [ ] **Step 5: .gitattributes anlegen**

```gitattributes
# Review-Fix LOW (2026-07-09): MediaIngestViewModel-Commit 440b956 war ein
# 99%-Line-Ending-Rewrite (LF<->CRLF) — festnageln verhindert Wiederholung.
*.cs   text eol=crlf
*.xaml text eol=crlf
*.ps1  text eol=crlf
*.bat  text eol=crlf
*.cmd  text eol=crlf
*.py   text eol=lf
*.md   text
*.json text
```

Danach prüfen dass KEIN Mass-Renormalize-Diff entsteht: `git status --short` muss (bis auf `.gitattributes`) leer bleiben — `git add --renormalize .` NICHT ausführen (würde riesigen Diff erzeugen; Normalisierung passiert organisch bei künftigen Edits).

- [ ] **Step 6: Build + Kompilat-Checks**

Run: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` und `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m py_compile backend/routers/chat_router.py backend/routers/brain_router.py src/pb_studio/audio/streaming_analyzer.py`
Expected: 0 Fehler

- [ ] **Step 7: Commit**

```bash
git add backend/routers/chat_router.py backend/routers/brain_router.py PBStudio.UI/ViewModels/MainViewModel.cs src/pb_studio/audio/streaming_analyzer.py .gitattributes
git commit -m "chore: docstring/import hygiene, frozen status brush, gitattributes eol pinning"
```

---

## Task 13: Kuratierte Modellnamen gegen LM Studio verifizieren (MEDIUM, teil-manuell)

**Problem:** `qwen3.6-vision`/`qwen3.5-vl` folgen nicht dem LM-Studio-Id-Schema (`org/name`); `_name_matches` toleriert org-Präfix und `:tag`, aber ob die Ids real installierten Modellen entsprechen, ist nur live prüfbar.

**Files:**
- Modify (nur bei Mismatch): `backend/routers/models_router.py:43-57`, `src/pb_studio/ai/model_registry.py:33-44`, `Tests/test_model_registry.py`

- [ ] **Step 1: LM Studio abfragen**

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:1234/v1/models" -TimeoutSec 5 | ConvertTo-Json -Depth 5
```

Falls LM Studio nicht läuft: starten oder — falls nicht startbar — Task mit Vermerk "nicht verifizierbar, LM Studio offline" abschließen und im Abschlussbericht ausweisen.

- [ ] **Step 2: Abgleich + ggf. Korrektur**

Für jede der drei neuen Ids (`qwen3.6-vision`, `qwen3.5-vl`, `gemma-4-26b-a4b-it-ultra-uncensored-heretic`) prüfen ob sie (mit `_name_matches`-Toleranz: org-Präfix + `:tag` werden gestrippt) in der Liste auftaucht. Bei Mismatch: exakte LM-Studio-Id in `CURATED_VISION_MODELS` (models_router.py) UND `DEFAULT_TASK_PREFERENCES` (model_registry.py) UND `Tests/test_model_registry.py` synchron ersetzen.

- [ ] **Step 3: Tests + Commit (nur falls geändert)**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/test_model_registry.py -v`

```bash
git add backend/routers/models_router.py src/pb_studio/ai/model_registry.py Tests/test_model_registry.py
git commit -m "fix(ai): align curated vision model ids with real LM Studio model list"
```

---

## Task 14: Gesamt-Verifikation + Abschluss

- [ ] **Step 1: Voller Testlauf**

Run: `$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest Tests/ -x -q`
Expected: 738+ passed (Neuzugänge aus Tasks 1/2/5/7/10/11), 0 failed

- [ ] **Step 2: Release-Build final**

Run: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`
Expected: 0 Fehler, 0 Warnungen; DLL-Timestamp aktuell

- [ ] **Step 3: Live-Smoke LLM-Widget**

App via run-pb-studio starten, Video-Analyse mit Captions anstoßen, beobachten: Widget zeigt loading→active→idle (Bereit), keine 15s-Verzögerung. Screenshot/Beobachtung dokumentieren. Falls LM Studio offline: Moondream-Fallback-Pfad beobachten.

- [ ] **Step 4: CHANGELOG**

Neuen Abschnitt `## 2026-07-09 - Review-Fixes (4-Experten-Review der Commits 2026-07-08/09)` oben in `CHANGELOG.md` mit einem Satz pro Task (Muster: bestehende Einträge).

- [ ] **Step 5: Commit + Push**

```bash
git add CHANGELOG.md
git commit -m "docs: changelog for review fixes 2026-07-09"
git push origin 00013-system-wide-bug-hunting-audit
```

- [ ] **Step 6: Vault-Sync (IRON Rule 11)**

`10_Projects/PB_studio/log.md` append (Zusammenfassung Review-Fixes + Commit-Hashes) und `INDEX.md` Frontmatter `updated`/`status` aktualisieren.
