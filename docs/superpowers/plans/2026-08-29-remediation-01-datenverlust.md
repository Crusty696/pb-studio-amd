# Datenverlust und stille Fehler — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vier Stellen beheben, an denen PB Studio bei jedem Lauf Daten verliert oder einen Fehlschlag als Erfolg meldet.

**Architecture:** Vier voneinander unabhängige Tasks, jeder nach TDD (Test rot → minimale Implementierung → Test grün → Commit). Kein Task hängt von einem anderen ab; die Reihenfolge folgt dem Schadensausmaß. Task 1 entfernt ein Duplikat, Task 2 macht drei verschluckte Fehler sichtbar, Task 3 sichert die Timeline vor Projektwechsel, Task 4 beseitigt ein Race beim parallelen Speichern.

**Tech Stack:** Python 3.11, pytest, FastAPI, SQLite, FAISS, C# .NET 9 WPF.

---

## Vorbedingungen

**Diese drei Punkte gelten für jeden Task in diesem Plan.**

1. **Eigenes `--basetemp` bei jedem pytest-Aufruf.** `pytest.ini` setzt `--basetemp=.pytest_tmp2`, einen für alle Läufe gemeinsamen Pfad, den pytest beim Sessionstart löscht. Zwei gleichzeitige Läufe zerstören sich gegenseitig. Die Option darf **nicht** entfernt werden — ohne sie scheitert unter Windows jeder Lauf mit `PermissionError [WinError 5]` beim `pytest-current`-Symlink.

2. **`PYTHONPATH=src` bei jedem Aufruf.** Kein editable install.

3. **Der Arbeitsbaum enthält 23 fremde geänderte Dateien** aus einem `patch.py`-Lauf. Fünf der sieben aktuell roten Tests stammen von dort. Referenzstand vor Beginn:

```
7 failed · 1497 passed · 13 skipped · 0 errors
```

Rote Tests, die **nicht** von diesem Plan verursacht werden und rot bleiben dürfen:
`test_audit_sdd_gate`, `test_openapi_snapshot_drift`, `test_t357_gpu_wpf_nullability_contracts`, `test_video_pipeline_truth` (3×), `test_viewmodel_binding_wiring`.

---

## File Structure

| Datei | Verantwortung | Task |
|---|---|---|
| `Tests/test_no_duplicate_dict_keys.py` | **neu** — AST-Wächter, verbietet doppelte String-Keys in Dict-Literalen repo-weit | 1 |
| `src/pb_studio/audio/spectral_analyzer.py` | Spektralanalyse; enthält den doppelten `mel_bands`-Key | 1 |
| `Tests/test_silent_persistence_failures.py` | **neu** — prüft, dass Persistenzfehler sichtbar werden statt verschluckt | 2 |
| `backend/_brain_singleton.py` | Bindung des Brain an die Projekt-`state.db`; verschluckt `unbind_project_state` | 2 |
| `src/pb_studio/data/vector_store.py` | FAISS-Index + Persistenz; verschluckt zwei Save-Fehler | 2 |
| `Tests/test_timeline_survives_project_switch.py` | **neu** — Timeline muss den Projektwechsel überleben | 3 |
| `backend/routers/project_router.py` | Projekt-Lifecycle; speichert vor Wechsel nicht, nutzt feste Stage-Dateinamen | 3, 4 |
| `Tests/test_concurrent_project_save.py` | **neu** — zwei gleichzeitige Saves dürfen sich nicht zerstören | 4 |
| `PBStudio.UI/Services/ProjectService.cs` | einzige Projektoperation ohne `_projectTransitionGate` | 4 |

---

## Task 1: Doppelter `mel_bands`-Key im Spektralergebnis

**Files:**
- Create: `Tests/test_no_duplicate_dict_keys.py`
- Modify: `src/pb_studio/audio/spectral_analyzer.py:150-160`

Der Dict in `analyze_from_array` enthält `"mel_bands"` zweimal. Python nimmt den letzten Eintrag, es ist also kein Syntaxfehler — aber `mel_db.tolist()` wird zweimal ausgewertet. Bei einem 60-Minuten-Mix sind das rund 40 Millionen Floats, doppelt materialisiert, für einen Wert, den repo-weit **niemand liest**.

