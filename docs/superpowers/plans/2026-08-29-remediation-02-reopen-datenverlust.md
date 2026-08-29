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
| `@router.post("/open", ...)` auf `:633`, `@recovery_write_operation` auf `:634`, `async def open_project(` auf **`:635`** | `backend/routers/project_router.py:633-635` |
| **Es gibt keinen Same-Path-Guard** in `open_project` — die Funktion liest `state.current_project` überhaupt nicht | `:635-747` |
| `_load_timeline_into_state(project_path, candidate_state)` auf **`:688`**, `await _activate_project(` auf **`:727`** | dort |
| `install_project_state` spannt `:421-478`; der eigentliche Austausch steht in **`:456-476`**, `self.current_timeline = timeline` auf **`:470`** | `backend/app_state.py` |
| `_activate_project` hat seit `def8f3d` einen Same-Path-Guard auf **`:461`**, der nur das **Persistieren** überspringt — er verhindert den Austausch **nicht** | `project_router.py:461` |
| `ProjectInfo` verlangt nur `name` und `path`; alles andere hat Defaults | `backend/schemas/project_schemas.py:18-27` |
| `ProjectInfo(**project_data)` wird bereits mit Extra-Schlüssel `project_uuid` aufgerufen — `response_model` verwirft ihn | `project_router.py:739`, `:747` |
| `get_audio_clips_snapshot` `:533`, `get_video_clips_snapshot` `:539`, `get_timeline_snapshot` `:635`, `set_timeline` `:640` | `app_state.py` |
| `_state_lock` ist ein `RLock` | `app_state.py:186` |
| `config` ist in `project_router` ein `backend.config.ServerConfig` mit Attribut `project_dir` (ein `Path`) | `config.py:78`, Nutzung `project_router.py:643` |
| `_read_project_meta(path) -> dict` gibt bei fehlender/kaputter Datei `{}` zurück und wirft nie | `project_router.py:236-244` |

**Der Datenverlust ist empirisch bewiesen**, nicht hergeleitet: der undekorierte `open_project` wurde gegen einen State ausgeführt, dessen `current_project` bereits auf das Ziel zeigte —

```
vorher  RAM-Timeline: 2
nachher RAM-Timeline: 0
response: has_timeline=False
```

Kette: `:688` lädt in den Kandidaten → kein `timeline.json` → `candidate_state.set_timeline([])` → `:727 _activate_project` → `:487 state.reset(...)` + `:488 install_project_state(...)` → `app_state.py:470`.

**Über die UI erreichbar**, nicht nur über die API: `ProjectOverviewViewModel.cs:165-183` reicht `dialog.FolderName` aus dem Ordnerdialog direkt an `/project/open` weiter. Wer den bereits offenen Ordner erneut auswählt, löst es aus. `ProjectService.cs:67-95` vergleicht keine Pfade. Es gibt keinen Auto-Open beim Start (`main.py:294-295`).

**Kein bestehender Schutz** — weder im Router noch in `install_project_state` noch im Frontend.

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

Die Tests fahren den **echten Endpunkt** über `TestClient` mit `dependency_overrides` — nicht die undekorierte Funktion. Grund: `open_project` hat genau **eine** `__wrapped__`-Ebene (`router.post` setzt keine), ein doppeltes `__wrapped__` wirft `AttributeError`. Über `TestClient` laufen zudem die Dekoratoren mit, statt umgangen zu werden.

Die `stub_project_db_lookup`-Fixture ist aus `Tests/test_timeline_survives_project_switch.py:265-302` übernommen. **Sie ist nicht optional:** ohne sie schreibt der Test eine echte Zeile in `data/pb_studio.db` — das ist bei der Vorabprüfung dieses Plans tatsächlich passiert und musste von Hand entfernt werden.

