"""Wächter: Der VRAM-Budget-Manager muss im Betrieb einen Hardware-Sensor haben.

Audit 2026-08-07. Der Sensor-Gegencheck in ``VRAMBudgetManager`` war zunächst
toter Code: ``self.monitor`` wurde nur von ``VRAMArbiter`` gesetzt, und der
Arbiter hat repo-weit keinen Produktions-Aufrufer. In Produktion blieb der
Monitor damit immer ``None``, und die Eigenbuchhaltung konnte nie gegen die
Realität geprüft werden — live gemessen lag sie um 6591 MB daneben, weil
LM Studio auf derselben Karte liegt.

Die Unit-Tests des Gegenchecks waren grün, weil sie den Monitor selbst
injizieren. Genau das ist das Producer-ohne-Consumer-Muster aus dem Audit
2026-08-05: Feature implementiert, getestet, aber niemand füttert es.
Dieser Test prüft deshalb den Produzenten, nicht das Feature.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJEKT_WURZEL = Path(__file__).resolve().parents[1]
MAIN_PY = PROJEKT_WURZEL / "backend" / "main.py"
ARBITER_PY = PROJEKT_WURZEL / "src" / "pb_studio" / "core" / "vram_arbiter.py"


def _get_vram_manager_aufrufe_mit_monitor(quelle: Path) -> list[int]:
    """Zeilennummern aller ``get_vram_manager(monitor=...)``-Aufrufe."""
    baum = ast.parse(quelle.read_text(encoding="utf-8"), filename=str(quelle))
    treffer: list[int] = []
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        funktion = knoten.func
        name = getattr(funktion, "id", None) or getattr(funktion, "attr", None)
        if name != "get_vram_manager":
            continue
        if any(kw.arg == "monitor" for kw in knoten.keywords):
            treffer.append(knoten.lineno)
    return treffer


def test_backend_startup_verdrahtet_den_vram_sensor():
    aufrufe = _get_vram_manager_aufrufe_mit_monitor(MAIN_PY)
    assert aufrufe, (
        "backend/main.py übergibt dem VRAM-Budget-Manager keinen Monitor mehr. "
        "Ohne diesen Aufruf ist sensor_free_vram_mb() im Betrieb wirkungslos "
        "und die Diskrepanz-Warnung kann nie feuern — die Unit-Tests bleiben "
        "trotzdem grün, weil sie den Monitor selbst injizieren."
    )


def test_arbiter_bleibt_der_einzige_andere_monitor_produzent():
    """Nur ein Ort außer main.py darf den Monitor setzen — der alte Arbiter.

    Der Test dokumentiert den Ist-Zustand. Kommt ein weiterer Produzent dazu,
    ist zu klären, welcher gewinnt: Der Manager ist ein Singleton und übernimmt
    einen nachgereichten Monitor nur, solange noch keiner gesetzt ist.
    """
    quellen = [
        p
        for p in (PROJEKT_WURZEL / "src").rglob("*.py")
        if "ui_legacy_archived" not in p.parts
    ]
    quellen += list((PROJEKT_WURZEL / "backend").rglob("*.py"))

    produzenten = {
        p.relative_to(PROJEKT_WURZEL).as_posix()
        for p in quellen
        if _get_vram_manager_aufrufe_mit_monitor(p)
    }

    assert produzenten == {
        "backend/main.py",
        "src/pb_studio/core/vram_arbiter.py",
    }, f"Unerwartete Monitor-Produzenten: {sorted(produzenten)}"


def test_sensor_gegencheck_existiert_und_faellt_offen_aus():
    """Ohne Monitor darf der Gegencheck nichts melden statt zu werfen."""
    from pb_studio.core.vram_budget_manager import VRAMBudgetManager

    VRAMBudgetManager.reset_for_testing()
    try:
        mgr = VRAMBudgetManager(monitor=None, max_vram_mb=16000)
        assert mgr.monitor is None
        assert mgr.sensor_free_vram_mb() is None
        # Darf keine Ausnahme werfen — Telemetrie kippt keine Allokation.
        mgr.register_model("ohne_sensor", "Ohne Sensor", 100)
        assert mgr.reserve("ohne_sensor") is True
    finally:
        VRAMBudgetManager.reset_for_testing()
