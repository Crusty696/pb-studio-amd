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

## Nachtrag 2026-09-30/10-01 — Auflösung der Befunde

| Befund | Ergebnis | Commit |
|---|---|---|
| 1 Struktur → transition | Streaming-Struktur vergibt bewusst neutral `section` (8fe5604); `_canonical_segment` faltete das in `transition`. `section` ist jetzt eigener neutraler Wert. | bf596c3 |
| 2 Brain-Achsen nur Kick | **Zurückgezogen, Fehldeutung:** Trigger-Achsen gelten pro Cut-Trigger; 2685/2889 Cuts waren Kick-Cuts. | — |
| 5 `/video/clips` ohne Tags | Analyse schrieb Tags nicht in den In-Memory-Clip; Liste las nur diesen. Beides korrigiert. | (dieser Commit) |
| 6 partial ohne Tonspur | `audio_key=unavailable` zählt nicht als Fehler. | fc25f21 |
| Captions ohne Figuren | Nur Frame 1 zählte (first-come + `[:10]`); Prompt ohne Figuren; Parser zerhackte Listen; Dubletten. | dd3ee87, a558db2 |
| Modellwechsel | Ein Modell (qwen3.5-9b, `reasoning_effort=none`); LM-Studio-`tool_use` wurde nie gelesen → Chat fiel auf Ollama. | 8a91eed, a558db2 |
| 10 DB-Bereinigung beim Start | **Kein Bereinigungscode, sondern Recovery-Rollback** (siehe unten). | a380a13 |
| Tests schreiben ins echte Recovery-Verzeichnis | conftest isoliert `LOCALAPPDATA`; Prozess-Lock. | a380a13 |

### Befund 10 im Detail: DB-Rollback auf 2026-09-24
Log `logs/backend.log`:
- 2026-09-28 05:15 Bootstrap „ready generation=20260924T051049…“, obwohl 2026-09-25T20:15 bereits CURRENT war — Ursache vor dieser Sitzung, nicht geloggt (wahrscheinlich Testlauf gegen echtes Recovery-Verzeichnis).
- 2026-09-28 11:05 Shutdown-Snapshot fehlgeschlagen → CURRENT blieb 09-24.
- 2026-09-30 00:48:53 zweites Backend (launch.ps1) startete, während das Driver-Backend noch herunterfuhr; sah RUNTIME_DIRTY, begann Restore auf 09-24, scheiterte an gesperrter DB → APPLYING-Journal.
- 2026-09-30 00:54:59 nächster Start: „recovered generation=20260924…“ → DB auf 09-24 zurückgesetzt. Verloren: Projekt `gui_qc_20260925` (572 Media) und `test` von 2026-09-28 (396 Media); das heutige Projekt 9 „test“ ist die Fassung vom 2026-09-23.
- Vorhanden zur Wiederherstellung: Generation `20260929T224820168496Z-bc85…` und `data/backups/t013_pre_20260930/pb_studio.db`. Nicht zurückgespielt (IDs 9–11 neu belegt; Nutzerentscheid nötig).
- Behoben: exklusiver Prozess-Lock in `ensure_recovery_ready`/`mark_runtime_dirty` (live belegt: zweites Backend abgewiesen, Journal unverändert).
