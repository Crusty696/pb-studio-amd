# PB Studio AMD – Konsolidierter Fullstack-Audit-Bericht (2026-05-21)

**Fokus:** Lückenloses System-Audit über alle 5 Code-Zonen (Z-AUDIO, Z-VIDEO, Z-RENDER, Z-CORE, Z-DATA, Shared-Zones & Z-INFRA).  
**Methodik:** Dezentralisiertes Audit-Team (Director, Video, Audio, VRAM, DB) mit Zero-Assumption-Dokumentation.

---

## 1. Kritische Befunde & Fehler (Bugs)

| ID | Zone | Datei + Zeile | Beschreibung | Empfohlene Behebung |
| :--- | :--- | :--- | :--- | :--- |
| **B-1** | `Z-INFRA` | [start.bat:L70-L83](file:///C:/Users/david/Documents/Pb_studio_AMD_version/start.bat#L70-L83)<br>[start.bat:L97-L108](file:///C:/Users/david/Documents/Pb_studio_AMD_version/start.bat#L97-L108) | **Verschluckter Exit-Code in Pipes:**<br>Durch die Piping-Ausführung von `build.ps1` und `launch.ps1` in PowerShell (`*>&1 | ForEach-Object { ... }`) wird der echte Exit-Code der Skripte verschluckt. `powershell.exe` gibt bei Pipeline-Durchlauf immer `0` an Cmd zurück, wodurch Error-Checks fehlschlagen. | Ergänzen Sie das PowerShell-Kommando am Ende mit `; exit $LASTEXITCODE`. |
| **B-2** | `Z-INFRA` | [build.ps1:L18](file:///C:/Users/david/Documents/Pb_studio_AMD_version/build.ps1#L18) | **Hartcodierter Python-Pfad:**<br>`build.ps1` verwendet einen fest verdrahteten absoluten Benutzerpfad (`C:\Users\david\AppData\Local...`), um Abhängigkeiten global zu installieren, was die virtuelle Umgebung (`.venv`) umgeht. | Ersetzen Sie den Pfad dynamisch: Prüfen Sie vorrangig auf `.venv\Scripts\python.exe`. |
| **B-3** | `Z-CORE` | [vram_budget_manager.py:L721](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/core/vram_budget_manager.py#L721)<br>[model_loader.py:L344](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/core/model_loader.py#L344) | **Zirkulärer Lock-Deadlock:**<br>`VRAMBudgetManager` ruft synchron den Evict-Callback auf, während er den `_registry_lock` hält. Dieser versucht, den `ModelLoader._session_lock` zu sperren, während zeitgleich ein anderer Thread Locks in entgegengesetzter Reihenfolge holen möchte. | Externe Callbacks (`unload_callback()`) dürfen *niemals* innerhalb des aktiven Locks des Budget Managers ausgeführt werden. Lock vor Callback-Aufruf freigeben. |
| **B-4** | `Z-CORE` | [vram_arbiter.py:L48](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/core/vram_arbiter.py#L48) | **Test-Sabotage (Limit unwirksam):**<br>Zuweisung an nicht existierendes Attribut `vram_total_mb` setzt das erzwungene 4GB-VRAM-Limit im BudgetManager komplett außer Kraft. Stresstests laufen mit physischem Riesenbudget weiter. | Überschreibe direkt die internen Attribute des `VRAMBudgetManager`-Singletons: `self.budget_manager._max_vram_mb = self.forced_limit` und passe `_usable_vram_mb` an. |
| **B-5** | `Z-CORE` | [dependencies.py:L121](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/dependencies.py#L121) | **Versteckte VRAM-Accounting-Lücke:**<br>`with_gpu_task` ruft vorzeitig `release` auf, während Modelle im `ModelLoader` real geladen bleiben. Dies führt zu einer gigantischen Lücke im Accounting und provoziert OOM-Crashes. | Koppel die Freigabe des Budgets ausschließlich an das tatsächliche Entladen der Inferenz-Sitzung innerhalb des `ModelLoader`s. |
| **B-6** | `Z-DATA` | [weight_store.py:L96-L133](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/brain/weight_store.py#L96-L133) | **Stale Cache Race Condition:**<br>Wenn ein Thread bei einem Cache-Miss Werte ohne Lock aus der DB liest, während ein paralleler Thread ein Update (Cache-Invalidierung) ausführt, schreibt der erste Thread danach veraltete Werte in den Cache. | Nutze eine Cache-Version `self._version` als Token beim Schreiben. |
| **B-7** | `Z-DATA` | [vector_store.py:L59](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/data/vector_store.py#L59) | **Fehlende Persistenz von Tombstones:**<br>Das Tombstone-Set `self._tombstoned_ids` existiert nur im RAM und wird nicht persistiert. Nach einem Neustart tauchen gelöschte FAISS-Segmente wieder auf. | Speichere `_tombstoned_ids` in `_meta.json` ab und lade sie beim Start wieder. |
| **B-8** | `Z-DATA` | [001_initial.sql:L4 (embedding_cache)](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/migrations/embedding_cache/001_initial.sql#L4) | **Überschreibender Primary Key im Cache:**<br>`media_hash` ist der alleinige `PRIMARY KEY`. Verschiedene Modelle überschreiben sich gegenseitig im Cache, was zu permanenten Cache-Misses führt. | Ändere den `PRIMARY KEY` der Tabelle in `(media_hash, model_name, model_version)`. |
| **B-9** | `Z-DATA` | [migration_runner.py:L35](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/migration_runner.py#L35) | **Gebrochene Transaktionssicherheit bei Script-Migrationen:**<br>Die Verwendung von `conn.executescript(sql)` innerhalb einer Transaktion führt in `sqlite3` zu einem impliziten Commit, wodurch Atomarität und Rollbacks blockiert werden. | Ersetze durch Statements-Schleife mit `sqlite3.complete_statement()`. |
| **B-10** | `Z-DATA` | [embedding_repository.py:L132](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/embedding_repository.py#L132) | **Nicht-atomare Doppel-Inserts:**<br>Weil Autocommit aktiv ist (`isolation_level=None`), werden separate Inserts in `units` und `embeddings` ohne Transaktion ausgeführt. | Umschließe Inserts mit einem expliziten Transaktions-Kontextmanager. |
| **B-11** | `Z-CORE` | [siglip_wrapper.py:L87](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/ai/siglip_wrapper.py#L87)<br>[clap_pytorch.py:L88-89](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/ai/clap_pytorch.py#L88-L89) | **Offline-Verstoß (Stiller Download):**<br>Text-Fallbacks und CLAP laden Gewichte im Fallback-Modus blind über HuggingFace Hub, was in einer Offline-Umgebung blockiert oder abstürzt. | Erzwinge das Laden aus dem lokalen Modellverzeichnis durch `local_files_only=True` und deaktiviere Remote-Downloads. |
| **B-12** | `Z-CORE` | [smart_director.py:L320-334](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/ai/smart_director.py#L320-334) | **Thread-Sicherheits-Bug bei Eviction:**<br>Eviction-Callbacks aus dem BudgetManager nullen Inferenz-Wrapper mitten in einer Operation ohne Thread-Synchronisation. | Sichere alle Zugriffe und Inferenzoperationen im SmartDirector über einen dedizierten Lock ab. |

---

## 2. Architektonische Risiken (Risks)

| ID | Zone | Datei + Zeile | Beschreibung | Empfohlene Behebung |
| :--- | :--- | :--- | :--- | :--- |
| **R-1** | `Z-CORE` | [app_state.py:L914](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/app_state.py#L914) | **Event Loop Block via Synchronous I/O in load_from_db:**<br>Synchroner Aufruf von `p.exists()` für Tausende von Clips blockiert den FastAPI-Event-Loop und verzögert alle Endpoints massiv. | Asynchron über `asyncio.to_thread` ausführen oder Prüfung in den On-Demand-Endpoint verlagern. |
| **R-2** | `Z-CORE` | [app_state.py:L891](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/app_state.py#L891) | **Concurrency & Unlocked State Erasure:**<br>In `load_from_db` wird der Zustand sofort gelöscht (`self.audio_clips.clear()`), während die DB-Prüfungen außerhalb des Locks laufen. Andere Threads sehen temporär ein leeres Projekt. | Bereiten Sie die temporären Dictionaries außerhalb des Locks vor, und führen Sie Löschen und Zuweisen atomar unter Lock durch. |
| **R-3** | `Z-RENDER` | [render_service.py:L301](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/rendering/render_service.py#L301) | **Codec-Mismatch-Fallback:**<br>Schlägt der primäre Hardware-HEVC-Encoder fehl, wird auf H.264 (`h264_mf`) zurückgefallen, was beim finalen Demux-Concat zum FFmpeg-Absturz führt. | Passen Sie die Fallback-Kette dynamisch an den gewünschten Ziel-Codec an (HEVC -> CPU HEVC). |
| **R-4** | `Z-RENDER` | [render_service.py:L510](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/rendering/render_service.py#L510) | **CPU-Overhead durch zeichenweises Lesen:**<br>`enqueue_stderr` liest den stderr-Stream von FFmpeg Zeichen für Zeichen (`pipe.read(1)`) aus. Extrem ineffizient bei langen Render-Vorgängen. | Implementieren Sie blockweises Lesen und suchen nach Carriage Returns. |
| **R-5** | `Z-VIDEO` | [video_router.py:L894](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/routers/video_router.py#L894) | **VRAM Release Gap:**<br>Nach dem Löschen des SigLIP-Wrappers wird kein expliziter `gc.collect()` durchgeführt, was verzögerte VRAM-Freigaben zur Folge haben kann. | Hinzufügen von `gc.collect()` im `finally`-Block der Embedding-Generierung. |
| **R-6** | `Z-DATA` | [embedding_cache.py:L96](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/embedding_cache.py#L96) | **Orphan-NPY-Dateien auf Platte:**<br>Die `.npy`-Datei wird geschrieben, *bevor* die DB aktualisiert wird. Schlägt der DB-Eintrag fehlerhaft fehl, bleibt die Datei als unregistrierte Datenleiche zurück. | Fange DB-Fehler ab und lösche die angelegte `.npy`-Datei im Fehlerfall. |
| **R-7** | `Z-CORE` | [system_monitor.py:L188-216](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/core/system_monitor.py#L188-216) | **GUI-Freeze & CPU-Choking:**<br>Ungedrosselter synchroner Start von bis zu 4 PowerShell-Prozessen bei blockierten AMD-Sensoren blockiert den Hauptthread für Sekunden. | PowerShell-Fallbacks asynchron im Hintergrund ausführen und Caching-Intervall von z.B. 10s implementieren. |

---

## 3. Ungenutzter verwaister Code (Dead-Code)

| ID | Zone | Datei + Zeile | Beschreibung | Empfohlene Behebung |
| :--- | :--- | :--- | :--- | :--- |
| **D-1** | `Z-VIDEO` | [video_renderer.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/video/video_renderer.py) | **Verwaiste Klasse:** Die gesamte Datei und Klasse `VideoRenderer` sind komplett ungenutzt und in `__init__.py` genullt. | Datei löschen, Imports entfernen. |
| **D-2** | `Z-RENDER` | [preview_renderer.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/rendering/preview_renderer.py) | **Verwaiste Klasse:** `PreviewGenerator` ist ungenutzt, da `RenderService` alle Previews rendert. | Datei löschen. |
| **D-3** | `Z-RENDER` | [final_renderer.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/rendering/final_renderer.py) | **Verwaiste Klasse:** `BatchRenderer` (Chunking für Windows-Limit) ist obsolet. | Datei löschen. |
| **D-4** | `Z-RENDER` | [render_engine.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/rendering/render_engine.py) | **Verwaiste Klasse:** `RenderEngine` ist komplett unbenutzt. | Datei löschen. |
| **D-5** | `Z-RENDER` | [proxy_service.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/rendering/proxy_service.py) | **Verwaiste Klasse:** `ProxyService` ist obsolet, da PB Studio mit Originalmedien arbeitet. | Datei löschen. |
| **D-6** | `Z-AUDIO` | [anchor_features.py](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/audio/anchor_features.py) | **Verwaiste Klasse:** `AnchorFeatureExtractor` (20-dim Features) wurde vollständig durch das moderne CLAP & SigLIP-2 Brain-Modul ersetzt. | Datei löschen. |
| **D-7** | `Z-CORE` | [main.py:L230](file:///C:/Users/david/Documents/Pb_studio_AMD_version/backend/main.py#L230) | **Redundante Endpunkt-Registrierung:** Endpunkte `/gpu/status` und `/gpu/cleanup` sind inline definiert, obwohl `health_router` existiert. | In `backend/routers/health_router.py` auslagern. |

---

## 4. Integrationslücken (Gaps)

| ID | Zone | Datei + Zeile | Beschreibung | Empfohlene Behebung |
| :--- | :--- | :--- | :--- | :--- |
| **G-1** | `Z-INFRA` | [setup_pb_studio.ps1:L501](file:///C:/Users/david/Documents/Pb_studio_AMD_version/setup_pb_studio.ps1#L501) | **Fehlendes pre-commit Error-Handling:** Ignoriert `$LASTEXITCODE` bei Installation des Schema-Drift-Hooks. Meldet immer Erfolg. | Füge Prüfung von `$LASTEXITCODE` ein und gib bei Fehlern eine Warnung aus. |
| **G-2** | `Z-DATA` | [project_repository.py:L77](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/data/repositories/project_repository.py#L77) | **Fehlendes Lock-Contention-Handling:** Repository-Schreibzugriffe besitzen im Gegensatz zu `MediaRepository` keinen Retry-Mechanismus unter hoher I/O-Last. | Implementiere `@_retry_on_database_lock` Dekorator. |
| **G-3** | `Z-DATA` | [embedding_repository.py:L282](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/storage/embedding_repository.py#L282) | **Fehlende Vektor-Normalisierung:** Embeddings werden vor Speichern/KNN-Suche nicht L2-normalisiert, was bei SQLite-Vec L2-Distanz zu verzerrter Suche führt. | L2-normalisiere alle Vektoren in `_coerce_embedding`. |
| **G-4** | `Z-DATA` | [media_repository.py:L245](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/data/repositories/media_repository.py#L245) | **Fehlende on-the-fly Migration:** Die Migrationsfunktionen für JSON-Blobs werden im Repository nicht direkt beim Laden aufgerufen, wodurch Legacy-Blobs an Aufrufer rausgehen. | Rufe Migrationsfunktionen direkt in `_row_to_dict` von `MediaRepository` auf. |
| **G-5** | `Z-CORE` | [siglip_wrapper.py:L106](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/ai/siglip_wrapper.py#L106)<br>[clap_wrapper.py:L112](file:///C:/Users/david/Documents/Pb_studio_AMD_version/src/pb_studio/ai/clap_wrapper.py#L112) | **Bypass des ModelLoaders:** AI-Wrapper instanziieren `InferenceSession`s direkt anstatt den standardisierten `ModelLoader` zu nutzen. Keine zentrale VRAM-Kontrolle möglich. | Refactorisiere die Wrapper, um ihre ONNX-Inferenzsitzungen über den `ModelLoader` zu beziehen. |

---

## Fazit & Roadmap zur Behebung

Das Audit beweist, dass das System durch die vorherigen Phasen bereits eine exzellente DirectML- und VRAM-Stabilität besitzt. Die verbleibenden Fehler betreffen primär:
1. **Concurrency & VRAM Deadlocks (Z-CORE)**: Der zirkuläre Lock-Deadlock im ModelLoader/BudgetManager und das Versagen des erzwungenen 4GB-VRAM-Limits bei Stresstests.
2. **Datenkonsistenz im Cache und bei der Persistenz (Z-DATA)**: Fehlerhafte Primary Keys im Cache und fehlendes Transaktionshandling bei SQLite-Vec Doppelinserts.
3. **Plattformintegrität & Windows Terminal Pipes (Z-INFRA)**: Fehlerhaftes Pipen in Batches führt zum Ignorieren von Compilerfehlern.
4. **Dead-Code-Ballast**: 6 vollständige Python-Dateien sind ungenutzt.

*Dieses Dokument wurde im Rahmen des autonomen System-Audits am 21. Mai 2026 erstellt. Zero Assumptions. Clinical. Brutally Honest.*
