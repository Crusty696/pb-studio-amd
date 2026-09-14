"""Die Testinfrastruktur darf das Produktionsverhalten nicht diktieren.

Audit 2026-08-29: conftest.isolated_test_database ist autouse und ruft
clear_project_state() ungeschuetzt in Setup und Teardown. Jeder Wurf aus dem
Produktionscode wuerde damit ~1540 Tests in Fixture-Errors verwandeln - die
Funktion ist dauerhaft auf "melden statt werfen" festgenagelt, egal was
fachlich richtig waere.

Zwei Zusicherungen:
1. Verhalten - die Kapselung schluckt den Wurf und meldet ihn.
2. Verdrahtung - die Fixture ruft clear_project_state NICHT mehr direkt.
"""

import ast
import importlib
import logging
import pathlib
from unittest.mock import patch as mock_patch

import pytest

conftest = importlib.import_module("conftest")

CONFTEST_PATH = pathlib.Path(__file__).resolve().parent / "conftest.py"


class TestResetHelperBehaviour:
    def test_helper_survives_a_raising_clear_project_state(self, caplog):
        """Ein Wurf darf die Suite nicht reissen - aber er muss sichtbar sein.

        Der Patch geht auf das conftest-Modul-Global: die Hilfsfunktion loest
        den Namen ueber conftest.__dict__ auf. Ein Patch auf _brain_singleton
        waere hier wirkungslos.

        Bewusst mock_patch statt monkeypatch: isolated_test_database fordert
        dieselbe funktionsskopierte monkeypatch-Instanz an und wird VOR ihr
        finalisiert. _explode waere im Fixture-Teardown noch aktiv und wuerde
        in jedem Lauf eine zweite BrainResetFailure erzeugen - Dauerrauschen in
        genau dem Kanal, den diese Kapselung als Signal benutzt. mock_patch ist
        ohne create=True genauso streng wie monkeypatch.setattr ohne
        raising=False, die Tippfehlersicherung bleibt also erhalten.
        """

        def _explode() -> None:
            raise RuntimeError("unbind kaputt")

        with mock_patch.object(conftest, "clear_project_state", _explode):
            with caplog.at_level(logging.WARNING):
                with pytest.warns(conftest.BrainResetFailure, match="Setup"):
                    conftest._reset_brain_project_state("Setup")

        assert any(
            record.levelno >= logging.WARNING
            and "clear_project_state" in record.getMessage()
            and "Setup" in record.getMessage()
            for record in caplog.records
        ), "Der verschluckte Wurf wurde nicht mit Phase ins Log geschrieben"

    def test_helper_is_a_no_op_when_the_import_failed(self):
        """Der bestehende ImportError-Pfad bleibt erhalten.

        Kein raising=False: nach der Aenderung ist clear_project_state ein
        Modul-Global von conftest. Die strikte Form faengt einen Tippfehler
        im Attributnamen, die nachsichtige verdeckt ihn.
        """
        with mock_patch.object(conftest, "clear_project_state", None):
            conftest._reset_brain_project_state("Teardown")


class TestResetHelperWiring:
    def test_fixture_does_not_call_clear_project_state_directly(self):
        """Wiring-Guard: die Fixture muss ueber die Kapselung gehen.

        Grenze dieses Guards, damit sie benannt ist: er prueft den Quelltext,
        nicht die Laufzeit. Wer den Aufruf in einen nie erreichten Zweig legt,
        bleibt gruen.

        Bewusst nur isolated_test_database, nicht alle autouse-Fixtures: es gibt
        genau eine conftest.py in Tests/, und keine ihrer beiden anderen
        autouse-Fixtures ruft clear_project_state. Eine Verallgemeinerung wuerde
        eine Regel behaupten, die nirgends gebraucht wird - und in Tests/ ist der
        direkte Aufruf teils gewollt (test_silent_persistence_failures).
        """
        tree = ast.parse(CONFTEST_PATH.read_text(encoding="utf-8"))

        fixture = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "isolated_test_database"
            ),
            None,
        )
        assert fixture is not None, "Fixture isolated_test_database nicht gefunden"

        # Auch die Attributform erfassen: bs.clear_project_state() oder
        # _brain_singleton.clear_project_state() waere sonst ein gruener
        # Rueckfall. Das Muster ist nicht hypothetisch - Tests im Repo rufen
        # die Funktion bereits in dieser Form auf.
        called = set()
        for node in ast.walk(fixture):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)

        assert "clear_project_state" not in called, (
            "isolated_test_database ruft clear_project_state direkt - damit "
            "diktiert die Testinfrastruktur wieder, ob die Funktion werfen darf"
        )
        assert "_reset_brain_project_state" in called, (
            "die Fixture geht nicht ueber _reset_brain_project_state"
        )
