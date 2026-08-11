# LM Studio VLM Diagnosis — 2026-08-11

## Autoritativer Receipt

- Zusammenfassung: `lmstudio-vlm-receipts-r4.json`.
- SHA-256:
  `4da6dcd32873466b8873165e210591b1bff16a557e7c26d090c2fe558159e8b5`.
- Die Receipts ohne Suffix sowie `-r2` und `-r3` sind durch die korrigierte
  CLI-Warte-, Settle- und SSE-Auswertung überholt und nicht autoritativ.
- Offizielles privates Serverlog:
  `logs/obj76_lmstudio_server_20260811_r8.jsonl`.
- Serverlog SHA-256:
  `e0ddc3059735c4ed94ed7baf745280bd017605bb6a6729fdf009150fe1b79c9b`.

## Ergebnis

- Das Werkzeug wartet auf terminales `lms load`, bestätigt `lms ps idle` und
  lässt nach jedem Unload zehn Sekunden für den Engine-/VRAM-Teardown.
- Konfiguriert: `qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive`; Load PASS,
  danach drei identische SSE-Aufrufe mit HTTP 200 und `[DONE]`. Kalt:
  6,313 s/TTFT 4,672 s; warm: 1,547 s/0,109 s und 1,531 s/0,109 s.
- Kontrolle: `qwen2.5-vl-7b-instruct`; Load PASS, ein SSE-Aufruf mit HTTP 200
  und `[DONE]` in 2,313 s/TTFT 2,250 s.
- Der qwen3.6-Lauf erzeugte dreimal 65 SSE-Datenchunks und erreichte jeweils
  das 64-Token-Budget. Das Serverlog weist auf ein Reasoning-Template hin; der
  Diagnosevertrag hat den finalen `message.content`-Text noch nicht erfasst.
  HTTP 200/`[DONE]` ist daher kein Tagging-Erfolgsbeleg.
- Der Follow-up-Vertrag erfasst deshalb für künftige Receipts getrennt
  `content_length`, `content_sha256`, `content_nonempty`, `reasoning_length` und
  `finish_reason`, ohne Reasoning als Tag-Payload umzudeuten.
- Das zuvor geladene `agents-a1-uncensored-mtp-apex` ist nach dem Lauf wieder
  exakt als `idle` mit Context 65536 vorhanden. Das `restore_error` im r4-JSON
  war ein Diagnose-Fehlalarm für einen bereits identisch vorhandenen Zustand;
  der Follow-up-Vertrag akzeptiert nur eine exakt passende Identität und
  schlägt bei jeder Abweichung fail-closed fehl.

## Diagnosevertrag

- `pytest Tests/test_lmstudio_diagnostic_contract.py -q`
- Ergebnis: dreimal 8 passed, 0 failed (14,85 s; 15,40 s; 15,71 s).
- Belegt: CLI-Terminalerfolg vor Ready-Receipt, Settle nach Unload und
  fail-closed exakte Wiederherstellung eines bereits vorhandenen Modells sowie
  getrennte Content-/Reasoning-Wahrheit.

## Gate

- T009: als bounded Engine-/Transportdiagnose abgeschlossen.
- T003 bleibt offen: Der reale App-Pfad muss nutzbare Tags liefern und sie über
  einen echten Backend-Neustart stage-aware wiederverwenden.
- Canary und Bulk bleiben bis zu diesem Nachweis gesperrt.
