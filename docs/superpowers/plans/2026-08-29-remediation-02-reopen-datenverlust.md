# Reopen-Datenverlust Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das erneute Öffnen eines bereits geöffneten Projekts darf ungespeicherte Cuts nicht mehr verwerfen.

**Architecture:** `open_project` lädt den Medienkatalog und die Datei-Timeline in einen `candidate_state` und übergibt ihn an `_activate_project` → `install_project_state`, das den Laufzeitzustand **ersetzt**. Zeigt die Anfrage auf das bereits offene Projekt, ist dieser Austausch kein Wechsel, sondern ein reiner Datenverlust: der RAM-Stand wird durch den älteren Dateistand überschrieben. Der Plan setzt einen Same-Path-Guard **vor** das Laden des Kandidaten und macht den Reopen zu einem No-Op, der den aktuellen Zustand zurückmeldet.

**Tech Stack:** FastAPI, Pydantic v2, pytest, `backend/app_state.py` (`AppState`, dataclass mit `RLock`).

---

## Vorbedingungen — am Quelltext verifiziert, nicht angenommen

Diese Angaben wurden vor dem Schreiben des Plans gegen HEAD (`ddc4187`) geprüft. Prüfe sie trotzdem selbst, bevor du änderst — in dieser Session war ein ungeprüfter Plan mehrheitlich falsch.

| Fakt | Beleg |
|---|---|
| `open_project` ist `async def`, Zeile 634, `response_model=ProjectInfo`, dekoriert mit `@recovery_write_operation("project-files")` | `backend/routers/project_router.py:632-638` |
| **Es gibt keinen Same-Path-Guard** in `open_project` | Grep über `current_project` in der Datei: kein Vergleich mit `request.path` |
| `_load_timeline_into_state(project_path, candidate_state)` läuft **vor** `_activate_project` | `:686` bzw. `:721` |
| `install_project_state` ersetzt den Laufzeitzustand aus dem Kandidaten | `backend/app_state.py:421-451` |
| `_activate_project` hat seit `def8f3d` einen Same-Path-Guard, der beim Reopen das **Persistieren** überspringt | `project_router.py:458` |
| `ProjectInfo` verlangt nur `name` und `path`; alles andere hat Defaults | `backend/schemas/project_schemas.py:18-27` |
| `ProjectInfo(**project_data)` wird bereits mit Extra-Schlüsseln (`project_uuid`) aufgerufen — Pydantic ignoriert sie | `project_router.py:747` |
| `state.get_timeline_snapshot()`, `get_audio_clips_snapshot()`, `get_video_clips_snapshot()` existieren | `app_state.py:635`, Nutzung in `project_router.py:674-679` |
| `_state_lock` ist ein `RLock` | `app_state.py:186` |

**Randbedingungen:**
- Interpreter `.venv/Scripts/python.exe`, immer `PYTHONPATH=src`.
- pytest **immer** mit eigenem `--basetemp=.pytest_tmp_t02x`. `--basetemp` darf **nie** aus `pytest.ini` entfernt werden (Windows-Symlink → `PermissionError: [WinError 5]`).
- Im Arbeitsbaum liegen ~25 **fremde** uncommittete Änderungen aus `patch.py`. Nicht anfassen, nicht committen. `git add` nur die Dateien dieses Plans.
- Commit-Message per Bash-Heredoc mit `git commit -F -`, nicht per PowerShell-Here-String.
- Zeilennummern verschieben sich, sobald du die erste Änderung schreibst. Lokalisiere per grep.

## Die Entscheidung, die dieser Plan trifft

Reopen wird ein **No-Op**, der den aktuellen Zustand zurückmeldet — nicht ein „speichern, dann neu laden". Begründung: „Öffne das Projekt, das bereits offen ist" hat keine andere sinnvolle Bedeutung, und ein stilles Speichern als Nebenwirkung eines Lesevorgangs wäre überraschend. Der Preis: ein echtes „von Platte neu laden" ist über diesen Endpunkt nicht mehr möglich. Das ist heute schon kaputt (es verliert Daten), und ein bewusstes Reload gehört in einen eigenen Endpunkt.