- [ ] **Step 1: Write the failing test**

Create `Tests/test_no_duplicate_dict_keys.py`:

```python
"""Waechter: kein Dict-Literal im Produktionscode darf einen String-Key doppelt fuehren.

Audit 2026-08-29: `spectral_analyzer.py` fuehrte "mel_bands" zweimal im selben Literal,
die zweite Zeile zusaetzlich falsch eingerueckt. Python akzeptiert das (letzter gewinnt),
der Wert wird aber zweimal berechnet. Fingerabdruck eines fehlgeschlagenen Edits.
"""

import ast
import pathlib

import pytest

ROOTS = [pathlib.Path("src"), pathlib.Path("backend")]


def _duplicate_string_keys(tree: ast.AST) -> list[tuple[int, list[str]]]:
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [
            k.value
            for k in node.keys
            if isinstance(k, ast.Constant) and isinstance(k.value, str)
        ]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            findings.append((node.lineno, dupes))
    return findings


def _python_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for root in ROOTS:
        files.extend(
            p for p in root.rglob("*.py") if "ui_legacy_archived" not in p.parts
        )
    return files


def test_no_dict_literal_repeats_a_string_key():
    offenders = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:  # pragma: no cover - defekte Datei ist ein eigener Fehler
            pytest.fail(f"{path} laesst sich nicht parsen: {exc}")
        for lineno, dupes in _duplicate_string_keys(tree):
            offenders.append(f"{path}:{lineno} fuehrt {dupes} mehrfach")

    assert not offenders, "Doppelte Dict-Keys gefunden:\n  " + "\n  ".join(offenders)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_no_duplicate_dict_keys.py -v --basetemp=.pytest_tmp_t01`

Expected: FAIL mit `src\pb_studio\audio\spectral_analyzer.py:150 fuehrt ['mel_bands'] mehrfach`

- [ ] **Step 3: Remove the duplicated key**

In `src/pb_studio/audio/spectral_analyzer.py`, im Dict ab Zeile 150, die **zweite** `mel_bands`-Zeile ersatzlos löschen. Sie ist an der Einrückung erkennbar — 12 statt 16 Leerzeichen:

```python
            return {
                "times": times.tolist(),
                "band_energies": band_energies,
                "centroids": centroids.tolist(),
                "mel_bands": mel_db.tolist(),
                "band_means": band_means,
                "band_variances": band_variances,
                "events": events,
                "duration": float(len(y) / sr),
            }
```

Die zu entfernende Zeile lautet exakt:

```python
            "mel_bands": mel_db.tolist(),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_no_duplicate_dict_keys.py -v --basetemp=.pytest_tmp_t01`

Expected: PASS

- [ ] **Step 5: Verify no regression in the spectral contract**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_audio_spectral_onsets_contract.py -q --basetemp=.pytest_tmp_t01`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add Tests/test_no_duplicate_dict_keys.py src/pb_studio/audio/spectral_analyzer.py
git commit -m "fix(audio): drop the duplicated mel_bands key from the spectral result"
```

---

## Task 2: Verschluckte Persistenzfehler sichtbar machen

**Files:**
- Create: `Tests/test_silent_persistence_failures.py`
- Modify: `backend/_brain_singleton.py:75-82`
- Modify: `src/pb_studio/data/vector_store.py:184-196`
- Modify: `src/pb_studio/data/vector_store.py:817-828`

Drei `except Exception: pass` an Stellen, an denen ein Fehlschlag Daten kostet:

**`_brain_singleton`** — scheitert `unbind_project_state()`, bleibt die Verbindung an die `state.db` des **geschlossenen** Projekts gebunden, während `_PROJECT_STATE_PATH` schon `None` ist. Jedes folgende `/brain/feedback` schreibt Lerndaten ins falsche Projekt. Der Nutzer erhält HTTP 200 auf `/project/close`.

**`vector_store`** 2× — der letzte FAISS-Persistenzpunkt. Scheitert der Save, gehen alle seit dem letzten Write hinzugefügten Embeddings verloren: ohne Log, ohne Exit-Code, ohne UI-Signal. Beim nächsten Start fehlen Clips im semantischen Index, und der Zeitpunkt ist nicht rekonstruierbar.

