# T023 14-Tab GUI/UIA/Keyboard

**Datum:** 2026-08-09
**Driver:** `scripts/dev/verify_obj74_14_tabs.py`
**Maschinelles Ergebnis:** `obj74-t023-result.json`

- Exakt 14 Tabs im erwarteten UIA-Baum: PROJEKT, AUDIO, VIDEO, KI-REGIE, TIMELINE, EXPORT, HIRN, SETTINGS, PERFORMANCE, MODELLE, CHAT, TERMINAL, INGEST, ANCHOR.
- UIA-Selektion: 14/14; je Tab Screenshot und sichtbare Controls/Texte gespeichert.
- Ctrl+Tab: kompletter Zyklus AUDIO → ... → ANCHOR → PROJEKT, PASS.
- UIA-Fehler: 0; Minimum pro Tab 52 sichtbare Controls und 31 sichtbare Texte.
- Sichtprüfung: Video zeigt `ANALYSIERT`, `TEILANALYSE`, `NICHT ANALYSIERT`; Director zeigt vollständige, teilweise und offene Clips; Audio-/Anchor-Waveform ist gerendert; Backend-Anzeige ist online.

Ergebnis: PASS.