## File Structure

| Datei | Verantwortung | Änderung |
|---|---|---|
| `backend/routers/project_router.py` | Projekt-Lebenszyklus über HTTP | Same-Path-Guard am Anfang von `open_project` |
| `Tests/test_reopen_keeps_unsaved_timeline.py` | Beweist, dass der RAM-Stand den Reopen überlebt | neu |

Keine Schema-, Routen- oder C#-Änderung. Kein WPF-Build nötig.

---

## Task 1: Same-Path-Guard in `open_project`

**Files:**
- Create: `Tests/test_reopen_keeps_unsaved_timeline.py`
- Modify: `backend/routers/project_router.py` (in `open_project`, nach dem `exists()`-Check, vor `meta = _read_project_meta(project_path)`)

- [ ] **Step 1: Write the failing test**

Create `Tests/test_reopen_keeps_unsaved_timeline.py`:

```python
"""Das erneute Oeffnen des bereits offenen Projekts darf nichts verwerfen.

Audit 2026-08-29: open_project laedt die Datei-Timeline in einen candidate_state
und _activate_project ersetzt damit ueber install_project_state den kompletten
Laufzeitzustand. Zeigt die Anfrage auf das bereits offene Projekt, ist das kein
Wechsel, sondern Datenverlust - ein Pacing-Lauf, der noch nicht gespeichert
wurde, ist danach weg.
"""

import importlib
import json

import pytest
from fastapi import HTTPException

from backend.app_state import AppState

project_router = importlib.import_module("backend.routers.project_router")


def _make_project(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps(
            {
                "name": name,
                "audio_count": 0,
                "video_count": 0,
                "has_timeline": False,
                "created_at": "2026-08-29T00:00:00+00:00",
                "modified_at": "2026-08-29T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    return root


def _state_with_open_project(root, timeline):
    state = AppState()
    state.current_project = {
        "name": root.name,
        "path": str(root),
        "db_project_id": 1,
    }
    state.set_timeline(timeline)
    return state


class TestReopenIsANoOp:
    def test_reopen_keeps_the_unsaved_timeline_in_ram(self, tmp_path, monkeypatch):
        root = _make_project(tmp_path, "alpha")
        unsaved = [
            {"clip_id": "clip_1", "start_time": 0.0, "end_time": 2.0, "metadata": {}},
            {"clip_id": "clip_2", "start_time": 2.0, "end_time": 4.5, "metadata": {}},
        ]
        state = _state_with_open_project(root, unsaved)

        monkeypatch.setattr(
            project_router.config, "project_dir", str(tmp_path), raising=False
        )

        info = asyncio.run(
            project_router.open_project.__wrapped__.__wrapped__(
                project_router.ProjectOpen(path=str(root)), state
            )
        )

        assert len(state.get_timeline_snapshot()) == 2, (
            "Reopen desselben Projekts hat den ungespeicherten RAM-Stand ersetzt"
        )
        assert info.has_timeline is True
        assert info.path == str(root)

    def test_reopen_does_not_read_the_project_from_disk(self, tmp_path, monkeypatch):
        """Der Guard muss VOR dem Laden greifen, nicht danach."""
        root = _make_project(tmp_path, "alpha")
        state = _state_with_open_project(
            root,
            [{"clip_id": "clip_1", "start_time": 0.0, "end_time": 1.0, "metadata": {}}],
        )

        monkeypatch.setattr(
            project_router.config, "project_dir", str(tmp_path), raising=False
        )

        def _must_not_run(*args, **kwargs):
            raise AssertionError(
                "open_project hat den Medienkatalog geladen, obwohl das Projekt "
                "bereits offen ist - der Guard steht zu spaet"
            )

        monkeypatch.setattr(
            project_router, "_load_timeline_into_state", _must_not_run
        )

        import asyncio

        asyncio.run(
            project_router.open_project.__wrapped__.__wrapped__(
                project_router.ProjectOpen(path=str(root)), state
            )
        )

    def test_opening_a_different_project_is_unaffected(self, tmp_path, monkeypatch):
        """Der Guard darf nicht zu breit greifen."""
        root_a = _make_project(tmp_path, "alpha")
        _make_project(tmp_path, "beta")
        state = _state_with_open_project(
            root_a,
            [{"clip_id": "clip_1", "start_time": 0.0, "end_time": 1.0, "metadata": {}}],
        )

        monkeypatch.setattr(
            project_router.config, "project_dir", str(tmp_path), raising=False
        )

        seen = []

        def _record(project_path, target_state):
            seen.append(project_path)
            return False

        monkeypatch.setattr(project_router, "_load_timeline_into_state", _record)

        import asyncio

        with pytest.raises((HTTPException, Exception)):
            asyncio.run(
                project_router.open_project.__wrapped__.__wrapped__(
                    project_router.ProjectOpen(path=str(tmp_path / "beta")), state
                )
            )

        assert seen, (
            "Beim Oeffnen eines ANDEREN Projekts muss der Ladepfad weiterhin laufen"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_reopen_keeps_unsaved_timeline.py -v --basetemp=.pytest_tmp_t02x`

