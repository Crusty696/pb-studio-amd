# Zone 02 – Audio-Router und Event/Health-Router
(Status: in Arbeit, Bericht wird abschnittsweise ergänzt)

## Abdeckung
| Datei | Zeilen | vollständig gelesen |
|---|---|---|
| backend/routers/__init__.py | 19 | ja |
| backend/routers/health_router.py | 158 | ja |
| backend/routers/events_router.py | 276 | ja |
| backend/routers/audio_router.py | 3538 | in Arbeit (0 gelesen) |

## Befunde
(events/health vorläufig, siehe unten ergänzt)

## Refactoring-Kandidaten (priorisiert)
## Nicht geprüft / Unsicherheiten

---
## Arbeitsnotizen (Rohstand, wird unten in Befunde überführt) – audio_router.py Z.1-2300 gelesen
- Z.807 `_band_stft_params = band_stft_params` Alias: Nutzer noch zu prüfen
- Z.61 `_same_audio_source`, Z.84 `_find_reusable_stem_files`, Z.1148 u.a.: Aufrufer zu prüfen
- Z.210 `_stem_model_identity` hasht komplette Modelldateien (SHA-256) bei JEDEM Aufruf; wird pro Marker/Pfad/Load mehrfach aufgerufen (Z.98,107,259,291,359,431,491) -> Performance
- Z.1529 `_audio_analysis_pool` max_workers=2 ok; Z.1295 `http_request: Request = None`
