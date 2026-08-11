# Live Tagging und Restart/Resume — 2026-08-11

## App-Probe

- Werkzeug: `scripts/diagnostics/verify_video_resume_live.ps1`.
- Testprojekt: dediziertes lokales QC-Projekt; Clip-ID 1; ausschließlich
  Captioning und Farben angefordert.
- Zwei getrennte Backendprozesse wurden nacheinander gestartet und sauber
  beendet. Port 8765 war danach frei.
- Beide Antworten waren `partial`: Farben `completed`, Captioning `failed`,
  `tags=[]`, `tag_source=none`, Fehler
  `Keine Tags von verfuegbarem Vision-Provider erzeugt`.
- Der persistierte Wahrheits-Hash war in beiden Läufen identisch:
  `bc53da7f7de6bd6e045613807c4c6a7818b2c6a53bf31a546c05af6ebe4754cd`.
  Weil Captioning fehlgeschlagen war, wurde die Stage nach dem Neustart korrekt
  erneut versucht; ein erfolgreicher Resume-No-op ist damit nicht belegt.

## Korrelation

- Erster Backendlog SHA-256:
  `f7e6731d2be0fa33cc05fcaf6ffb322f15188bd1c230ac0f0ad92a1b559f669c`.
- Zweiter Backendlog SHA-256:
  `ed9e24850bc0219c0671bdad27cc8536bc1693b0609d0bd8fb4ca60366a3c88c`.
- Das konfigurierte qwen3.6-VLM scheiterte im App-Lauf beim JIT-Load, qwen2.5
  lief in das 45-s-Budget und qwen3.5 scheiterte ebenfalls beim Load. Danach
  endete die Receipt-gebundene Drei-Kandidaten-Kette bounded; der fehlende
  Moondream-ONNX-Fallback wurde ehrlich als unavailable behandelt.
- Der direkte isolierte r4-Lauf belegt zwar Engine-/SSE-Transporterfolg, aber
  qwen3.6 verbrauchte das vollständige 64-Token-Budget ohne nachgewiesenen
  finalen Tag-Inhalt. `reasoning_content` wird zu Recht nicht als Tag-Payload
  interpretiert.

## Isolierungsgrenze

- Drei Versuche, ausschließlich das vorbestehende Modell
  `agents-a1-uncensored-mtp-apex` vor der App-Probe kontrolliert zu entladen,
  wurden vor jedem Projektschreibzugriff abgebrochen: Ein anderer `lms-cli`-
  Client lud dieselbe Identität während der zehnsekündigen Settle-Phase erneut.
- Vorher/Nachher blieb die Identität exakt `idle`, Context 65536; es wurde kein
  fremder Prozess beendet und kein Modellzustand erzwungen.

## Gate

- T003 bleibt offen. Zuständiger Produktfix liegt in der separat reservierten
  Videoanalyse-Zone: Captioning muss bei Reasoning-VLMs einen nutzbaren finalen
  Content erzeugen oder bounded auf ein nachweislich taglieferndes Vision-Modell
  wechseln. Danach ist genau diese App-Probe einmal zu wiederholen.
- T019 und Bulk bleiben NO-GO.
