# LM Studio VLM Diagnosis — 2026-08-11

## Autoritativer Receipt

- Zusammenfassung: `lmstudio-vlm-receipts-r3.json`.
- SHA-256:
  `6a86be9f00816e9af95f7b30addbc7317c77bba32a68988a55701f000efbb679`.
- Die früheren Receipts ohne Suffix und mit `-r2` sind durch die korrigierte
  CLI-Warte- und SSE-Auswertung überholt und nicht autoritativ.
- Offizielles privates Serverlog:
  `logs/obj76_lmstudio_server_20260811_r7.jsonl`.
- Serverlog SHA-256:
  `f8f21adb40ceefe4aa09c8f5fea16fc5b61a13a786dbf6f0eaf0bc35d8b2bb6d`.

## Ergebnis

- Das korrigierte Werkzeug wartet zuerst auf das terminale Ergebnis von
  `lms load` und prüft erst danach Prozess-/API-Wahrheit.
- Konfiguriert: `qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive`; offizieller
  Load scheiterte mit `Error: Engine protocol startup was aborted.`.
- Kontrolle: `qwen2.5-vl-7b-instruct`; offizieller Load scheiterte mit
  demselben Fehler.
- Beide Load-Receipts sind `null`, beide Call-Listen leer. Es wurde keine
  vermeintliche Bereitschaft aus einem Zwischenstatus abgeleitet.
- Das zuvor geladene fremde Modell `agents-a1-uncensored-mtp-apex` wurde mit
  Context 65536 wiederhergestellt und als `idle` bestätigt.
- Keine erfolgreiche kalte oder warme Captioning-Antwort liegt vor. OOM, ABI
  oder Treiberfehler sind nicht belegt und werden nicht behauptet.

## Diagnosevertrag

- `pytest Tests/test_lmstudio_diagnostic_contract.py -q`
- Ergebnis: 2 passed, 0 failed in 15,04 s.
- Belegt: CLI-Terminalerfolg muss vor einem akzeptierten `lms ps idle` liegen;
  ein CLI-Loadfehler kann keinen Ready-Receipt erzeugen.

## Gate

- T009: als bounded Diagnose mit Zustandswiederherstellung abgeschlossen.
- Normaler Tagging-Erfolg, Restart/Resume, Canary und Bulk bleiben gesperrt.
