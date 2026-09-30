# T013 – Real-Media-Workflow über die Backend-API (2026-09-30)

Nutzerentscheid: Variante A (API statt GUI-Klicks; GUI-Zugriff abgelehnt).
Abweichung von T013-Wortlaut: neues Projekt `t013_psy_20260930` statt bestehendem QA-Projekt;
Bedienung über dieselben Endpunkte wie die WPF, nicht über Buttons.

## Umgebung
- Start über `launch.ps1` (Owner-Token + LHM), `/health` → `gpu_available: true`
- Vision: LM Studio `qwen2.5-vl-7b-instruct`, Runtime `llama.cpp-win-x86_64-vulkan-avx2@2.47.0` (kein ROCm)
- DB-Backup vorher: `data/backups/t013_pre_20260930/pb_studio.db` (10 Projekte, 1681 Media, integrity ok)

## Ablauf und Ergebnis
| Schritt | Ergebnis |
|---|---|
| `POST /project/create` | 200, db_project_id 10 |
| `POST /audio/import` | 200, 21,2 s, Mix 3299,46 s |
| `POST /video/import` (56 Clips, 8 je Ordner aus `Eigene_Videos\Video`) | 200, 3,2 s |
| `POST /audio/analyze` | 200, 171,3 s: 136,36 BPM, E minor, 7401 Beats, 2300 Downbeats, 50 Strukturabschnitte, 30 Subtracks |
| `POST /video/analyze` ×56 | 56/56 200; scenes/motion/embedding/colors/captions `completed`; 10 Tags je Clip; 60 s Warmup, danach 4,5–5,9 s/Clip |
| `POST /pacing/generate` | 200, 16,3 s: 2889 Cuts, lückenlos 0–3299,46 s, 44/56 Clips genutzt, nie gleicher Clip direkt hintereinander |
| `POST /render/start` h264_amf | completed, `validated`, ~340 fps |
| ffprobe (unabhängig) | h264 1920×1080, 98 984/98 984 Pakete, AAC, 3299,47 s, 4854 MB |
| save → close → open | 200; Timeline 2889 Einträge erhalten |
| **App komplett beendet (CloseMainWindow, RUNTIME_DIRTY weg) → neu gestartet → open** | Timeline-Hash `a2d4a0d19ec38ac3`, Tag-Hash `6ac68b89c40bd120`, Audio-Werte: **identisch** |

## Befunde (nicht behoben)
1. **Struktur kommt im Pacing nicht an:** 2872/2889 Cuts `segment_type=transition` trotz 50 Strukturabschnitten.
2. **Brain-Achsen melden `missing_or_synthetic`** für beat/onset/snare/hihat/energy, obwohl die Analyse diese Listen liefert; nur kick `available`.
3. **Monotones Schnitttempo:** Cut-Länge 1,0–2,55 s, Median 1,10 s über 55 min.
4. **Semantik aus:** `cross_modal_projector_untrained` (erwartbar ohne 20 Bewertungen).
5. **`/video/clips` veraltet:** direkt nach Analyse 0 Clips mit Tags, nach Reopen 56/56.
6. **44/56 Clips `analysis_status=partial`** nur wegen `audio_key=unavailable` (Clips ohne Tonspur).
7. **Kick-Plausibilität offen:** 16 944 Kicks gegen 7401 Beats; 30 Subtracks in 55 min (Referenz fehlt, nicht bewertet).
8. **Tags jetzt englisch** (2026-08-07: deutsch).
9. **Projekt-Pfad doppelt verschachtelt:** `path` + Name → `.../t013_psy_20260930/t013_psy_20260930`.
10. **DB-Bereinigung beim Backend-Start (Ursache offen):** Projekt `gui_qc_20260925` (Ordner manuell gelöscht) samt 572 Media-Zeilen entfernt, Projekt `test` von ID 10 auf 9 umnummeriert und von 396 auf 204 Media reduziert (entspricht seinem project.json). Backup vorhanden.
11. `run-pb-studio/driver.ps1`: 30-s-Backend-Timeout zu knapp (Start gemessen 33 s); ohne verbundenen Client fährt das Backend nach ~4,5 min selbst herunter.

## Offen für T013
GUI-Sichtprüfung (Projekt in der WPF öffnen, Tabs/Tags/Timeline ansehen) durch den Nutzer.
