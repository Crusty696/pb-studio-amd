# ADR-006: Render-Pipeline-Architektur

**Status:** Accepted
**Datum:** 2026-03-06
**Entscheider:** David Lochmann (Owner)
**Kontext:** WPF + FastAPI Hybrid, AMD DirectML, Phase G-J abgeschlossen

---

## Kontext

PB Studio rendert Video-Timelines durch Konkatenation einzelner Clips mit Master-Audio-Muxing.
Die aktuelle Implementierung besteht aus **zwei** Python-Klassen mit ähnlicher Verantwortung:

| Klasse | Datei | Strategie |
|--------|-------|-----------|
| `BatchRenderer` | `rendering/final_renderer.py` | Timeline → 30-Clip-Chunks → Concat-Demuxer (löst Windows CMD-Limit) |
| `RenderService` | `rendering/render_service.py` | Mixed-Footage-Normalisierung → Scale/Padding/FPS-Anpassung → AMF Encode |

Beide Klassen überschneiden sich: Encoder-Detection, Subprocess-Calls, Temp-File-Verwaltung.
Der `render_router.py` ruft `_execute_render()` auf, der intern `RenderService` nutzt.
`BatchRenderer` wird nur bei sehr langen Projekten (>30 Clips) explizit aktiviert.

**Frage:** Soll die Render-Pipeline zu einer **direkten C# MediaFoundation/WinRT-Pipeline** migriert werden, oder bleibt sie in Python/FFmpeg?

---

## Decision

**Beibehaltung der Python/FFmpeg AMF Pipeline. BatchRenderer und RenderService werden zu einer einzigen `UnifiedRenderer`-Klasse konsolidiert.**

C# MediaFoundation wird explizit abgelehnt.

---

## Options Considered

### Option A: Status Quo (Python/FFmpeg AMF, zwei Klassen)

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Mittel (zwei ähnliche Klassen, redundante Encoder-Detection) |
| AMD-Kompatibilität | Hoch (hevc_amf, h264_amf, av1_amf vollständig getestet) |
| Encoder-Flexibilität | Hoch (Auto-Detect: hevc_amf → h264_amf → h264_mf → libx264) |
| Wartbarkeit | Niedrig (Redundanz: 2× Encoder-Detection, 2× Temp-File-Cleanup) |
| Windows CMD-Limit | Gelöst (BatchRenderer 30-Clip-Chunks) |
| Team-Know-How | Hoch |

**Pros:**
- Bewährt: 14/14 Smoke-Tests PASSED
- FFmpeg AMF direkt auf GPU (kein CPU-Roundtrip)
- Vollständige Encoder-Kontrolle (Quality Params, FPS, Bitrate)
- Kein neuer Tech-Stack notwendig

**Cons:**
- Zwei Klassen mit redundanter Logik (BatchRenderer + RenderService)
- Encoder-Detection wird zweimal ausgeführt (bei BatchRenderer UND RenderService)
- Temp-File-Management an zwei Stellen
- `OUTPUT_FPS = 30` in BatchRenderer ist hardcoded (BUG-026 in RenderService behoben, BatchRenderer nicht angepasst)

---

### Option B: C# MediaFoundation / WinRT Video Encoding

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Sehr Hoch (neues Framework, P/Invoke oder COM Interop) |
| AMD-Kompatibilität | Unklar (MF nutzt DXVA2/D3D11VA, nicht DirectML) |
| Encoder-Flexibilität | Niedrig (nur H.264/H.265 via MFT, kein AV1 AMF) |
| AMF-Optimierung | Keine (MF nutzt eigene AMD-Treiber-Integration, nicht AMF direkt) |
| Concat-Pipeline | Nicht nativ (Timeline-Concat muss manuell implementiert werden) |
| Wartbarkeit | Niedrig initial (kein bestehendes Know-How) |
| Team-Know-How | Niedrig |

**Pros:**
- Native Windows-Integration (kein externer FFmpeg-Prozess)
- Potential für tiefere GPU-Pipeline-Integration
- Weniger Prozess-Overhead (kein subprocess)

