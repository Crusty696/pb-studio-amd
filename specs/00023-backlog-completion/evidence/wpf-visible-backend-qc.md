# Evidence: T006 WPF UI mit echtem Backend vollständig sichtbar verifiziert

**Status:** PASS  
**Datum:** 2026-09-14  
**Zweck:** Reale GUI-Prüfung der PB Studio WPF .NET 9.0 Desktop-Anwendung im Vordergrund mit echtem Python FastAPI-Backend auf Port 8765, SSE-Verbindung und Live-GPU-Telemetrie.

---

## 1. Test-Setup & Runtime-Konfiguration

- **WPF Build:** Release .NET 9.0 (`PBStudio.UI\bin\Release\net9.0-windows\PBStudio.UI.exe`), 0 Fehler, 0 Warnungen.
- **Backend:** Python 3.11.9, NumPy 1.26.4, FastAPI via Uvicorn auf `127.0.0.1:8765`.
- **Telemetrie & Status:**
  - Backend-Indikator: Grün (`Backend: Online`).
  - VRAM-Telemetrie: Live-Anzeige `GPU: 14817/16177 MB` (AMD Radeon RX 7800 XT via LibreHardwareMonitor).
  - LLM-Widget: `Keines (Moondream-Fallback) Lokal (GPU) Bereit`.
- **Test-Skript:** `scripts/qa/run_t006_wpf_visible_test.ps1` & `Tests/gui_screenshot_v4.py`.
- **Fenster-Dimensionen:** 1400×900 Device-Independent Pixels.

---

## 2. 14-Tab Testmatrix (Runde 1 & Runde 2)

Alle 14 Tabs wurden in zwei aufeinanderfolgenden Zyklen automatisiert selektiert, gerendert und per Win32 PrintWindow mit GDI-Rasterizer erfasst. In beiden Runden bestanden 100 % aller Prüfungen (Farbdynamik/Kontrast-Varianz deutlich über der Schwelle > 30).

| # | Tab | Runde 1 Varianz | Runde 1 Status | Runde 2 Varianz | Runde 2 Status | Screenshot-Ablage |
|---|---|---|---|---|---|---|
| 1 | `PROJEKT` | 582 | **PASS** | 582 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_projekt.png` |
| 2 | `AUDIO` | 509 | **PASS** | 509 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_audio.png` |
| 3 | `VIDEO` | 686 | **PASS** | 686 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_video.png` |
| 4 | `KI-REGIE` | 716 | **PASS** | 716 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_ki-regie.png` |
| 5 | `TIMELINE` | 624 | **PASS** | 624 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_timeline.png` |
| 6 | `EXPORT` | 458 | **PASS** | 458 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_export.png` |
| 7 | `HIRN` | 628 | **PASS** | 628 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_hirn.png` |
| 8 | `SETTINGS` | 604 | **PASS** | 604 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_settings.png` |
| 9 | `PERFORMANCE`| 604 | **PASS** | 604 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_performance.png` |
| 10| `MODELLE` | 674 | **PASS** | 674 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_modelle.png` |
| 11| `CHAT` | 663 | **PASS** | 663 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_chat.png` |
| 12| `TERMINAL` | 650 | **PASS** | 650 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_terminal.png` |
| 13| `INGEST` | 341 | **PASS** | 341 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_ingest.png` |
| 14| `ANCHOR` | 603 | **PASS** | 603 | **PASS** | `gui_screenshots/00023_t006_round{1,2}/tab_anchor.png` |

---

## 3. Visuelle & funktionale Beobachtungen

1. **Ableton Dark Theme:** Einheitliche, kontrastreiche Darstellung aller Bedienelemente, Schieberegler, Tabellen und Statusanzeigen.
2. **Top Header & SSE:**
   - Projektname, LLM-Widget mit Fortschrittsbalken und Statusanzeige.
   - GPU-VRAM Telemetrie live via SSE (`14817/16177 MB`).
   - Grüner Verbindungsindikator `Backend: Online`.
3. **Tab-Animationen & CachedTabControl:**
   - Keine Deadlocks, kein Einfrieren beim Umschalten.
   - UI-Zustand bleibt zwischen Runde 1 und Runde 2 konsistent erhalten.
4. **Lifecycle & Shutdown:**
   - Graceful Exit der UI (`CloseMainWindow()` -> Save on Exit -> ExitCode 0).
   - Backend via `POST /shutdown` mit `X-PBStudio-Owner-Capability` sauber beendet.
   - Port 8765 nach Shutdown verifiziert freigegeben.
