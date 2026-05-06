# Security Audit — PB Studio AMD Edition
**Datum:** 2026-03-05
**Auditor:** Claude (Lead Senior Developer)
**Scope:** Python FastAPI Backend + C# WPF Frontend + SQLite Data Layer
**Risiko-Kontext:** Single-User Desktop-App, localhost-only

---

## Zusammenfassung

| Schweregrad | Anzahl | Status |
|-------------|--------|--------|
| KRITISCH    | 0      | —      |
| HOCH        | 2      | Offen  |
| MITTEL      | 4      | Offen  |
| NIEDRIG     | 3      | Akzeptiert/Info |

**Gesamtbewertung:** Für eine lokale Single-User Desktop-App ist die Sicherheitslage **akzeptabel**. Es gibt keine kritischen Schwachstellen. Die 2 hohen Findings betreffen Path-Traversal-Risiken, die bei einer Netzwerk-Exposition gefährlich wären.

---

## 1. Dependency-Vulnerabilities (CVEs)

### MITTEL — opencv-python==4.9.0.80 (gepinnt)

**Befund:** Fest gepinnte Version. OpenCV hat regelmäßig CVEs (Buffer Overflows bei malformed Bildern). Version 4.9.0.80 ist aus Januar 2024.

**Empfehlung:** Auf `opencv-python>=4.10.0` anheben oder `>=4.9.0,<5.0` verwenden.

### NIEDRIG — Keine pip-audit im CI

**Befund:** Kein automatisiertes CVE-Scanning in der Build-Pipeline.

**Empfehlung:** `pip-audit` oder `safety check` als Pre-Commit oder CI-Step einbauen.

---

## 2. Authentication / Authorization

### INFO — Kein Auth (by Design)

**Befund:** `backend/main.py` Zeile 8: *"Kein Auth, kein HTTPS, kein Multi-User."* — Das ist dokumentiert und für eine localhost Desktop-App korrekt.

**Risiko:** Wenn der Server versehentlich auf `0.0.0.0` statt `127.0.0.1` gebunden wird, wäre jeder im Netzwerk Admin. Config default ist korrekt `127.0.0.1:8765`.

**Status:** Akzeptiert. `FEHLENDE_KOMPONENTEN.md` enthält ein Beispiel mit `host="0.0.0.0"` — das sollte entfernt oder als Warnung markiert werden.

---

## 3. Input-Validation & Injection

### HOCH — Path Traversal in Audio/Video Import

**Befund:** `audio_router.py:48` und `video_router.py:51` akzeptieren beliebige Dateipfade vom Client:

```python
# audio_router.py
audio_path = Path(request.path)
if not audio_path.exists():
    raise HTTPException(...)
```

Es gibt **keine Validierung** ob der Pfad innerhalb eines erlaubten Verzeichnisses liegt. Ein Angreifer (bei Netzwerk-Exposition) könnte beliebige Dateien lesen lassen, z.B. `C:\Windows\System32\config\SAM`.

**Empfehlung:** Path-Sanitization einbauen:
```python
allowed_dirs = [Path(config.project_dir), Path.home() / "Music", Path.home() / "Videos"]
resolved = audio_path.resolve()
if not any(resolved.is_relative_to(d) for d in allowed_dirs):
    raise HTTPException(403, "Pfad außerhalb erlaubter Verzeichnisse")
```

### HOCH — Path Traversal in Render Output

**Befund:** `render_router.py` — `RenderRequest.output_path` wird direkt als Dateipfad verwendet:
```python
output_p = _Path(request.output_path)
service = RenderService(output_dir=str(output_p.parent))
```

Ein manipulierter Client könnte Dateien an beliebige Orte schreiben.

**Empfehlung:** Output-Pfad auf Projekt-Verzeichnis einschränken.

### MITTEL — Project Router: mkdir mit beliebigem Pfad

**Befund:** `project_router.py:30-35`:
```python
project_path = Path(request.path) / request.name
project_path.mkdir(parents=True, exist_ok=True)
```

Erstellt Ordner an beliebigen Orten im Dateisystem.

**Empfehlung:** `request.path` gegen `config.project_dir` validieren.

