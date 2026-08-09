# T011 Video Regression Receipt

**Result:** PASS

- Der zonierte Video-Vertrag bestand in der Runde-2-Konvergenz mit **60/60**.
- Abgedeckt sind die 20,0-s-Dauergrenze, adressierbare Ersatz-Samples,
  Preroll-begrenzte Ergebniszeiten, Force-Embedding und Retry-Wahrheit.
- Der spätere Post-Audit-Cluster aus `test_lmstudio_vision_wrapper.py`,
  `test_video_pipeline_truth.py` und `test_video_analysis_resume.py` bestand
  zusätzlich mit **48 passed** in **25,26 s**.
- Die Live-VLM-Prüfung gegen ein echtes Katalogvideo lieferte zehn Tags; Details
  stehen in `post-audit-video-review.md`.

Damit ist TR-367 fokussiert belegt. Der davon getrennte Projektwechsel-Smoke aus
T049 bleibt bis zum A→B-Live-Receipt offen.