Expected: `test_reopen_keeps_the_unsaved_timeline_in_ram` und `test_reopen_does_not_read_the_project_from_disk` FAIL. Notiere die exakte Ausgabe.

**Wenn die Tests aus einem anderen Grund scheitern** (z. B. `__wrapped__` löst die Dekoratoren nicht auf, oder `ProjectOpen` heißt anders): melde das und passe den Aufrufweg an, statt die Zusicherung abzuschwächen. Der Zugriff auf die undekorierte Funktion ist ein Testdetail; die Zusicherung ist es nicht. `Tests/test_project_close_anchor_contracts.py` und `Tests/test_timeline_survives_project_switch.py` zeigen, wie in diesem Repo Router-Funktionen direkt gerufen werden — orientiere dich daran.

- [ ] **Step 3: Add the guard**

In `backend/routers/project_router.py`, in `open_project` **unmittelbar nach** dem `if not project_path.exists(): raise HTTPException(404, ...)` und **vor** `meta = _read_project_meta(project_path)`:

```python
    # Reopen desselben Projekts ist KEIN Wechsel. Der weitere Verlauf laedt den
    # Medienkatalog und die Datei-Timeline in einen candidate_state, den
    # _activate_project ueber install_project_state (app_state.py:421) als
    # kompletten Laufzeitzustand einsetzt. Beim bereits offenen Projekt wuerde
    # damit der aeltere Dateistand den RAM-Stand ersetzen - ein Pacing-Lauf, der
    # noch nicht gespeichert wurde, waere ersatzlos weg.
    # Der Guard steht bewusst VOR dem Laden: er soll den Austausch verhindern,
    # nicht nachtraeglich reparieren.
    with state._state_lock:
        active_project = dict(state.current_project or {})
    active_path = active_project.get("path")
    if active_path and Path(active_path).resolve() == project_path:
        active_meta = _read_project_meta(project_path)
        logger.info(
            "Projekt ist bereits geoeffnet, Reopen bleibt folgenlos: %s",
            project_path,
        )
        return ProjectInfo(
            name=active_project.get("name", project_path.name),
            path=str(project_path),
            db_project_id=active_project.get("db_project_id"),
            audio_count=len(state.get_audio_clips_snapshot()),
            video_count=len(state.get_video_clips_snapshot()),
            has_timeline=bool(state.get_timeline_snapshot()),
            created_at=active_meta.get("created_at")
            or active_project.get("created_at"),
            modified_at=active_meta.get("modified_at")
            or active_project.get("modified_at"),
        )
```

`Path`, `logger`, `ProjectInfo` und `_read_project_meta` sind in der Datei bereits vorhanden — kein neuer Import.