---

## 4. Data Exposure

### NIEDRIG — Exception-Details in HTTP Responses

**Befund:** Mehrere Router geben interne Python-Exceptions an den Client weiter:
```python
raise HTTPException(status_code=500, detail=f"Analyse fehlgeschlagen: {e}")
```

In einer Desktop-App unkritisch, aber bei Netzwerk-Exposition würden Stack-Traces und interne Pfade exponiert.

**Empfehlung:** Für Produktion generische Fehlermeldungen verwenden, Details nur loggen.

### NIEDRIG — Absolute Dateipfade in API Responses

**Befund:** `AudioClipInfo` und `VideoClipInfo` enthalten den vollen Dateipfad (`C:\Users\david\...`). Für lokale Nutzung OK, bei Netzwerk-Exposition ein Info-Leak.

---

## 5. Configuration Security

### MITTEL — CORS allow_origins=["*"]

**Befund:** `backend/main.py:79`:
```python
allow_origins=["*"],  # Lokal — kein Risiko
```

Bei localhost technisch korrekt, aber ein Browser-Tab mit einer bösartigen Website könnte via JavaScript Requests an `localhost:8765` senden (CSRF via CORS). Moderne Browser erlauben dies bei `*`-Origin.

**Empfehlung:** Origins auf `http://localhost:*` oder den spezifischen WPF-Client einschränken:
```python
allow_origins=["http://localhost:8765", "http://127.0.0.1:8765"],
```

### MITTEL — os._exit(0) im Shutdown

**Befund:** `backend/main.py:165` — `os._exit(0)` umgeht alle Cleanup-Handler (atexit, finally, DB-Connections). SQLite WAL-Journal könnte korrupt werden.

**Empfehlung:** Graceful Shutdown via `uvicorn.Server.should_exit = True` oder `signal.raise_signal(SIGTERM)`.

---

## 6. Secrets Management

### INFO — Keine Secrets vorhanden

**Befund:** Die App verwendet keine API-Keys, Tokens oder Passwörter. Alle Konfiguration erfolgt über `pydantic-settings` mit `.env`-Datei Support (aktuell keine `.env` vorhanden). Keine Secrets im Repository gefunden.

**Status:** Kein Handlungsbedarf.

---

## 7. Subprocess Security

### INFO — Kein shell=True gefunden

**Befund:** Alle `subprocess.run/check_output/Popen` Aufrufe verwenden Listen-Syntax (kein `shell=True`). Das ist korrekt und verhindert Shell-Injection. Ein expliziter Kommentar in `video_renderer.py:72` bestätigt diese Policy.

**Alle subprocess-Aufrufe haben Timeouts** — kein Risiko für hängende Prozesse.

---

## 8. SQL-Sicherheit

### INFO — Parametrisierte Queries (korrekt)

**Befund:** Alle SQL-Queries in `project_repository.py` und `media_repository.py` verwenden parametrisierte Queries (`?`-Platzhalter). Die dynamische Query-Konstruktion in `update_project()` (Zeile 97) baut nur Spaltennamen dynamisch — die kommen aus internem Code, nicht von User-Input. `bulk_update_status()` (Zeile 116-118) nutzt `','.join('?' * len(media_ids))` — ebenfalls sicher.

**Status:** Kein SQL-Injection-Risiko.

---

## Priorisierte Empfehlungen

1. **Path-Traversal-Schutz** (HOCH) — Whitelist-Validierung für Import/Export-Pfade einbauen
2. **CORS einschränken** (MITTEL) — `allow_origins` von `*` auf localhost begrenzen
3. **Graceful Shutdown** (MITTEL) — `os._exit()` durch sauberen Shutdown ersetzen
4. **Project-Pfad validieren** (MITTEL) — `project_router.create` gegen `config.project_dir` prüfen
5. **opencv-python aktualisieren** (MITTEL) — Version-Pin lockern
6. **pip-audit einführen** (NIEDRIG) — Automatisches CVE-Scanning

---

*Audit durchgeführt am 2026-03-05. Nächster Review empfohlen vor Netzwerk-Exposition oder Multi-User-Betrieb.*