```python
"""Das erneute Oeffnen des bereits offenen Projekts darf nichts verwerfen.

Audit 2026-08-29: open_project laedt die Datei-Timeline in einen candidate_state
(project_router.py:688) und _activate_project ersetzt damit ueber
install_project_state (app_state.py:470) den kompletten Laufzeitzustand. Zeigt
die Anfrage auf das bereits offene Projekt, ist das kein Wechsel, sondern
Datenverlust - gemessen: RAM-Timeline 2 -> 0. Der Same-Path-Guard in
_activate_project (:461) ueberspringt nur das Persistieren, nicht den Austausch.
"""

import importlib
import json
from pathlib import Path

import pytest

from backend.app_state import AppState

project_router = importlib.import_module("backend.routers.project_router")


def _timeline_entries():
    return [
        {"clip_id": "clip_1", "start_time": 0.0, "end_time": 2.0, "metadata": {}},
        {"clip_id": "clip_2", "start_time": 2.0, "end_time": 4.5, "metadata": {}},
    ]


class TestReopenIsANoOp:
    @pytest.fixture
    def fresh_state(self):
        from backend.app_state import get_app_state
        from backend.main import app

        state = AppState()
        app.dependency_overrides[get_app_state] = lambda: state
        yield state
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self, fresh_state):
        from fastapi.testclient import TestClient
        from backend.main import app

        return TestClient(app)

    @pytest.fixture(autouse=True)
    def stub_project_db_lookup(self, monkeypatch):
        """Ohne diese Stubs schreibt der Test in die produktive Datenbank."""
        from pb_studio.data.repositories.project_repository import ProjectRepository

        records: dict[int, dict] = {}
        next_id = {"value": 500}

        def fake_find(project_path) -> int | None:
            normalized = str(Path(project_path).resolve())
            for project_id, record in records.items():
                if record["path"] == normalized:
                    return project_id
            return None

        def fake_find_or_create(project_path, project_name, meta=None) -> int:
            existing = fake_find(project_path)
            if existing is not None:
                return existing
            project_id = next_id["value"]
            next_id["value"] += 1
            records[project_id] = {"path": str(Path(project_path).resolve())}
            return project_id

        def fake_create_owned(_repo, _name, data, _owner_token) -> int:
            project_id = next_id["value"]
            next_id["value"] += 1
            records[project_id] = {"path": str(Path(data["path"]).resolve())}
            return project_id

        def fake_update(_repo, project_id, name=None, data=None):
            return None

        monkeypatch.setattr(
            project_router, "_find_or_create_project_db_record", fake_find_or_create
        )
        monkeypatch.setattr(project_router, "_find_project_db_record_id", fake_find)
        monkeypatch.setattr(ProjectRepository, "create_owned_project", fake_create_owned)
        monkeypatch.setattr(ProjectRepository, "update_project", fake_update)
        return records

    def test_reopen_keeps_the_unsaved_timeline_in_ram(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        assert client.post(
            "/project/create", json={"name": "Alpha", "path": str(tmp_path)}
        ).status_code == 200
        project_path = tmp_path / "Alpha"

        # Ein Pacing-Lauf, der noch NICHT gespeichert wurde.
        fresh_state.set_timeline(_timeline_entries())

        response = client.post("/project/open", json={"path": str(project_path)})

        assert response.status_code == 200
        assert len(fresh_state.get_timeline_snapshot()) == 2, (
            "Reopen desselben Projekts hat den ungespeicherten RAM-Stand ersetzt"
        )
        assert response.json()["has_timeline"] is True
        assert response.json()["path"] == str(project_path)

    def test_reopen_does_not_load_the_project_from_disk(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        """Der Guard muss VOR dem Laden greifen, nicht danach."""
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        assert client.post(
            "/project/create", json={"name": "Alpha", "path": str(tmp_path)}
        ).status_code == 200
        project_path = tmp_path / "Alpha"
        fresh_state.set_timeline(_timeline_entries())

        def _must_not_run(*args, **kwargs):
            raise AssertionError(
                "open_project hat den Projektzustand geladen, obwohl das Projekt "
                "bereits offen ist - der Guard steht zu spaet"
            )

        monkeypatch.setattr(project_router, "_load_timeline_into_state", _must_not_run)

        assert client.post(
            "/project/open", json={"path": str(project_path)}
        ).status_code == 200

    def test_opening_a_different_project_still_loads_it(
        self, client, fresh_state, tmp_path, monkeypatch
    ):
        """Der Guard darf nicht zu breit greifen."""
        from backend.config import config

        monkeypatch.setattr(config, "project_dir", tmp_path)
        for name in ("Alpha", "Beta"):
            assert client.post(
                "/project/create", json={"name": name, "path": str(tmp_path)}
            ).status_code == 200

        # /project/create hat zuletzt Beta aktiviert - zurueck auf Alpha.
        assert client.post(
            "/project/open", json={"path": str(tmp_path / "Alpha")}
        ).status_code == 200

        seen = []
        real_loader = project_router._load_timeline_into_state

        def _record(project_path, target_state):
            seen.append(Path(project_path))
            return real_loader(project_path, target_state)

        monkeypatch.setattr(project_router, "_load_timeline_into_state", _record)

        response = client.post(
            "/project/open", json={"path": str(tmp_path / "Beta")}
        )

        assert response.status_code == 200
        assert seen == [tmp_path / "Beta"], (
            "Beim Oeffnen eines ANDEREN Projekts muss der Ladepfad weiterhin laufen"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/test_reopen_keeps_unsaved_timeline.py -v --basetemp=.pytest_tmp_t02x`