- [ ] **Step 1: Write the failing test**

Create `Tests/test_silent_persistence_failures.py`:

```python
"""Persistenzfehler duerfen nicht stillschweigend verschluckt werden.

Audit 2026-08-29: drei `except Exception: pass` an Stellen, an denen ein Fehlschlag
Daten kostet. Ein atexit-Handler darf nicht werfen — aber "nicht werfen" ist nicht
dasselbe wie "nicht melden".
"""

import logging

import pytest


class TestBrainUnbindFailure:
    def test_failed_unbind_forces_state_conn_to_none(self, monkeypatch, caplog):
        """Fail-closed: lieber gar nicht schreiben als ins falsche Projekt."""
        from backend import _brain_singleton
        from pb_studio.brain.brain_service import BrainService

        class ExplodingService:
            def unbind_project_state(self):
                raise RuntimeError("unbind kaputt")

        monkeypatch.setattr(BrainService, "get", staticmethod(lambda: ExplodingService()))

        with caplog.at_level(logging.ERROR):
            _brain_singleton.clear_project_state()

        assert _brain_singleton._PROJECT_STATE_PATH is None
        assert any(
            "unbind" in r.message.lower() or "state" in r.message.lower()
            for r in caplog.records
        ), "fehlgeschlagenes unbind_project_state wurde ohne Logzeile verschluckt"


class TestVectorStoreSaveFailure:
    def test_failed_final_save_is_logged_and_marks_dirty(self, tmp_path, caplog):
        """Ein gescheiterter Abschluss-Save muss auffindbar sein."""
        from pb_studio.data.vector_store import VectorStore

        store = VectorStore(index_path=str(tmp_path / "idx.faiss"), dim=8)

        def explode(*args, **kwargs):
            raise OSError("Platte voll")

        store._save_unlocked = explode

        with caplog.at_level(logging.ERROR):
            store.close()

        assert any(
            r.levelno >= logging.ERROR for r in caplog.records
        ), "gescheiterter FAISS-Save wurde ohne Logzeile verschluckt"
        assert (tmp_path / "idx.faiss.dirty").exists(), (
            "kein Dirty-Marker — der Verlust ist beim naechsten Start nicht feststellbar"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_silent_persistence_failures.py -v --basetemp=.pytest_tmp_t02`

Expected: FAIL — beide Tests. Der erste, weil keine Logzeile erzeugt wird; der zweite, weil weder geloggt noch ein Dirty-Marker geschrieben wird.

- [ ] **Step 3: Make the brain unbind failure loud and fail-closed**

In `backend/_brain_singleton.py`, den Block ab Zeile 75 ersetzen:

```python
    global _PROJECT_STATE_PATH
    _PROJECT_STATE_PATH = None
    try:
        BrainService.get().unbind_project_state()
    except Exception:
        # Audit 2026-08-29: frueher `pass`. Scheitert das Unbind, bleibt die
        # Verbindung an die state.db des GESCHLOSSENEN Projekts gebunden und
        # jedes folgende /brain/feedback schreibt Lerndaten ins falsche Projekt.
        # Im Zweifel gar nicht schreiben statt falsch schreiben.
        logger.error(
            "unbind_project_state fehlgeschlagen - Brain-State wird hart geloest",
            exc_info=True,
        )
        try:
            service = BrainService.get()
            setattr(service, "state_conn", None)
        except Exception:
            logger.error("Brain-State liess sich nicht hart loesen", exc_info=True)
```

Sicherstellen, dass `logger` am Modulanfang existiert:

```python
import logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Make both vector store save failures loud**

In `src/pb_studio/data/vector_store.py`, den `atexit`-Block ab Zeile 184:

```python
            try:
                inst._stop_writer()
                inst._save_on_exit(faiss_mod=_faiss_ref, json_mod=_json_ref, ...)
                inst._closed = True
            except Exception:
                # Audit 2026-08-29: frueher nur `pass`. Ein atexit-Handler darf
                # nicht werfen — melden muss er trotzdem, sonst ist der Verlust
                # der seit dem letzten Write hinzugefuegten Embeddings nicht
                # feststellbar.
                logger.critical(
                    "FAISS-Abschluss-Save fehlgeschlagen - Embeddings seit dem "
                    "letzten Write sind verloren",
                    exc_info=True,
                )
                inst._mark_dirty()
