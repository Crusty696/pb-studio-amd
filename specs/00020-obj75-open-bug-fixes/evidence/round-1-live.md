# T028 Live Receipt

**Result:** PASS

- `/gpu/status`, `/brain/stats` und `/shutdown` antworteten im echten
  Backend-Lauf mit HTTP 200; Uvicorn beendete sich regulär.
- Der WPF-Lauf verband `/events/log`, `/events/progress` und `/events/gpu`.
  `logs/wpf_app.log` und `logs/backend.log` enthalten die korrespondierenden
  Start-/Connect-/Stop-Receipts vom 09.08.2026, 09:22–09:26 CEST.
- Zwei Shutdown-Snapshots wurden als vollständige Recovery-Generationen
  committed. Ein erzwungener Abbruch hinterließ nur `PREPARING`; der nächste
  Bootstrap verwarf diese Generation und behielt `CURRENT` am letzten
  bestätigten Stand.
- Der VLM-Wrapper verarbeitete ein Screenshot- und ein echtes
  Katalogvideoframe über `qwen2.5-vl-7b-instruct`, jeweils mit zehn Tags und
  Heartbeats unter fünf Sekunden. Das Modell wurde danach entladen.
- Alle 14 WPF-Hauptviews wurden in zwei vollständigen Automationsrunden geöffnet
  und per Screenshot belegt.

Der spezielle A→B-Auswahlwechsel ist kein Wiederholungsgate für diese Smokes,
sondern bleibt ausschließlich unter T049 offen.
