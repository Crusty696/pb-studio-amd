# 🔧 Fix-Vorschläge — PB Studio (kritische Audit-Funde)

**Projekt:** `C:\Users\david\Documents\Pb_studio_AMD_version`
**Datum:** 2026-07-24
**Bezug:** `AUDIT_REPORT_PB_Studio_20260724.md` (Python #1–#7) + `AUDIT_REPORT_PB_Studio_CSharp_20260724.md` (C#-1/2/3)

> **Status: Vorschläge, noch NICHT angewendet.** Die Desktop-Verbindung war beim Erstellen offline, daher konnte ich nicht direkt auf die Platte schreiben. Sobald die Claude-Desktop-App wieder verbunden ist, wende ich die als **✅ sicher** markierten Patches auf Wunsch direkt an.
>
> **Zwei Klassen von Fixes:**
> - **✅ Sicher/mechanisch** (#1, #2, #5, #6, #7, C#-1, C#-2, C#-3): eindeutig, geringes Risiko.
> - **⚠️ Heikel/Concurrency** (#3, #4): korrigieren echte VRAM-Lecks, berühren aber die Sperr-Logik. **Vor dem Vertrauen unbedingt `pytest Tests/ -x -q` auf dem Zielrechner laufen lassen** (DirectML/VRAM-Tests), was ich im Linux-Container nicht kann.
>
> Alle IRON RULES beachtet (kein CUDA/pynvml, DirectML-Flags unangetastet, AMF, pathlib, PYTHONPATH=src, `Tests/` groß).

---

## ✅ FIX #1 — `audio_embedding_worker.py` — `UnboundLocalError` beheben

**Datei:** `src/pb_studio/workers/audio/audio_embedding_worker.py`
**Ursache:** Der lokale Re-Import von `CLAP_SAMPLE_RATE` (Z.121) macht den Namen für die ganze Funktion lokal → Z.84 wirft `UnboundLocalError`.
**Fix:** `CLAP_DURATION` bereits am Modulanfang mitimportieren und den lokalen Re-Import entfernen.

**Zeile 15 — vorher:**
```python
from ...ai.clap_pytorch import CLAPPyTorch, CLAP_SAMPLE_RATE
```
**Zeile 15 — nachher:**
```python
from ...ai.clap_pytorch import CLAPPyTorch, CLAP_SAMPLE_RATE, CLAP_DURATION
```

**Zeile 120-122 — vorher:**
```python
                # BUG-092 FIX: Nutze Konstanten aus clap_pytorch für exaktes Padding/Crop
                from ...ai.clap_pytorch import CLAP_DURATION, CLAP_SAMPLE_RATE
                target_length = int(CLAP_DURATION * CLAP_SAMPLE_RATE)
```
**Zeile 120-122 — nachher:**
```python
                # BUG-092 FIX: Nutze Konstanten aus clap_pytorch für exaktes Padding/Crop
                # (Import steht jetzt auf Modul-Ebene — lokaler Re-Import verursachte UnboundLocalError in Z.84)
                target_length = int(CLAP_DURATION * CLAP_SAMPLE_RATE)
```
*Wirkung:* CLAP-Embedding läuft wieder. Direkt verifizierbar mit `pytest Tests/ -k embedding` oder einem echten Embedding-Lauf.

---

## ✅ FIX #2 — `video_vision_worker.py` — VRAM-Freigabe im `finally` ergänzen

**Datei:** `src/pb_studio/workers/video/video_vision_worker.py`
**Ursache:** `finally` gibt OpenCV-Handle frei und entlädt das Modell, ruft aber nie `arbiter.release()` → 2500 MB bleiben prozessweit belegt.
**Fix:** Im `finally` `arbiter.release()` ergänzen (analog Motion-/Stem-Worker, Z.156 dort).

**Zeile ~155-159 — vorher:**
```python
        finally:
            if cap is not None:
                cap.release()
            self._unload_model()
```
**Zeile ~155-159 — nachher:**
```python
        finally:
            if cap is not None:
                cap.release()
            self._unload_model()
            # FIX: reservierten/committeten VRAM immer freigeben (analog Motion-/Stem-Worker),
            # sonst leckt das globale VRAMBudget 2500 MB pro Vision-Lauf.
            if vram_reserved:
                arbiter.release(model_id=model_id)
```
*Hinweis:* `arbiter` und `model_id`/`vram_reserved` sind bereits im `_execute`-Scope gebunden (Z.82/86). `VRAMArbiter.release` ist idempotent gegenüber reserve+commit desselben `model_id`.

---

## ⚠️ FIX #3 — `vram_budget_manager.update_max_vram` — Leck/Drift bei fehlgeschlagener Verdrängung

**Datei:** `src/pb_studio/core/vram_budget_manager.py:380-418`
**Ursache:** `_evict_for_space` reduziert `_committed_mb` und sammelt Unload-Callbacks; schlägt die Verdrängung nicht ausreichend an, wird `raise ValueError` **vor** der Callback-Schleife ausgelöst → physischer Unload bleibt aus, Buchhaltung ist aber schon reduziert (Leck + Drift).
**Fix (minimal-invasiv):** Callback-Schleife über `try/finally` immer ausführen, damit die physische VRAM-Freigabe mit der bereits gebuchten Reduktion konsistent bleibt.

**Vorher (380-418):**
```python
        callbacks_to_invoke = []
        with self._registry_lock:
            new_usable = limit_mb - self._safety_buffer_mb
            if new_usable < 0:
                raise ValueError("Das VRAM-Limit ist zu niedrig ...")

            if new_usable < self._committed_mb:
                shortfall = self._committed_mb - new_usable
                freed, callbacks_to_invoke = self._evict_for_space(shortfall)

                if new_usable < self._committed_mb:
                    raise ValueError(
                        f"Limit kann nicht auf {limit_mb}MB gesenkt werden. ..."
                    )

            self._max_vram_mb = limit_mb
            self._usable_vram_mb = new_usable
            logger.info(...)

        # Callbacks ausserhalb von self._registry_lock ausfuehren ...
        for name, callback, budget in callbacks_to_invoke:
            try:
                callback()
            except Exception as e:
                logger.error(f"Unload callback failed for {name}: {e}")
                budget.metadata["eviction_error"] = True
```
**Nachher:**
```python
        callbacks_to_invoke = []
        try:
            with self._registry_lock:
                new_usable = limit_mb - self._safety_buffer_mb
                if new_usable < 0:
                    raise ValueError("Das VRAM-Limit ist zu niedrig ...")

                if new_usable < self._committed_mb:
                    shortfall = self._committed_mb - new_usable
                    freed, callbacks_to_invoke = self._evict_for_space(shortfall)

                    if new_usable < self._committed_mb:
                        raise ValueError(
                            f"Limit kann nicht auf {limit_mb}MB gesenkt werden. ..."
                        )

                self._max_vram_mb = limit_mb
                self._usable_vram_mb = new_usable
                logger.info(...)
        finally:
            # FIX: Bereits durch _evict_for_space verbuchte Verdrängungen MÜSSEN physisch
            # entladen werden — auch auf dem raise-Pfad — sonst leckt der VRAM und die
            # Buchhaltung driftet (committed reduziert, Modell aber noch resident).
            for name, callback, budget in callbacks_to_invoke:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Unload callback failed for {name}: {e}")
                    budget.metadata["eviction_error"] = True
```
**Verbleibendes Verhalten (bewusst, dokumentieren):** Wird das Limit abgelehnt, sind trotzdem einige Modelle entladen worden. Das ist konsistent (kein Leck) und besser als der Status quo. Ideale Langfristlösung: Machbarkeit der Verdrängung prüfen, **bevor** `_evict_for_space` mutiert. **Vor Merge VRAM-Tests laufen lassen.**

---

## ⚠️ FIX #4 — `vram_budget_manager.reserve(force=True)` — Überbuchung bei Callback-Fehler

**Datei:** `src/pb_studio/core/vram_budget_manager.py:622-648`
**Ursache:** Wirft der Unload-Callback eines verdrängten Modells, bucht der `except` dessen VRAM als committed zurück — die neue Reservierung (`_reserved_mb += …`) bleibt aber bestehen → Budget autorisiert mehr als vorhanden. Zusätzlich **überschattet** die Schleifenvariable `budget` das anzufordernde Modell-`budget`.
**Fix:** Reservierten Zustand vor der Callback-Schleife merken, bei Callback-Fehler die neue Reservierung zurückrollen und `success=False` setzen.

**Vorher (ab „# Callbacks ausserhalb …"):**
```python
        # Callbacks ausserhalb von self._registry_lock ausfuehren ...
        for name, callback, budget in callbacks_to_invoke:
            try:
                callback()
            except Exception as e:
                logger.error(f"Unload callback failed for {name}: {e}")
                budget.metadata["eviction_error"] = True
                with self._registry_lock:
                    if not budget.is_loaded:
                        budget.is_loaded = True
                        self._committed_mb += budget.estimated_vram_mb

        return success
```
**Nachher:**
```python
        # FIX: Referenz auf das ANZUFORDERNDE Modell festhalten, bevor die Schleifenvariable
        # 'budget' es überschattet.
        requested_budget = self._models.get(model_id)
        eviction_failed = False

        # Callbacks ausserhalb von self._registry_lock ausfuehren ...
        for name, callback, evicted_budget in callbacks_to_invoke:
            try:
                callback()
            except Exception as e:
                logger.error(f"Unload callback failed for {name}: {e}")
                evicted_budget.metadata["eviction_error"] = True
                eviction_failed = True
                with self._registry_lock:
                    if not evicted_budget.is_loaded:
                        evicted_budget.is_loaded = True
                        self._committed_mb += evicted_budget.estimated_vram_mb

        # FIX: Materialisierte sich die Freigabe NICHT, darf die neue Reservierung nicht
        # bestehen bleiben (sonst Überbuchung → DirectML-OOM-Risiko).
        if eviction_failed and success and requested_budget is not None:
            with self._registry_lock:
                if requested_budget.is_reserved:
                    requested_budget.is_reserved = False
                    self._reserved_mb -= requested_budget.estimated_vram_mb
            logger.error(
                f"Reservierung für {getattr(requested_budget, 'name', model_id)} zurückgerollt: "
                f"Verdrängungs-Callback ist fehlgeschlagen."
            )
            success = False

        return success
```
**Caveat:** Berührt die Reserve-Semantik. **Vor Merge unbedingt die VRAM-/Arbiter-Tests laufen lassen** und einen Callback-Fehler simulieren (`force=True` + werfender Unload-Callback).

---

## ✅ FIX #5 — `spectral_analyzer.py` — „air"-Band bei 22050 Hz tot

**Datei:** `src/pb_studio/audio/spectral_analyzer.py`
**Ursache:** Bei `sr=22050` (Nyquist 11025) liefern die Bänder `air` (12–20 kHz) und teils `brilliance` konstant Null.
**Empfohlener Fix (Option A, robust):** Analyse-Sample-Rate anheben, damit die oberen Bänder existieren. `44100 Hz` deckt bis 22050 Hz ab.

**Zeile 46 — vorher:**
```python
    def __init__(self, sr: int = 22050, hop_length: int = 512, n_fft: int = 2048):
```
**Zeile 46 — nachher:**
```python
    def __init__(self, sr: int = 44100, hop_length: int = 512, n_fft: int = 2048):
        # FIX: 22050 Hz (Nyquist 11025) machte die Bänder 'air' (12–20 kHz) und den oberen
        # Teil von 'brilliance' permanent zu Null. 44100 Hz deckt das volle 8-Band-Modell ab.
```
**Option B (falls 22050 Hz aus Performance-Gründen zwingend bleibt):** Die Band-Definitionen dokumentiert an Nyquist kappen bzw. `air` entfernen, damit das Feature-Modell ehrlich 7-bandig ist — und alle Konsumenten von `get_band_means`/`get_band_variances` entsprechend anpassen. **Empfehlung: Option A**, weil sie das beworbene 8-Band-Verhalten herstellt.
*Nebeneffekt von A:* etwas höhere CPU-Last und andere `times`-Auflösung — prüfen, dass Event-Erkennungs-Schwellen (`_detect_events`) weiterhin passen (siehe auch Audit-Fund #15, der `self.sr` vs. tatsächliches `sr` betrifft).

---

## ✅ FIX #6 — `cold_start.py` — Gewichte außerhalb [0,1] normalisieren

**Datei:** `src/pb_studio/brain/cold_start.py:18-19`
**Ursache:** `min_clip_length=1.0`, `max_clip_length=8.0` werden als Posterior-**Gewichte** (`bridge_value * weight`) genutzt; `8.0` dominiert jeden Score.
**Empfohlener Fix (Option A, minimal):** Die beiden Clip-Längen-Achsen auf einen neutralen, in-Range-Wert setzen (wie die Video-Achsen `0.5`), damit sie das Ranking nicht dominieren.

**Zeile 18-19 — vorher:**
```python
    "min_clip_length": 1.0,
    "max_clip_length": 8.0,
```
**Zeile 18-19 — nachher:**
```python
    # FIX: Diese Achsen fließen als Gewicht (bridge_value * weight) in den Score ein.
    # Roh-Sekunden (bis 8.0) sprengten [0,1] und dominierten das Cold-Start-Ranking.
    # Neutraler In-Range-Wert wie die Video-Achsen.
    "min_clip_length": 0.5,
    "max_clip_length": 0.5,
```
**Option B (gründlicher, empfohlen zusätzlich):** In `scorer.py` (Schleife ~Z.32-37) und `post_processor.py` (~Z.215-218) das Achsen-Produkt hart auf `[0,1]` klammern:
```python
    sub_scores[axis] = max(0.0, min(1.0, bridge_value * weight))
```
Das schützt generell vor jedem künftigen Out-of-Range-Gewicht. **Empfehlung: A jetzt, B als Härtung.**

---

## ✅ FIX #7 — `base_worker.run()` gibt Ergebnis zurück (Orchestrator-Pipelines)

**Datei:** `src/pb_studio/workers/base_worker.py:131-153`
**Ursache:** `run()` ist `-> None`; `orchestrator.py:238` macht `return worker.run()` → `None` → Folgezugriffe crashen. (Pfad aktuell verwaist, aber der Code ist defekt.)
**Fix (minimal, QThreadPool-kompatibel):** `run()` gibt das Ergebnis zusätzlich zurück; `QThreadPool` ignoriert den Rückgabewert, der synchrone Orchestrator nutzt ihn.

**Vorher (131-153):**
```python
    def run(self) -> None:
        """Main entry point called by QThreadPool. Do not override ... implement _execute()."""
        try:
            self.emit_status(f"{self.worker_name}: Starting")
            result = self._execute()

            if not self._is_cancelled:
                self.emit_result(result)
                self.emit_status(f"{self.worker_name}: Completed")

        except CancelledError:
            self.emit_status(f"{self.worker_name}: Cancelled")

        except Exception as e:
            self.emit_error(e)
            self.emit_status(f"{self.worker_name}: Failed - {str(e)}")

        finally:
            self.signals.finished.emit()
```
**Nachher:**
```python
    def run(self):
        """Main entry point called by QThreadPool. Do not override ... implement _execute().

        Gibt das Ergebnis von _execute() zurück, damit der synchrone WorkerOrchestrator
        es verwenden kann. QThreadPool ignoriert den Rückgabewert von run() — kompatibel.
        """
        result = None
        try:
            self.emit_status(f"{self.worker_name}: Starting")
            result = self._execute()

            if not self._is_cancelled:
                self.emit_result(result)
                self.emit_status(f"{self.worker_name}: Completed")

        except CancelledError:
            self.emit_status(f"{self.worker_name}: Cancelled")
            result = None

        except Exception as e:
            self.emit_error(e)
            self.emit_status(f"{self.worker_name}: Failed - {str(e)}")
            raise   # FIX: Fehler an den synchronen Orchestrator weiterreichen statt None zurückzugeben

        finally:
            self.signals.finished.emit()

        return result
```
**Hinweis:** Das `raise` im Exception-Zweig sorgt dafür, dass `_run_worker_sync` einen echten Fehler sieht (statt still `None`). Falls der signalbasierte QThreadPool-Pfad ein `raise` nicht verträgt, alternativ ohne `raise` lassen und im Orchestrator auf `None` prüfen. **Da der Orchestrator aktuell keinen Aufrufer hat, ist dieser Fix niedrig-dringlich** — anwenden, wenn die Orchestrator-Pipelines reaktiviert werden.

---

## ✅ FIX C#-1 — `BrainViewModel` — Cross-Thread-Zugriff auf UI-Collections

**Datei:** `PBStudio.UI/ViewModels/BrainViewModel.cs:51-52`
**Ursache:** `ProjectOpenedMessage`/`ProjectClosedMessage` können vom Hintergrund-Thread kommen; die Handler mutieren gebundene `ObservableCollection`s ohne Dispatcher → `NotSupportedException`.
**Fix:** Handler auf den UI-Thread marshallen.

**Zeile 51-52 — vorher:**
```csharp
        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) => _ = RefreshStatsAsync());
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) => ResetForProjectClose());
```
**Zeile 51-52 — nachher:**
```csharp
        // FIX: Messages können vom Background-Thread gesendet werden (ProjectService).
        // RefreshStatsAsync/ResetForProjectClose mutieren an die UI gebundene ObservableCollections
        // → auf den Dispatcher marshallen, sonst NotSupportedException.
        WeakReferenceMessenger.Default.Register<ProjectOpenedMessage>(this, (_, _) =>
            System.Windows.Application.Current.Dispatcher.Invoke(() => _ = RefreshStatsAsync()));
        WeakReferenceMessenger.Default.Register<ProjectClosedMessage>(this, (_, _) =>
            System.Windows.Application.Current.Dispatcher.Invoke(ResetForProjectClose));
```
*Wirkung:* `RefreshStatsAsync` startet auf dem UI-Thread; nach jedem `await` kehrt der WPF-`SynchronizationContext` auf den UI-Thread zurück, sodass `TopPositive.Clear()/Add()` sicher sind. `ResetForProjectClose` (synchron) läuft vollständig im Dispatcher.

---

## ✅ FIX C#-2 — `FileLoggerProvider` — Startup-Crash absichern

**Datei:** `PBStudio.UI/Services/FileLoggerProvider.cs:14-17`
**Ursache:** Ungeschütztes `File.WriteAllText` im Ctor (läuft in `OnStartup`); gesperrte/nicht schreibbare Datei → App stirbt vor jedem Fenster.
**Fix:** In try/catch kapseln — ein Logger darf den Start nie kippen.

**Zeile 12-17 — vorher:**
```csharp
    public FileLoggerProvider(string filePath)
    {
        _filePath = filePath;
        // Log-Datei bei jedem Start leeren
        File.WriteAllText(_filePath, $"=== PB Studio WPF Log — {DateTime.Now:yyyy-MM-dd HH:mm:ss} ==={Environment.NewLine}");
    }
```
**Zeile 12-17 — nachher:**
```csharp
    public FileLoggerProvider(string filePath)
    {
        _filePath = filePath;
        // FIX: Best-Effort — ein gesperrtes/nicht schreibbares Log darf den Start (OnStartup)
        // nicht abreißen. Fehler schlucken; FileLogger.Log fängt Schreibfehler ohnehin ab.
        try
        {
            File.WriteAllText(_filePath, $"=== PB Studio WPF Log — {DateTime.Now:yyyy-MM-dd HH:mm:ss} ==={Environment.NewLine}");
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"FileLoggerProvider: Log-Init fehlgeschlagen: {ex.Message}");
        }
    }
```

---

## ✅ FIX C#-3 — `MainWindow` — synchrones Datei-I/O bei jedem Klick entfernen

**Datei:** `PBStudio.UI/MainWindow.xaml.cs:33-114`
**Ursache:** `OnPreviewMouseLeftButtonDown` schreibt bei **jedem** Klick synchron auf dem UI-Thread in die nie rotierte `click_manual_wpf.log`.
**Fix (empfohlen):** Den separaten manuellen Datei-Append entfernen — der `_logger.LogInformation(logLine)` protokolliert denselben Klick bereits in `wpf_app.log` (über den `FileLogger` mit Lock). Damit entfällt UI-Thread-I/O **und** das unbegrenzte Log-Wachstum.

**Zeile ~95-105 — vorher:**
```csharp
            // Log in standard wpf_app.log via _logger
            var logLine = $"[CLICK] X:{(int)pos.X}, Y:{(int)pos.Y} | Element: '{elementName}' | Type: {elementType} | AutoId: '{autoId}'";
            _logger.LogInformation(logLine);

            // Log in separate click_manual_wpf.log (korrekter 4-Ebenen-Pfad)
            var logPath = System.IO.Path.Combine(System.AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", "logs", "click_manual_wpf.log");
            var resolvedPath = System.IO.Path.GetFullPath(logPath);

            var dir = System.IO.Path.GetDirectoryName(resolvedPath);
            if (dir != null && !System.IO.Directory.Exists(dir))
            {
                System.IO.Directory.CreateDirectory(dir);
            }

            var timestamp = System.DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
            var fileLogLine = $"[{timestamp}] {logLine}";

            System.IO.File.AppendAllText(resolvedPath, fileLogLine + System.Environment.NewLine, System.Text.Encoding.UTF8);
```
**Zeile ~95-105 — nachher:**
```csharp
            // Log in standard wpf_app.log via _logger (bereits mit Lock, kein UI-Thread-Blocking-Risiko
            // wie der frühere synchrone AppendAllText pro Klick).
            var logLine = $"[CLICK] X:{(int)pos.X}, Y:{(int)pos.Y} | Element: '{elementName}' | Type: {elementType} | AutoId: '{autoId}'";
            _logger.LogInformation(logLine);

            // FIX: Separater synchroner Append in 'click_manual_wpf.log' entfernt —
            // blockierte den UI-Thread bei jedem Klick und wuchs unbegrenzt (nie rotiert).
            // Der Klick wird bereits oben via _logger protokolliert.
```
*Falls das separate Klick-Log gewünscht bleibt:* stattdessen über einen dedizierten `ILogger`-Kanal / eine gepufferte, hintergrund-geflushte Queue schreiben und mit Größenrotation versehen — nicht synchron auf dem UI-Thread.

---

## Reihenfolge / Empfehlung

1. **Sofort (sicher, hoher Nutzen):** FIX #1 (Crash), FIX #2 (VRAM-Leck), C#-2 (Startup-Crash), C#-1 (UI-Crash), C#-3 (UI-Stutter).
2. **Bald (sicher):** FIX #5 (Spektral-Feature), FIX #6 (Brain-Ranking).
3. **Nach VRAM-Testlauf (heikel):** FIX #3, FIX #4 — erst `pytest Tests/ -x -q` grün, dann mergen.
4. **Wenn Orchestrator reaktiviert wird:** FIX #7.

**Verifikation nach dem Anwenden:**
```powershell
.venv\Scripts\activate
$env:PYTHONPATH = "src"
pytest Tests/ -x -q          # bestätigt v.a. FIX #1 sofort
dotnet build PBStudio.UI\PBStudio.UI.csproj   # C#-Fixes kompilieren
```

*Erstellt aus den auditierten Quellständen. Noch nicht angewendet — auf Freigabe/Reconnect wartend.*