**Cons:**
- **AMF-Qualität schlechter als direktes FFmpeg AMF** – MediaFoundation nutzt eine abstrahierte Schicht, FFmpeg ruft AMF-SDK direkt auf
- Keine AV1-Unterstützung via MF (AMF AV1 ist FFmpeg-exklusiv)
- Timeline-Concat-Demuxer-Äquivalent fehlt komplett in MF
- Audio-Muxing (PCM → AAC → MP4 Mux) komplexer in C#
- Verstößt gegen Architektur-Regel: Core-Logik bleibt in Python (ADR-002)
- Bricht die klare Frontend/Backend-Trennung (Rendering IST Backend)
- Kein Weg zurück ohne kompletten Rewrite

---

### Option C: Python/FFmpeg AMF mit `UnifiedRenderer` (Konsolidierung)

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Niedrig (Refactoring bestehender Klassen) |
| AMD-Kompatibilität | Hoch (identisch mit Option A) |
| Encoder-Flexibilität | Hoch (identisch mit Option A) |
| Wartbarkeit | Hoch (eine Klasse, ein Encoder-Cache, ein Temp-Manager) |
| Windows CMD-Limit | Gelöst (Chunk-Strategie wird beibehalten) |
| Risiko | Niedrig (kein neuer Tech-Stack) |

**Pros:**
- Eliminiert BatchRenderer/RenderService-Redundanz
- Encoder-Detection einmal, gecacht als Klassen-Variable (bereits in RenderService vorhanden: `_working_encoder`)
- `target_fps: float` statt hardcoded `OUTPUT_FPS = 30` (BUG-026 Konsistenz)
- Einheitlicher Progress-Callback statt zwei Callbacks
- Weniger Test-Coverage notwendig

**Cons:**
- Kurzfristiger Aufwand: Migration von BatchRenderer-Aufrufen
- Muss BUG-026-Konsistenz explizit für Batch-Pfad sicherstellen

---

## Trade-off Analysis

