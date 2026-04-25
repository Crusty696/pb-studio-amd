# RESEARCH: PB Studio (AMD-Version) - Offene Bugs & Aufgaben zur Fertigstellung

**Datum:** 16. April 2026
**Fokus:** Lückenlose Erfassung aller noch offenen Aufgaben, Architekturlücken und ausstehenden Validierungen, um PB Studio den "Production-Ready" (MVP) Status zu verleihen.

---

## 1. Ausgangslage & Kürzliche Audits
Gemäß dem `WORKLOG.md` (Stand 29.03.2026) wurden im "Grand Audit" bereits 52 identifizierte Bugs (inklusive Thread-Safety-Probleme, ML-Ladefehler und Pfad-Escaping) vollständig behoben. Das System durchläuft bereits erfolgreich E2E-Runtime-Tests (Import -> Analyse -> Pacing -> Render).

Dennoch weisen die `STATUS_MATRIX.md` und `FEHLENDE_KOMPONENTEN.md` auf mehrere kritische Lücken hin, die für einen produktiven Einsatz (Release-Readiness) geschlossen werden müssen.

---

## 2. Offene Architektur- & Stabilitäts-Lücken

### 2.1 VRAM Eviction & Ressourcen-Management (Stabilität)
*   **Problem:** Der aktuelle `VRAMArbiter` blockiert neue Modell-Ladevorgänge (Out-of-Memory-Prävention), wirft aber inaktive Modelle nicht automatisch aus dem Speicher (Eviction).
*   **Lösung:** Implementierung einer LRU (Least Recently Used) oder prioritätsbasierten Eviction-Strategie in `vram_arbiter.py`, sodass bei Speicherengpässen automatisch Platz gemacht wird (z. B. Moondream entladen, um FFmpeg-AMF Platz zu machen).

### 2.2 Error Recovery & Crash Handling
*   **Problem:** Das System fängt Backend-Crashes (z. B. Worker-Threads) derzeit nur rudimentär ab und loggt diese. Es gibt keine automatische Wiederherstellung (Graceful Restart) oder OOM-Recovery.
*   **Lösung:** Einbau eines `RecoveryHandler`, der abgestürzte Worker neu startet, den VRAM bereinigt (Garbage Collection) und die WPF-UI sauber über den Status informiert.

### 2.3 Render-Telemetrie (UX / Progress)
*   **Problem:** Während des Render-Vorgangs werden ETA (verbleibende Zeit), aktuelle Frame-Nummer und FPS weder im Backend noch in der WPF-UI live aktualisiert (bleiben auf 0 bis zum Abschluss).
*   **Lösung:** Backend SSE-Stream (Server-Sent Events) für den Render-Progress patchen, sodass FFmpeg/Render-Engine Metriken korrekt geparst und an die UI durchgereicht werden.

---

## 3. Offene UI/UX-Komponenten (WPF)

### 3.1 Echter interaktiver Timeline-Editor / Player
*   **Problem:** Die aktuelle Timeline in WPF ist primär eine Listenansicht. Ein echter Player mit Scrubbing, Schnitt-Feinjustierung und visueller Vorschau fehlt.
*   **Lösungsansatz:** Entscheidung treffen, ob dies Teil des MVP (Release 1.0) ist oder auf 1.1 verschoben wird. Falls MVP, muss ein Custom WPF-Control für die Zeitleiste und Video-Vorschau gebaut werden.

### 3.2 Native Import-Dialoge & Edge Cases
*   **Problem:** Der Video-Import funktioniert funktional über die API, aber die nativen Datei-/Ordner-Auswahldialoge in WPF (inkl. Edge Cases bei falschen Dateiformaten) müssen robuster werden.

---

## 4. Ausstehende Deep-Tests & QA

### 4.1 Semantische Qualitätsprüfung (KI-Logik)
*   **Aufgabe:** Die generierten Schnitte (Pacing) funktionieren technisch, jedoch wurde die visuelle *Bedeutung* (Matching von Drop-Energie mit stark bewegten Videos) noch nicht mit echten, semantisch reichen Video-Clips bewertet.
*   **Maßnahme:** Manueller Output-Review mit einem echten DJ-Mix und einer echten Stock-Footage-Bibliothek.

### 4.2 Multi-Clip Selection & Stress-Test
*   **Aufgabe:** Testen des Director-Moduls mit einer großen Anzahl (100+) unterschiedlicher Clips und gleichzeitiger Ausführung von Stem-Separation und Rendering.

### 4.3 Unit Test Coverage
*   **Aufgabe:** Hinzufügen spezifischer Unit-Tests für den VRAM-Manager (`test_vram_budget_manager.py`) und Caching-Mechanismen, um Regressionen in der Zukunft zu vermeiden.

---

## 5. Fazit & Nächste Schritte

Das System ist zu ca. 90% funktional (Backend, API, WPF-Grundgerüst, KI-Integration stehen). Die Priorität für die absolute Fertigstellung liegt nun auf:
1.  **VRAM-Eviction & Recovery** (für die Stabilität langer Mixes).
2.  **Live Render-Telemetrie** (für das User-Feedback).
3.  **Qualitätssicherung** (Stresstests mit echtem Material).

Sobald diese Punkte abgearbeitet sind, ist die App voll funktional und bereit für den produktiven Einsatz.