```

Und den Block ab Zeile 817:

```python
        try:
            with self._lock:
                self._save_unlocked(force=True, ...)
        except Exception:
            # Audit 2026-08-29: frueher `pass`.
            logger.error("FAISS-Save fehlgeschlagen", exc_info=True)
            self._mark_dirty()
```

Neue Hilfsmethode auf `VectorStore` ergänzen:

```python
    def _mark_dirty(self) -> None:
        """Persistenter Marker, damit der Verlust beim naechsten Start auffaellt."""
        try:
            marker = pathlib.Path(f"{self.index_path}.dirty")
            marker.write_text(
                f"save failed at {datetime.now(timezone.utc).isoformat()}\n",
                encoding="utf-8",
            )
        except Exception:
            logger.error("Dirty-Marker liess sich nicht schreiben", exc_info=True)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_silent_persistence_failures.py -v --basetemp=.pytest_tmp_t02`

Expected: PASS

- [ ] **Step 6: Verify no regression**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_vector_store.py Tests/test_project_brain_binding.py -q --basetemp=.pytest_tmp_t02`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add Tests/test_silent_persistence_failures.py backend/_brain_singleton.py src/pb_studio/data/vector_store.py
git commit -m "fix(storage): surface persistence failures instead of swallowing them"
```

---

## Task 3: Timeline vor Projektwechsel sichern

**Files:**
- Create: `Tests/test_timeline_survives_project_switch.py`
- Modify: `backend/routers/project_router.py:761-806` (`close_project`)
- Modify: `backend/routers/project_router.py:354-386` (`_activate_project`)

Die Timeline lebt bis zum manuellen `POST /project/save` ausschließlich im RAM. Die Pacing-Engine schreibt ihr Ergebnis über `state.set_timeline(...)` — die einzigen `timeline.json`-Schreiber im ganzen Repo sitzen in `save_project`. Weder `close_project` noch `_activate_project` speichern.

**Wer nach einem Pacing-Lauf das Projekt wechselt, verliert die generierte Timeline ersatzlos.** Save-on-Exit gibt es (`App.xaml.cs:222`), Save-on-Switch nicht.

- [ ] **Step 1: Write the failing test**

Create `Tests/test_timeline_survives_project_switch.py`:

```python
"""Die Timeline muss einen Projektwechsel ueberleben.

Audit 2026-08-29: `close_project` und `_activate_project` speichern nicht. Ein
Pacing-Lauf schreibt nur nach RAM. Wer danach das Projekt wechselt, verliert die
erzeugte Timeline ohne jede Warnung.
"""

import json

from backend.app_state import AppState


def _make_project(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps({"name": name, "audio_count": 0, "video_count": 0}),
        encoding="utf-8",
    )
    return root


class TestTimelinePersistence:
    def test_timeline_is_written_before_the_project_is_closed(self, tmp_path):
        root = _make_project(tmp_path, "alpha")
        state = AppState()
        state.current_project = {"name": "alpha", "path": str(root), "db_project_id": 1}
        state.set_timeline([{"clip_id": 7, "start": 0.0, "end": 2.5}])

        from backend.routers import project_router

        project_router.persist_timeline_for_context(state, root)

        timeline_file = root / "timeline.json"
        assert timeline_file.exists(), (
            "timeline.json wurde beim Schliessen nicht geschrieben - "
            "die Timeline ist nach dem Projektwechsel verloren"
        )
        entries = json.loads(timeline_file.read_text(encoding="utf-8"))
        assert entries and entries[0]["clip_id"] == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_timeline_survives_project_switch.py -v --basetemp=.pytest_tmp_t03`

Expected: FAIL mit `AttributeError: module 'backend.routers.project_router' has no attribute 'persist_timeline_for_context'`

- [ ] **Step 3: Add the helper and call it on both paths**

In `backend/routers/project_router.py` eine Hilfsfunktion ergänzen:

```python
def persist_timeline_for_context(state, project_root: Path) -> bool:
    """Schreibt die aktuelle In-Memory-Timeline nach <root>/timeline.json.

    Audit 2026-08-29: die Timeline war bis zum manuellen /project/save fluechtig.
    Weder close_project noch _activate_project haben gespeichert, die Pacing-Engine
    schreibt nur nach RAM. Ein Projektwechsel nach einem Pacing-Lauf hat die
    erzeugte Timeline ersatzlos verworfen.

    Rueckgabe: True, wenn geschrieben wurde; False, wenn es nichts zu schreiben gab.
    """
    entries = state.get_timeline_snapshot()
    if not entries:
        return False

    path = Path(project_root) / "timeline.json"
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return True
    finally:
        tmp.unlink(missing_ok=True)