**Option B (C# MediaFoundation) ist technisch unterlegen und architektonisch falsch:**

1. AMF-Qualität: FFmpeg kommuniziert direkt mit dem AMF SDK (nicht via MF-Abstraktion). Tests zeigen, dass direkte AMF-Calls bessere Bitrate-Effizienz erreichen als MF-Wrapper.
2. AV1: `av1_amf` ist nur via FFmpeg verfügbar. MediaFoundation unterstützt AV1-Encoding erst ab Windows 11 22H2 und nur via Software-Fallback auf älteren AMD-Treibern.
3. ADR-002-Verstoß: Rendering-Logic gehört in Python Core. C# ist ausschließlich für UI zuständig.
4. Concat-Pipeline: FFmpeg's `concat` Demuxer ist eine bewährte, dokumentierte Lösung. Ein Äquivalent in C# würde einen vollständigen Media-Framework-Stack erfordern.

**Option C (UnifiedRenderer) ist die richtige Entscheidung:**
- Kein neues Risiko, nur Verbesserung der bestehenden Lösung
- Löst die konkrete Schwachstelle (Redundanz, BUG-026-Inkonsistenz)
- Bleibt innerhalb der definierten Architektur-Grenzen (ADR-002)

---

## Consequences

**Wird einfacher:**
- Encoder-Detection: Einmal gecacht, überall verfügbar
- Temp-File-Management: Zentrales `_cleanup_temp_files()` an einer Stelle
- Testing: Eine Klasse zu mocken statt zwei
- Progress-Reporting: Einheitlicher Callback für alle Render-Pfade
- FPS-Handling: `target_fps: float` überall konsistent (kein hardcoded `OUTPUT_FPS = 30`)

**Wird schwieriger:**
- Kurze Migrations-Phase: `BatchRenderer` Aufrufer müssen auf `UnifiedRenderer` umgestellt werden
- render_engine.py und preview_renderer.py müssen geprüft werden (nutzen sie BatchRenderer direkt?)

**Muss neu bewertet werden:**
- AV1 AMF (`av1_amf`): Stabilität auf AMD RX 6000/7000 Series prüfen – experimentell laut FFmpeg-Docs
- HDR-Rendering (BT.2020): Aktuell nicht unterstützt, könnte via `hevc_amf` + `colorspace`-Filter hinzugefügt werden

---

## Implementation Plan (UnifiedRenderer)

### Phase 1: Analyse (vor Implementierung)

```
1. Welche Dateien rufen BatchRenderer auf?
   → grep -r "BatchRenderer" src/ backend/

2. Welche Dateien rufen RenderService auf?
   → grep -r "RenderService" backend/

3. render_engine.py: Eigene Encoder-Logic oder delegiert an BatchRenderer/RenderService?
```

### Phase 2: UnifiedRenderer-Klasse

```python
# src/pb_studio/rendering/unified_renderer.py
class UnifiedRenderer:
    """
    Konsolidierter Renderer: BatchRenderer + RenderService vereint.

    Strategie:
    - Encoder-Detection: einmal gecacht (_working_encoder Klassenvar)
    - Chunk-Strategie: CHUNK_SIZE = 30 (Windows CMD-Limit)
    - FPS: target_fps: float (kein hardcoded int)
    - Temp-Dir: zentral verwaltet
    - Progress: einheitlicher Callback(phase: str, percent: float)
    """
    CHUNK_SIZE = 30
    _working_encoder: Optional[str] = None
    _encoder_lock = threading.Lock()
```

### Phase 3: Migration

```
1. UnifiedRenderer schreiben (Tests: alle bestehenden BatchRenderer + RenderService Tests)
2. render_router.py auf UnifiedRenderer umstellen
3. BatchRenderer und RenderService als @deprecated markieren
4. Smoke-Tests: 14/14 PASSED
5. E2E-Test mit C:\Users\david\Videos\test_data\video
6. BatchRenderer + RenderService nach 1 Release-Zyklus löschen
```

### Kritische Constraints

- `CHUNK_SIZE = 30` MUSS beibehalten werden (Windows 8191-Zeichen-Limit)
- `target_fps: float` mit `vf_filter fps={fps:.3f}` (23.976 korrekt)
- KEIN CPU-Fallback für GPU-Fehler – Fehler wird als Exception propagiert
- `with_gpu_task("renderer")` im Router bleibt (VRAMBudgetManager)

---

## Action Items

- [ ] 1. `grep -r "BatchRenderer\|RenderService" backend/ src/` ausführen – alle Aufrufer identifizieren
- [ ] 2. `render_engine.py` und `preview_renderer.py` prüfen – delegieren sie an BatchRenderer?
- [ ] 3. `UnifiedRenderer` in `src/pb_studio/rendering/unified_renderer.py` implementieren
- [ ] 4. render_router.py `_execute_render()` auf `UnifiedRenderer` umstellen
- [ ] 5. BUG-026-Konsistenz: `target_fps: float` überall, `OUTPUT_FPS = 30` entfernen
- [ ] 6. Alle Smoke-Tests (14/14) + E2E-Tests ausführen
- [ ] 7. CLAUDE.md aktualisieren (ADR-006, UnifiedRenderer-Eintrag)

**Priorität:** Mittel – aktuelle Pipeline funktioniert. Migration vor nächstem Feature-Release.
**Geschätzter Aufwand:** 2–4 Stunden (Implementierung) + 1 Stunde (Tests)

---

## Rejected Alternatives Summary

| Option | Grund der Ablehnung |
|--------|---------------------|
| C# MediaFoundation | ADR-002-Verstoß, schlechtere AMF-Qualität als FFmpeg, kein AV1, kein Concat-Demuxer |
| NVENC | AMD-Hardware, kein CUDA (eiserne Regel) |
| CPU-only libx264/libx265 | GPU-Rendering-Anforderung, OOM-Risiko bei CPU-Auslastung durch ML-Parallel-Tasks |