Expected: `test_reopen_keeps_the_unsaved_timeline_in_ram` FAIL (RAM-Timeline ist 0 statt 2, `has_timeline` ist `False`) und `test_reopen_does_not_load_the_project_from_disk` FAIL (die `AssertionError` aus `_must_not_run` schlägt durch). `test_opening_a_different_project_still_loads_it` ist schon **vor** dem Guard grün — das ist Absicht, er ist der Wächter gegen einen zu breiten Guard, kein Fixnachweis. Sag das im Bericht ausdrücklich, damit die drei Grünen später nicht als drei Belege gelesen werden.

Notiere die exakte Ausgabe. **Scheitert ein Test aus einem anderen Grund** — Fixture-Fehler, `/project/create` liefert nicht 200, Owner-Capability —, melde das und repariere den Aufbau, statt die Zusicherung abzuschwächen.

**Prüfe vor dem Lauf**, dass keine Zeile in `data/pb_studio.db` entsteht: `sqlite3 data/pb_studio.db "SELECT COUNT(*) FROM projects"` vor und nach dem Lauf muss denselben Wert liefern. Genau das ist bei der Vorabprüfung dieses Plans schiefgegangen.

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
        logger.info(
            "Projekt ist bereits geoeffnet, Reopen bleibt folgenlos: %s",
            project_path,
        )
        return ProjectInfo(
            name=meta.get("name", active_project.get("name", project_path.name)),
            path=str(project_path),
            db_project_id=active_project.get("db_project_id"),
            audio_count=len(state.get_audio_clips_snapshot()),
            video_count=len(state.get_video_clips_snapshot()),
            # ODER-Semantik wie in def8f3d (:742): der RAM-Stand ist der
            # aktuellere, aber eine vorhandene timeline.json darf nicht
            # verschwiegen werden, nur weil der RAM gerade leer ist.
            has_timeline=bool(state.get_timeline_snapshot())
            or bool(meta.get("has_timeline")),
            created_at=meta.get("created_at") or active_project.get("created_at"),
            modified_at=meta.get("modified_at") or active_project.get("modified_at"),
        )
```

**Setze den Block hinter das bestehende `meta = _read_project_meta(project_path)` (`:649`) und nutze dieses `meta` mit** — die Datei wird in dieser Funktion ohnehin schon zweimal gelesen (`:649` und `:687`), ein dritter Zugriff wäre unnötig.

`Path`, `logger`, `ProjectInfo` und `_read_project_meta` sind bereits vorhanden — kein neuer Import.

**Zu `has_timeline`:** der ursprüngliche Planentwurf nahm nur den RAM-Wert. Das hätte die ODER-Semantik gebrochen, die `def8f3d` bewusst eingeführt hat (`:742`): RAM leer, `timeline.json` vorhanden → der Guard hätte `false` gemeldet, wo der heutige Code `true` liefert. Die ODER-Form oben erhält beides.

**Zu den Zählern:** `audio_count`/`video_count` kommen aus dem RAM, der Normalpfad nimmt `meta` mit Verzeichnis-Fallback (`:690-695`). Das ist eine bewusste Abweichung — beim bereits offenen Projekt ist der RAM die Wahrheit. Kein Frontend-Bruch: `ApiClient.cs:1310` (`record ProjectInfo`) nutzt die Zähler nur zur Anzeige, und alle Felder sind non-null.

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
      **Keine Zahl vorregistrieren.** Miss die Grundlinie und berichte das Delta gegen den letzten dokumentierten Lauf (7 failed / 1522 passed / 13 skipped / 0 errors, Stand `ddc4187`). Entscheidend: **kein neuer Fehler**, und die Zunahme bei `passed` muss sich vollständig aus den neuen Tests erklären.
      Während des Laufs **keine** Datei ändern — ein solcher Lauf musste in dieser Session schon einmal verworfen werden.
- [ ] **DB-Unversehrtheit:** `sqlite3 data/pb_studio.db "PRAGMA integrity_check"` muss `ok` liefern und `SELECT COUNT(*) FROM projects` denselben Wert wie vor der Arbeit. Bei der Vorabprüfung dieses Plans ist eine Testzeile in der produktiven Datenbank gelandet.
- [ ] **Roadmap nachziehen:** in `2026-08-29-audit-remediation-ROADMAP.md` den Folgepunkt „`install_project_state` verwirft beim Reopen ungespeicherte Cuts" abhaken.
- [ ] **Obsidian-Vault:** `INDEX.md` (`updated`, Status) und `log.md` ergänzen.
- [ ] **Push** und Remote-SHA gegen lokal verifizieren.

## Was dieser Plan ausdrücklich nicht löst

- **`modified_at` bleibt nach Close-ohne-Save stale.** Eigener Punkt in der Roadmap.
- **Ein bewusstes „Reload von Platte"** gibt es danach nicht. Falls jemand das braucht, ist ein eigener Endpunkt der richtige Ort — nicht eine Sonderbedeutung von `/project/open`.
