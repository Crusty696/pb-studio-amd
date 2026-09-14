# Live Shutdown Verification — 2026-08-11

## Probe

- HEAD-Basis: `958353b25575b650c85f052f2a6a2149790f9577` plus OBJ-76-Arbeitsstand.
- Reale WPF-App, kanonischer Launcher und Backend wurden gemeinsam erfasst.
- Projekt `obj74_qc_20260809_001`, Medium 207 (`test_10s`): Tags und Farben
  angefordert; Szenen, Motion und SigLIP für diese Probe deaktiviert.
- WPF wurde während des kalten Captioning-Aufrufs gegen das konfigurierte
  qwen3.6-VLM geschlossen.

## Ergebnis

- Kein `RuntimeError: No response returned` und kein ASGI-Traceback.
- Backend protokollierte den Abbruch als erwarteten Shutdown der
  `/video/analyze`-Anfrage.
- Persistenz: Gesamtstatus `failed`; `captions=interrupted`,
  `colors=interrupted`, nicht angeforderte Stages `skipped`, jeweils mit
  explizitem Interruption-Receipt.
- Exitcodes: WPF 0, Supervisor 0, Backend 0.
- Recovery-Shutdown-Snapshot:
  `20260811T000428041390Z-7d8315262f8e43f9b9b1132b8ada89fc`.

## Capture und fokussierte Verträge

- Sanitisiert: `evidence/capture/obj76_live_20260811_020009_sanitized.jsonl`
- SHA-256: `7891bf3fe21b88be6b9c6a127b4b2d3ee5f305fb1dbe7d1f9bbfb70db0e5cae0`
- 122 Records, eine Session, terminaler `monitor_stopped`, Drop-Count 0.
- Drei fokussierte Deadline-/Cancellation-/Resume-Tests: 3 passed, 0 failed.
- Ergebnis: T013–T015 bestanden. T003 bleibt offen, weil der direkte VLM-
  Transport zwar grün ist, der reale App-Pfad aber noch keinen nutzbaren
  Tag-Commit und damit keinen erfolgreichen Restart/Resume belegt.
