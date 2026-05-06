# PLAN: PB Studio (AMD-Version) - Vollständige Fertigstellung

**Ziel:** Vollständige Umsetzung und Validierung aller in `RESEARCH.md` identifizierten Lücken, um das System "Production-Ready" (Release 1.0) zu machen.

**Vorgehen:** Wir werden die Entwicklung in logischen, isolierten Phasen (Sprints) durchführen. Nach jeder Phase erfolgt ein Validierungstest.

---

## Phase 1: Backend-Stabilität & Ressourcen (Prio 1)
Diese Phase ist kritisch, um Abstürze bei großen Projekten und langen Renderings zu vermeiden.

1.  **VRAM Eviction Manager implementieren**
    *   Datei: `src/pb_studio/core/vram_arbiter.py` und/o. `vram_budget_manager.py`
    *   Aufgabe: LRU (Least Recently Used) Eviction-Logik einbauen. Wenn ein neues Modell geladen wird und der VRAM voll ist, werden ungenutzte Modelle entladen.
2.  **Global Error Recovery & Crash Handler implementieren**
    *   Datei: `src/pb_studio/core/recovery_handler.py` (neu)
    *   Aufgabe: Abfangen von Thread-Crashes (Worker) und OOM-Fehlern (Out-of-Memory). Automatisches Aufräumen (GC, Cache-Invalidierung) und Neustart-Logik für gescheiterte Tasks.
3.  **Unit Tests für Ressourcen-Management schreiben**
    *   Datei: `Tests/test_vram_budget_manager.py` (neu)
    *   Aufgabe: Sicherstellen, dass die Eviction-Logik nach Priorität (Low/High) und Speichervolumen korrekt funktioniert.

## Phase 2: Live-Telemetrie & UX-Glue (Prio 2)
Der Render-Vorgang wirkt aktuell wie eine "Blackbox". Wir brauchen aktives Feedback in der Oberfläche.

4.  **Render-Telemetrie (Backend) patchen**
    *   Datei: `src/pb_studio/rendering/render_service.py` / `render_engine.py`
    *   Aufgabe: FFmpeg-Output in Echtzeit auslesen (Regex auf FPS, Time, Speed) und diese Metriken über Server-Sent Events (`/events`) an die UI senden.
5.  **Render-UI (WPF) an Telemetrie anbinden**
    *   Datei: `PBStudio.UI/ViewModels/ProductionViewModel.cs`
    *   Aufgabe: Empfangen der SSE-Telemetrie und Aktualisieren der ETA-, FPS- und Fortschrittsanzeigen in der WPF-View.

## Phase 3: UI-Polish & Native Integration (Prio 3)
6.  **Native WPF Import-Dialoge robuster machen**
    *   Datei: z.B. `PBStudio.UI/ViewModels/MediaLibraryViewModel.cs` oder ähnliche FilePicker-Services.
    *   Aufgabe: Robuste Behandlung von falschen Dateiformaten, Abfangen von Berechtigungsfehlern und natives Windows-Dialog-Feeling sicherstellen.

## Phase 4: Qualitätsprüfung & Stresstest (Prio 4)
7.  **Semantische Qualitätsprüfung (Pacing Logic)**
    *   Aufgabe: Manueller Review eines generierten 3-Stunden-Mock-Schnitts mit echtem Video-Material, um sicherzustellen, dass harte Cuts mit Drops und sanfte Übergänge mit Ambient-Passagen übereinstimmen.
8.  **Multi-Clip & Stress-Test**
    *   Aufgabe: Director-Lauf mit 100+ Clips im Workspace parallel zu einer intensiven Stem-Separation, um OOM-Handler und Crash-Recovery zu validieren.

---

*(Hinweis: Der "Echte interaktive Timeline-Editor" aus RESEARCH.md wird als separates Großprojekt (Feature-Branch) behandelt und erst begonnen, sobald die Backend-Stabilität zu 100% gesichert ist, da dies eine massive UI-Neuentwicklung in WPF bedeutet.)*