**Zu `has_timeline`:** der Wert kommt hier bewusst aus dem RAM (`get_timeline_snapshot()`), nicht aus `project.json`. Das ist der einzige Ort, an dem beide auseinanderlaufen können, und der RAM-Stand ist der aktuellere. Er ist zugleich die Zusicherung, die der erste Test prüft.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_reopen_keeps_unsaved_timeline.py -v --basetemp=.pytest_tmp_t02x`

Expected: 3 passed.

- [ ] **Step 5: Gegenprobe — der Test muss am Guard hängen**

Nimm den Guard testweise zurück (Block auskommentieren), lass die Tests laufen, zeige die rote Ausgabe, stelle die Datei **byte-exakt** wieder her (`git diff` muss danach nur die beabsichtigte Änderung zeigen).

Das ist keine Formalie: in dieser Session hat eine Gegenprobe an der falschen Stelle einmal einen irreführend grünen Lauf erzeugt.

- [ ] **Step 6: Regression**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_project_persistence.py Tests/test_timeline_survives_project_switch.py Tests/test_t410_project_switch_e2e.py Tests/test_project_close_anchor_contracts.py Tests/test_reopen_keeps_unsaved_timeline.py -q --basetemp=.pytest_tmp_t02x`

Expected: alle passed. Achte besonders auf `test_t410_project_switch_e2e.py` — der ruft `_activate_project` direkt und wechselt zwischen zwei Projekten; der Guard darf ihn nicht berühren.

- [ ] **Step 7: Commit**

```bash
git add Tests/test_reopen_keeps_unsaved_timeline.py backend/routers/project_router.py
git commit -F - <<'EOF'
fix(project): Reopen des offenen Projekts verwirft keine ungespeicherten Cuts mehr

open_project laedt Medienkatalog und Datei-Timeline in einen candidate_state,
den _activate_project ueber install_project_state (app_state.py:421) als
kompletten Laufzeitzustand einsetzt. Ein Same-Path-Guard fehlte, deshalb hat
das erneute Oeffnen des bereits offenen Projekts den RAM-Stand durch den
aelteren Dateistand ersetzt - ein noch nicht gespeicherter Pacing-Lauf war
danach weg.

Der Guard steht vor dem Laden und macht den Reopen zu einem No-Op, der den
aktuellen Zustand zurueckmeldet. has_timeline kommt dabei aus dem RAM, nicht
aus project.json - das ist der aktuellere der beiden Werte.

Bewusste Einschraenkung: ein echtes "von Platte neu laden" ist ueber diesen
Endpunkt nicht mehr moeglich. Es war es vorher auch nicht sinnvoll, weil es
Daten verlor; ein Reload gehoert in einen eigenen Endpunkt.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Abschluss

- [ ] **Vollsuite sequenziell:** `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/ -q --basetemp=.pytest_tmp_final03`
      Erwartung: **7 failed / 1523+ passed / 0 errors**. Die 7 sind bekannt und zuordenbar (5 davon aus dem uncommitteten `patch.py`-Stand). Kein neuer Fehler.
      Während des Laufs **keine** Datei ändern — ein solcher Lauf musste in dieser Session schon einmal verworfen werden.
- [ ] **Roadmap nachziehen:** in `2026-08-29-audit-remediation-ROADMAP.md` den Folgepunkt „`install_project_state` verwirft beim Reopen ungespeicherte Cuts" abhaken.
- [ ] **Obsidian-Vault:** `INDEX.md` (`updated`, Status) und `log.md` ergänzen.
- [ ] **Push** und Remote-SHA gegen lokal verifizieren.

## Was dieser Plan ausdrücklich nicht löst

- **`modified_at` bleibt nach Close-ohne-Save stale.** Eigener Punkt in der Roadmap.
- **Ein bewusstes „Reload von Platte"** gibt es danach nicht. Falls jemand das braucht, ist ein eigener Endpunkt der richtige Ort — nicht eine Sonderbedeutung von `/project/open`.