```

Erforderliche Importe am Modulanfang sicherstellen: `import os`, `import uuid`, `import json`, `from pathlib import Path`.

In `close_project` **vor** dem Freigeben des Projektkontexts:

```python
    if context.project_root:
        try:
            persist_timeline_for_context(state, context.project_root)
        except Exception:
            logger.error(
                "Timeline konnte vor dem Schliessen nicht gesichert werden",
                exc_info=True,
            )
```

In `_activate_project` **vor** `invalidate_project_context`, nur wenn bereits ein Projekt offen ist:

```python
    previous = state.current_project
    if previous and previous.get("path"):
        try:
            persist_timeline_for_context(state, Path(previous["path"]))
        except Exception:
            logger.error(
                "Timeline des vorherigen Projekts konnte nicht gesichert werden",
                exc_info=True,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_timeline_survives_project_switch.py -v --basetemp=.pytest_tmp_t03`

Expected: PASS

- [ ] **Step 5: Verify no regression**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_project_persistence.py Tests/test_app_state.py -q --basetemp=.pytest_tmp_t03`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add Tests/test_timeline_survives_project_switch.py backend/routers/project_router.py
git commit -m "fix(project): persist the timeline before closing or switching projects"
```

---

## Task 4: Race beim parallelen Speichern

**Files:**
- Create: `Tests/test_concurrent_project_save.py`
- Modify: `backend/routers/project_router.py:700-701` (`_save_project_in_context`)
- Modify: `backend/routers/project_router.py:259-271` (`_restore_file_snapshot`)
- Modify: `PBStudio.UI/Services/ProjectService.cs:98` (`SaveProjectAsync`)

`_save_project_in_context` nutzt **feste** Stage-Dateinamen (`timeline.json.save.tmp`, `project.json.save.tmp`). Bei zwei gleichzeitigen Saves überschreibt B die Stage-Datei von A; A's `finally`-unlink löscht B's Stage-Datei, bevor B sie umbenennen kann; B wirft, und B's Rollback restauriert auf **B's** Vorher-Stand — womit A's bereits committeter Save überschrieben wird.

**Die Vorlage steht 200 Zeilen tiefer in derselben Datei:** `set_anchors` nutzt `f".{path.name}.{uuid.uuid4().hex}.tmp"`.

Erreichbar, weil `ProjectService.SaveProjectAsync` als **einzige** Projektoperation ohne `_projectTransitionGate` läuft und `App.xaml.cs:222` beim Beenden einen weiteren Save auslöst.

- [ ] **Step 1: Write the failing test**

Create `Tests/test_concurrent_project_save.py`:

```python
"""Zwei gleichzeitige Saves duerfen sich nicht gegenseitig zerstoeren.

Audit 2026-08-29: feste Stage-Dateinamen. A's finally-unlink loescht B's
Stage-Datei; B wirft; B's Rollback ueberschreibt A's bereits committeten Save.
"""

import re
import pathlib


def test_save_uses_unique_stage_filenames():
    """Der Stage-Name muss pro Aufruf eindeutig sein.

    Ein Integrationstest fuer das Rennen selbst waere zeitabhaengig und flaky.
    Geprueft wird deshalb die Eigenschaft, die das Rennen ausschliesst:
    der Stage-Name enthaelt einen uuid4-Hex-Anteil.
    """
    source = pathlib.Path("backend/routers/project_router.py").read_text(
        encoding="utf-8"
    )

    match = re.search(
        r"def _save_project_in_context\b.*?(?=\ndef |\Z)", source, re.S
    )
    assert match, "_save_project_in_context nicht gefunden"
    body = match.group(0)

    assert ".save.tmp" not in body, (
        "fester Stage-Dateiname in _save_project_in_context - "
        "zwei gleichzeitige Saves zerstoeren sich gegenseitig"
    )
    assert "uuid4().hex" in body, (
        "kein eindeutiger Stage-Name; Vorbild: set_anchors in derselben Datei"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_concurrent_project_save.py -v --basetemp=.pytest_tmp_t04`

Expected: FAIL mit `fester Stage-Dateiname in _save_project_in_context`

- [ ] **Step 3: Use unique stage filenames**

In `backend/routers/project_router.py`, in `_save_project_in_context` die beiden Zeilen ersetzen:

```python
    stage_token = uuid.uuid4().hex
    timeline_stage = timeline_path.with_name(f".{timeline_path.name}.{stage_token}.tmp")
    meta_stage = meta_path.with_name(f".{meta_path.name}.{stage_token}.tmp")
```

Dasselbe in `_restore_file_snapshot` für den Rollback-Zwischenpfad:

```python
    rollback_tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.rollback.tmp")
```

Sicherstellen, dass `import uuid` am Modulanfang steht.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_concurrent_project_save.py -v --basetemp=.pytest_tmp_t04`

Expected: PASS

- [ ] **Step 5: Put SaveProjectAsync behind the transition gate**

In `PBStudio.UI/Services/ProjectService.cs`, `SaveProjectAsync` in dasselbe Gate ziehen, das `CreateProjectAsync`, `OpenProjectAsync` und `CloseProjectAsync` bereits nutzen:

```csharp
    public async Task<bool> SaveProjectAsync(CancellationToken ct = default)
    {
        // Audit 2026-08-29: SaveProjectAsync lief als einzige Projektoperation
        // ohne dieses Gate. Zusammen mit dem Save-on-Exit aus App.xaml.cs
        // konnten zwei Saves gleichzeitig laufen.
        await _projectTransitionGate.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            return await SaveProjectCoreAsync(ct).ConfigureAwait(false);
        }
        finally
        {
            _projectTransitionGate.Release();
        }
    }
```

Den bisherigen Rumpf von `SaveProjectAsync` in eine private `SaveProjectCoreAsync` mit identischer Signatur verschieben.

- [ ] **Step 6: Build the WPF frontend in Release**

Run: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`

Expected: `0 Warnung(en)`, `0 Fehler`

- [ ] **Step 7: Verify no regression**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_project_persistence.py -q --basetemp=.pytest_tmp_t04`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add Tests/test_concurrent_project_save.py backend/routers/project_router.py PBStudio.UI/Services/ProjectService.cs
git commit -m "fix(project): make concurrent saves safe with unique stage filenames"
```

---

## Abschluss dieses Plans

- [ ] **Vollsuite sequenziell**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/ -q --basetemp=.pytest_tmp_final_01`

Expected: **höchstens 7 failed**, und keiner davon aus diesem Plan. Erlaubte rote Tests siehe Vorbedingungen.

- [ ] **Release-Build**

Run: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`

Expected: 0/0

- [ ] **Roadmap nachziehen:** in `2026-08-29-audit-remediation-ROADMAP.md` die Tasks 1.1–1.4 auf erledigt setzen.

- [ ] **Obsidian-Vault:** `INDEX.md` (Frontmatter `updated`, Status-Sektion) und `log.md` ergänzen.

- [ ] **Offen und bewusst nicht in diesem Plan:** Task 1.5 der Roadmap (Anker-Lesefehler wird als leere Liste ausgegeben). Er gehört fachlich zum Projekt-Router, hängt aber an einer Vertragsentscheidung — HTTP 500 oder ein `source_status`-Feld —, die vor dem Schreiben des Tests getroffen sein muss.
