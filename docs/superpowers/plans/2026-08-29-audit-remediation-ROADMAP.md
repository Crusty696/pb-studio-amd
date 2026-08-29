# Audit-Remediation — Roadmap (Rev. 3)

> **Dies ist KEIN ausfuehrbarer Plan.** Es ist die verifizierte Bestandsaufnahme und
> Reihenfolge. Es fehlen die Codebloecke, die `superpowers:writing-plans` fuer jeden
> Schritt verlangt — 125 Schritte, 0 Codebloecke. Ein Agent kann das nicht Schritt fuer
> Schritt abarbeiten.
>
> **Grund fuer die Aufteilung (Scope Check der writing-plans-Skill):** dieses Dokument
> spannt Audio, Video, Pacing, Brain, GPU, Storage, Security, Persistenz, Tests, Infra und
> die LTX-Uebernahme — mehrere unabhaengige Subsysteme. Die Skill verlangt dafuer je einen
> eigenen Plan, der fuer sich lauffaehige, testbare Software erzeugt.
>
> **Ausfuehrbare Teilplaene** (mit vollstaendigem Code je Schritt):
> - `2026-08-29-remediation-01-datenverlust.md` — Stufe 1
> - weitere folgen je Subsystem, jeweils erst wenn der vorige durch ist
>
> Diese Roadmap bleibt die gemeinsame Wahrheitsquelle fuer Reihenfolge, Abhaengigkeiten
> und den Verifikationsstand jedes Befunds.

> **Für ausführende Agenten:** Jeder Pfad, jedes Symbol und jede Zeilennummer in diesem
> Plan wurde am 2026-08-29 gegen den Arbeitsbaum geprüft. **Trotzdem gilt: vor jeder
> Änderung selbst greppen.** Zeilennummern verschieben sich, sobald der erste Task
> committet ist.

**Ziel:** Die im Audit 2026-08-29 belegten Defekte beheben — in einer Reihenfolge, die
Abhängigkeiten respektiert, und ohne die drei Befunde anzufassen, die sich bei der
Gegenprüfung als falsch oder als bewusster Kompromiss erwiesen haben.

---

## Warum Revision 2

Rev. 1 trug den Titel „Fully Verified & Validated" und war es nicht. Die Gegenprüfung ergab:

| Problem in Rev. 1 | Realität |
|---|---|
| `get_gpu_lock` importiert | heißt `get_gpu_inference_lock` (`gpu_lock.py:15`) |
| `reset_app_state()` importiert | existiert nicht |
| `src/pb_studio/pacing/pacing_service.py` | liegt unter `services/` |
| `src/pb_studio/pacing/smart_director.py` | liegt unter `ai/` |
| `src/pb_studio/storage/outbox.py` | heißt `data/vector_operation_outbox.py` |
| `PBStudio.UI/ViewModels/MainWindowViewModel.cs` | existiert nicht |
| `PBStudio.UI/Models/DirectorViewModel.cs` | liegt unter `ViewModels/` |
| Task 0.1: `--basetemp` entfernen | **bricht pytest komplett** — ausgeführt und belegt |
| Task 0.3: GPU-Fixture ändern | basiert auf C-17, und C-17 ist auf dieser Maschine falsch |
| Task 2.5: `RLock` statt `Lock` | **verdeckt** den Defekt, statt ihn zu beheben |

Rev. 1 hatte den Auditbericht gelesen, aber nicht gegen den Code geprüft — dasselbe Muster,
das der Bericht selbst als Kernproblem des Projekts beschreibt.

---

## Was seit dem Bericht passiert ist

**Erledigt und gepusht** (`b3f5ec8`, `6afd489` auf `codex/obj76-runtime-truth`):

- **C-02 gefixt.** `_decomp` in `app_state.py` ist typerhaltend, nimmt einen feldrichtigen
  Leerwert und loggt unlesbare Blobs. Regressionstest `Tests/test_app_state_ai_data_compression.py`
  (vor dem Fix 3 rot, danach 6/6 grün). **Dabei eine zweite Quelle desselben HTTP 500
  gefunden**, die im Bericht fehlte: `media_json_schema.py:102` setzt `{}` als Default, und
  `{}` bricht `Optional[SpectralData]` genauso wie `[]`, weil `SpectralData.clip_id`
  Pflichtfeld ist. Beide Quellen sind abgedeckt.
- Bericht, HTML-Version und CLAUDE.md-Korrekturen committet.

**Gestrichen — nicht umsetzen:**

| Befund | Grund |
|---|---|
| **C-16** `--basetemp` entfernen | Ausgeführt: danach `PermissionError [WinError 5]` am `pytest-current`-Symlink, **kein Test lief mehr**. Die Option ist eine Narbe, kein Versehen. Die reale Ursache der 5 Fehler waren parallele Audit-Läufe. Sauberer Lauf: **7 failed / 1497 passed / 0 errors** statt 10/1492/2. |
| **C-17** GPU-Fixture | Der Fake steht in `except DirectMLAdapterError`. Auf dieser Maschine löst der echte Adapter auf: `AMD Radeon RX 7800 XT`, `luid=0x00000000_0x00010c23`, 15.8 GB. Der Zweig wird nie betreten. Gilt nur für Runner ohne AMD-GPU. |
| **C-12** Dedup | Faktisch korrekt (34 Events → 1 bei 16teln @128 BPM), aber der Code dokumentiert den Trade-off selbst: „für Overlap-Jitter-Dedup gewollt … bei Problemen gegen `current_group[0]` vergleichen". Bewusster Kompromiss. **Erst entscheiden, dann ändern** — siehe Task 4.1. |

**Neu gefunden, nicht im Bericht:**

- Die Segment-Label-Umbenennung im Arbeitsbaum ist ein **Fix**, kein Bruch (siehe Task 2.6).
- `audio_router.py:2528`: der RAM-Schutz `duration=600.0` wurde entfernt (Task 3.4).
- `spectral_analyzer.py:150`: Duplikat-Key `mel_bands` (Task 1.1).
- CLAUDE.md führt die veraltete LUID `0x0001185b`; real ist `0x00010c23` (Task 5.3).

---

## Vorbedingungen

1. **Der Arbeitsbaum enthält 23 fremde geänderte Dateien** aus dem `patch.py`-Lauf.
   **Fünf der sieben verbleibenden Testfehler stammen von dort.** Vor Beginn entscheiden:
   diesen Stand committen, zurücknehmen oder in einen eigenen Branch schieben. Solange er
   liegt, ist nicht unterscheidbar, welcher Fehler von wem stammt.
2. **Bei jedem `pytest`-Aufruf ein eigenes `--basetemp` setzen**
   (`--basetemp=.pytest_tmp_<zweck>`). `pytest.ini` teilt sich sonst ein Verzeichnis, und
   pytest löscht es beim Sessionstart — parallele Läufe zerstören sich gegenseitig.
3. Nach jeder C#-Änderung: `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release`.
   Der Launcher lädt die Release-DLL.
4. Nach jeder Backend-Schema-Änderung: `openapi.snapshot.json` regenerieren **und**
   `ApiClient.cs` nachziehen. Sonst ist `test_openapi_snapshot_drift` rot.

---

## Stufe 1 — Verlorene Daten und stille Fehler

*Zuerst, weil hier bei jedem Lauf Daten verschwinden.*

> ### ✅ Tasks 1.1–1.4 abgearbeitet am 2026-08-29 (8 lokale Commits)
>
> Umgesetzt über `superpowers:subagent-driven-development` mit einer
> **Vorabverifikation pro Task** (User-Direktive: „nicht dass Bugs eingebaut
> werden, wo keine sind"). Vollsuite danach: **7 failed / 1522 passed /
> 13 skipped / 0 errors** — dieselben 7 Fehler wie vorher, keine neuen.
>
> **Die Vorabverifikation hat den Plan überwiegend widerlegt. Was hier unten
> steht, war zu drei Vierteln falsch:**
>
> - **1.1 ist sachlich falsch beschrieben.** `mel_bands` existierte **nicht in
>   HEAD**, sondern nur in einer fremden, uncommitteten Arbeitsbaum-Änderung.
>   Es gab dort keinen zu reparierenden Defekt. Mein Commit `d1724f6` hat die
>   fremde Änderung mitcommittet und dabei eine Fix-Message getragen (7
>   Einfügungen, **0 Löschungen**) — revertiert in `1d9a8d4`. Auch die Zahl
>   „60-Minuten-Mix, 40 Mio. Floats" stimmt nicht: die Streaming-Schwelle liegt
>   bei 600 s, realistisch sind ~6 Mio. Floats bei einem 9-Minuten-Track.
>   **Geblieben ist der Wächter** `Tests/test_no_duplicate_dict_keys.py` — der
>   ist nützlich und grün.
> - **1.2 wäre wirkungslos geblieben.** `state_conn = None` allein stoppt
>   `/brain/feedback` nicht; der Schreibpfad läuft über `_current_state_slot`
>   (`brain_service.py:311`). Umgesetzt als
>   `BrainService.force_unbind_project_state()`, die zusätzlich
>   `_retire_slot_locked` **und** `_close_state_connection` ruft — ohne die
>   beiden wäre ein Verbindungsleck entstanden, das unter Windows den
>   Projektordner festhält.
> - **1.3 hätte still nichts bewirkt.** Der Plan wollte eine nackte Liste
>   schreiben; der einzige Leser erwartet ein Dict und wäre in ein
>   `except Exception` gelaufen — Timeline gespeichert und trotzdem weg.
>   Zusätzlich hätte der Fix beim **Reopen desselben Projekts** frische Cuts
>   zerstört (ein Fall, der vorher harmlos war). Gelöst per Same-Path-Guard.
> - **1.4 behebt keinen erreichbaren Bug.** `_save_project_in_context` ist
>   synchron und await-frei (Event-Loop-atomar), `uvicorn` läuft einprozessig.
>   Die Begründung im Plan war zudem falsch: `App.xaml.cs:222` ruft
>   `IApiClient.SaveProjectAsync()`, nicht `ProjectService.SaveProjectAsync()`.
>   **Umgesetzt als Härtung**, C#-Teil ersatzlos gestrichen.
>
> **Neue Folgearbeiten aus den Reviews dieser Runde:**
>
> - [ ] Startup-Sweeper für verwaiste `.*.tmp` (durch die eindeutigen
>       Stage-Namen bleibt nach hartem Abbruch jede Leiche liegen; der Sweep in
>       `backend/main.py:280` kennt nur `.temp_render`)
> - [ ] `_write_project_meta` (`project_router.py:250`) auf die
>       `with_name`-Konvention ziehen — letzter fester, sichtbarer Temp-Name
> - [ ] Test-Spy in `test_concurrent_project_save.py` auf das Projektverzeichnis
>       eingrenzen (patcht `Path.write_text` prozessweit)
> - [ ] `install_project_state` verwirft beim Reopen weiterhin ungespeicherte
>       Cuts — **Altdefekt**, von dieser Runde bewusst nicht geheilt
> - [ ] `Tests/conftest.py:109/122` ruft `clear_project_state()` ungeschützt in
>       Setup und Teardown und nagelt die Funktion damit dauerhaft auf „melden
>       statt werfen" fest
> - [ ] `modified_at` in `project.json` bleibt nach Close-ohne-Save stale
>
> **1.5 bleibt offen** (Anker-Lesefehler) — hängt an einer Vertragsentscheidung.

### Task 1.1 — Duplikat-Key `mel_bands` entfernen

**Datei:** `src/pb_studio/audio/spectral_analyzer.py:150`

Der Dict enthält `"mel_bands"` zweimal (AST-verifiziert), die zweite Zeile mit falscher
Einrückung. `mel_db.tolist()` wird dadurch **zweimal** materialisiert — bei einem
60-Minuten-Mix rund 40 Millionen Floats. Repo-weiter Grep: **null Leser** für `mel_bands`.

- [ ] **1.** Wächter schreiben: `Tests/test_no_duplicate_dict_keys.py` — AST-Scan über
      `src/` und `backend/`, schlägt bei doppelten String-Keys in einem Dict-Literal fehl.
      Muss jetzt **rot** sein.
- [ ] **2.** Zeile 158 löschen (das eingerückte Duplikat).
- [ ] **3.** Entscheiden: `mel_bands` ganz entfernen (kein Konsument) oder behalten. Ohne
      Konsument sind es reine Rechen- und Speicherkosten pro Analyse.
- [ ] **4.** Wächter grün, dann `pytest Tests/test_audio_spectral_onsets_contract.py --basetemp=.pytest_tmp_t11`
- [ ] **5.** Commit: `fix(audio): drop duplicated mel_bands key from spectral result`

### Task 1.2 — Verschluckte Persistenzfehler sichtbar machen

**Dateien:** `backend/_brain_singleton.py:79`, `src/pb_studio/data/vector_store.py:184` und `:817`

Drei `except Exception: pass` an Stellen, an denen ein Fehlschlag Daten kostet:

- `_brain_singleton`: scheitert `unbind_project_state()`, bleibt `state_conn` an die
  **state.db des geschlossenen Projekts** gebunden. Jedes folgende `/brain/feedback`
  schreibt Lerndaten ins falsche Projekt. Der Nutzer bekommt HTTP 200.
- `vector_store` 2×: letzter FAISS-Persistenzpunkt. Alle seit dem letzten Write
  hinzugefügten Embeddings gehen verloren — ohne Log, ohne Exit-Code, ohne UI-Signal.

- [ ] **1.** Test: `_brain_singleton` mit fehlschlagendem `unbind_project_state` →
      `state_conn` muss danach `None` sein (Fail-closed statt falsch schreiben).
- [ ] **2.** `logger.error(exc_info=True)` in allen drei Handlern; `_brain_singleton`
      zusätzlich Hard-Kill von `state_conn`.
- [ ] **3.** `vector_store`: persistiertes Dirty-Flag setzen, wenn der Save scheitert, damit
      der Verlust beim nächsten Start überhaupt feststellbar ist. `atexit` darf nicht
      werfen — aber melden muss es.
- [ ] **4.** `pytest Tests/test_vector_store.py Tests/test_project_brain_binding.py --basetemp=.pytest_tmp_t12`
- [ ] **5.** Commit: `fix(storage): surface persistence failures instead of swallowing them`

### Task 1.3 — Timeline vor Projektwechsel sichern

**Dateien:** `backend/routers/project_router.py` (`close_project`, `_activate_project`),
`PBStudio.UI/Services/ProjectService.cs`

Die Timeline lebt bis zum manuellen `/project/save` nur im RAM. Weder `close_project` noch
der Projektwechsel speichern. **Wer nach einem Pacing-Lauf das Projekt wechselt, verliert
die Timeline ersatzlos.**

- [ ] **1.** Test: Timeline setzen → Projekt wechseln → zurückwechseln → Timeline muss da sein.
- [ ] **2.** Save vor dem Wechsel in `_activate_project` und `close_project`.
- [ ] **3.** `pytest Tests/test_project_persistence.py --basetemp=.pytest_tmp_t13`
- [ ] **4.** Commit: `fix(project): persist timeline before switching or closing a project`

### Task 1.4 — Parallel-Save-Race

**Datei:** `backend/routers/project_router.py:652` (`_save_project_in_context`),
`PBStudio.UI/Services/ProjectService.cs` (`SaveProjectAsync`)

Feste Stage-Dateinamen (`timeline.json.save.tmp`). Bei zwei gleichzeitigen Saves löscht
A's `finally`-unlink B's Stage-Datei; B wirft, B's Rollback überschreibt A's bereits
committeten Save. **Die Vorlage steht 200 Zeilen tiefer in derselben Datei:** `set_anchors`
nutzt `f".{path.name}.{uuid.uuid4().hex}.tmp"`.

- [ ] **1.** Test: zwei gleichzeitige Saves, beide müssen konsistent enden.
- [ ] **2.** `uuid4()`-Stage-Namen in `_save_project_in_context` und `_restore_file_snapshot`.
- [ ] **3.** `SaveProjectAsync` durch `_projectTransitionGate` führen — es ist die einzige
      Projektoperation ohne dieses Gate.
- [ ] **4.** Release-Build + `pytest Tests/test_project_persistence.py --basetemp=.pytest_tmp_t14`
- [ ] **5.** Commit: `fix(project): make concurrent saves safe with unique stage filenames`

### Task 1.5 — Anker-Lesefehler nicht als „keine Anker" ausgeben

**Datei:** `backend/routers/project_router.py:848` (`load_project_anchors`, `get_anchors`)

Bei unlesbarer `anchors.json` liefert der Endpunkt HTTP 200 mit leerer Liste. Die UI kann
„defekt" nicht von „keine Anker" unterscheiden, der Nutzer setzt neue, und `POST` überschreibt
via `os.replace` — **Datenverlust ohne Signal.**

- [ ] **1.** Test: defekte `anchors.json` → Endpunkt darf keine leere Erfolgsliste liefern.
- [ ] **2.** Fehlerkanal einziehen (HTTP 500 oder `source_status`-Feld), UI blockt das
      Überschreiben. `pacing_router._load_ui_anchors` bleibt best-effort — dort ist es korrekt.
- [ ] **3.** Commit: `fix(project): distinguish unreadable anchors from an empty anchor set`

---

## Stufe 2 — Kaputte Ketten zwischen Domänen

*Der Kernbefund des Audits. Reihenfolge innerhalb der Stufe ist bindend.*

### Task 2.1 — Downbeats: alle drei Brüche gemeinsam

**Dateien:** `backend/routers/audio_router.py:2255`, `:2258-2263`, `:2265`, `:2591`;
`src/pb_studio/services/pacing_service.py:389`

> **Nicht einzeln fixen.** Solange `get_downbeats()` wirft, ist die Liste zufällig sortiert
> und `beat_count` zufällig richtig. Repariert man nur den Aufruf, brechen Sortierung und
> Zähler **sofort** auf.

Drei Brüche in einer Kette:
1. `detector.get_downbeats()` ohne das Pflichtargument → `TypeError` (Signatur:
   `beat_detector.py:306` `get_downbeats(self, audio_path)`), gefangen von `except` bei `:2277`
2. Router schreibt `downbeat_provenance.status = "available"`, `pacing_service.py:389`
   prüft auf `"measured"`
3. Downbeats werden an `beats` angehängt, **nie sortiert** (Grep `beats.sort`: 0 Treffer);
   `beat_count` zählt sie doppelt

- [ ] **1.** Test: echte Audiodatei → Downbeats vorhanden, `beats` zeitlich sortiert,
      `beat_count` = Anzahl echter Beats, `downbeat_provenance` von `pacing_service`
      akzeptiert. **Muss dreifach rot sein.**
- [ ] **2.** `get_downbeats(audio_path)` — Pfad übergeben.
- [ ] **3.** `beats.sort(key=lambda b: b["time"])` nach dem Anhängen.
- [ ] **4.** `beat_count` auf echte Beats begrenzen (Downbeats sind Duplikate).
- [ ] **5.** Vokabular vereinheitlichen: **eine** Schreibweise, beide Seiten anpassen.
      `advanced_pacing_engine.py:645` setzt `"measured"` intern — dort gegenprüfen.
- [ ] **6.** `pytest Tests/test_beat_detector*.py Tests/test_pacing_engine.py --basetemp=.pytest_tmp_t21`
- [ ] **7.** Commit: `fix(audio): make measured downbeats reach the pacing engine`

### Task 2.2 — Beta-Bernoulli-Varianz

**Datei:** `src/pb_studio/brain/weight_store.py:239` (`_compute_variance`), Zeile 249

`denom = (alpha+beta)**2 * (alpha+beta+1)` — **ohne** den Laplace-Prior, den
`_compute_posterior_mean` 13 Zeilen darüber verwendet. Folge: jedes einseitig bewertete
Bucket hat Varianz **exakt 0**, die Learning-Session rankt genau die begonnenen Kontexte
ans Ende. Aktives Lernen konvergiert nie. `brain_router.py:475-480` rechnet die **richtige**
Formel — drei Stellen, zwei Formeln.

- [ ] **1.** Test mit **befülltem** Store: `α=24, β=0` muss Varianz `> 0` liefern.
      **Muss rot sein.** Die 12 bestehenden Sampler-Tests nutzen `empty_weights` und können
      den Defekt strukturell nicht sehen.
- [ ] **2.** Formel an `brain_router.py:480` angleichen: `a=α+1, b=β+1`,
      `var = a*b / ((a+b)²(a+b+1))`.
- [ ] **3.** `_compute_variance` dieselbe `MIN_CONFIDENT_SAMPLES`-Bedingung geben wie der
      Posterior — sonst bleibt die Level-Auswahl zwischen Mittel und Varianz asymmetrisch.
- [ ] **4.** `pytest Tests/test_brain_core.py Tests/test_brain_smart_sampler.py --basetemp=.pytest_tmp_t22`
- [ ] **5.** Commit: `fix(brain): include the Laplace prior in the posterior variance`

### Task 2.3 — `rejected_clips`: durchziehen oder zurücknehmen

**Dateien:** `backend/schemas/pacing_schemas.py:113-114`, `backend/routers/pacing_router.py`,
`PBStudio.UI/openapi.snapshot.json`, `PBStudio.UI/Services/ApiClient.cs:1475`,
`PBStudio.UI/ViewModels/DirectorViewModel.cs:380`, `PBStudio.UI/Views/DirectorView.xaml`

Gemessen: Schema **1**, Producer im Router **0**, Snapshot **0**, C#-Record **0**,
Reflection im ViewModel **1**. Die Reflection umgeht genau die Compilerprüfung, die den
Fehler sofort gezeigt hätte. **Zwei Guard-Tests sind deswegen rot.**

> **Entscheidung zuerst.** Zurücknehmen ist legitim und billiger.

**Variante A — zurücknehmen:** Felder aus `pacing_schemas.py` und den Reflection-Block aus
`DirectorViewModel.cs` entfernen. Beide Guard-Tests werden grün.

**Variante B — durchziehen:**
- [ ] **1.** Producer in `pacing_router.py` bei der `CutListResponse`-Konstruktion —
      `ClipSelector` trägt die Ablehnungsgründe bereits.
- [ ] **2.** `ApiClient.cs:1475` um zwei typisierte Properties erweitern.
- [ ] **3.** Reflection durch direkten Zugriff ersetzen.
- [ ] **4.** XAML-Binding in `DirectorView.xaml` ergänzen —
      `RejectionSummary` hat sonst weiterhin kein Ziel.
- [ ] **5.** Snapshot regenerieren, Release-Build.
- [ ] **6.** `pytest Tests/test_openapi_snapshot_drift.py Tests/test_viewmodel_binding_wiring.py --basetemp=.pytest_tmp_t23`
      — **beide müssen grün werden.**
- [ ] **7.** Commit: `feat(pacing): report rejected clips through the full contract`

### Task 2.4 — Embeddings erreichen den Reranker

**Dateien:** `src/pb_studio/services/pacing_service.py:521` und `:548`,
`src/pb_studio/pacing/clip_selector.py:591-592`, `backend/routers/pacing_router.py:986`

Gemessen: `audio_embedding`/`video_embedding` haben repo-weit **fünf Treffer, alle `.get()`**
— kein einziger Schreiber. Der Reranker entscheidet damit grundsätzlich ohne Semantik-Achse,
während der nachgelagerte Post-Prozessor sie sehr wohl berechnet. **Timeline und Feedback
zeigen Semantik-Scores für eine Auswahl, die ohne Semantik getroffen wurde** — das vergiftet
spätere Lernrunden.

Zweiter Bruch derselben Stelle: `pacing_service.py:521` setzt `brain_context_keys = [""]`,
hart auf Level 0. Die 6-stufige Backoff-Hierarchie wirkt nur in der Annotation.

- [ ] **1.** Test: Clips mit Embeddings im Cache → `semantic_match_weight` muss im
      Reranker-Pfad `available` sein. **Muss rot sein.**
- [ ] **2.** `_configure_brain_selector` den `EmbeddingCache` und die Media-Hashes reichen —
      `pacing_router.py:485-494` und `:517-519` haben beide bereits zur Hand.
- [ ] **3.** Entscheidung zu `brain_context_keys`: echte Kontextschlüssel liefern **oder**
      dokumentieren, dass die Auswahl bewusst nur Level-0-Gewichte nutzt. Der jetzige
      Zwischenzustand ist irreführend.
- [ ] **4.** `pytest Tests/test_pacing_brain_w5.py Tests/test_clip_selector_provenance.py --basetemp=.pytest_tmp_t24`
- [ ] **5.** Commit: `fix(pacing): feed embeddings to the brain reranker`

### Task 2.5 — SigLIP-Selbstdeadlock **ohne** RLock

**Dateien:** `src/pb_studio/ai/smart_director.py:883, :916, :1467, :1526` und `:346-399`

> **`RLock` ist die falsche Lösung.** Sie macht den Deadlock unsichtbar und verdeckt die
> eigentliche Ursache: **asymmetrische Sperrung**. `_unload_siglip`/`_unload_clap` mutieren
> `self._siglip`/`self._active_model` **unter** dem Lock, `_load_siglip`/`_load_clap`
> mutieren dieselben Felder **ohne** jedes Lock. Rev. 1 schlug `RLock` vor — das würde beide
> Defekte gleichzeitig zudecken.

`gpu_inference_lock` (`gpu_lock.py:13`) ist ein `threading.Lock()`. `SmartDirector` hält ihn
an vier Stellen und ruft darin SigLIP-Methoden, die ihn erneut nehmen. Feuert heute nur nicht,
weil `models/siglip_text.onnx` fehlt. Für CLAP ist dieselbe Falle in
`smart_director.py:555-557` erkannt und korrekt vermieden.

- [ ] **1.** Test: `encode_text` unter gehaltenem Lock darf nicht hängen (mit Timeout).
- [ ] **2.** Die vier `with self._inference_lock:`-Blöcke auflösen — das Lock gehört in den
      Wrapper, nicht in beide Ebenen. Vorbild: die CLAP-Behandlung im selben File.
- [ ] **3.** Load-Pfade unter dasselbe Lock ziehen wie die Unload-Pfade (Asymmetrie).
- [ ] **4.** Eviction-Callback: `_unload_siglip` ist als VRAM-Eviction-Callback registriert
      (`smart_director.py:250`) und nimmt darin den nicht-reentranten Lock. Lockfreie
      Variante registrieren, sonst entsteht beim Umbau ein **neuer** Selbstdeadlock.
- [ ] **5.** `pytest Tests/test_smart_director_integration.py Tests/test_gpu_core_release_readiness.py --basetemp=.pytest_tmp_t25`
- [ ] **6.** Commit: `fix(gpu): remove nested acquisition of the shared inference lock`

### Task 2.6 — Segment-Labels: Backfill für 121 Altbestände

**Dateien:** `src/pb_studio/audio/structure_analyzer.py`, Migration in `src/pb_studio/data/schemas/`

> **Korrektur zum Bericht.** Ich hatte die Umbenennung als Risiko gemeldet. Sie ist ein
> **Fix**: die Pacing-Gewichtungsmap kennt `verse/chorus/bridge/drop/buildup/breakdown`,
> der Analyzer lieferte bisher `high_energy/rising/falling/low_energy` — **keines davon
> steht in der Map**, alle Segmente fielen auf den Default. Die Umbenennung verbindet
> Producer und Consumer.

Der Fix ist nur unvollständig: die Datenbank enthält **121 Segmente mit alten Labels**
(gemessen: `plateau` 37, `rising` 24, `high_energy` 21, `falling` 21, `low_energy` 11,
`intro` 5, `verse` 2, `outro` 2). Die fallen weiter auf den Default.

- [ ] **1.** Test: persistiertes `high_energy` muss nach dem Laden eine Gewichtung ≠ Default
      bekommen.
- [ ] **2.** Migration: `high_energy→chorus`, `rising→buildup`, `falling→breakdown`,
      `low_energy→verse`. `plateau` bleibt — es **steht** in der Map (0.8).
- [ ] **3.** Die Inkonsistenz im Arbeitsbaum prüfen: an einer Stelle wurde `plateau→bridge`
      umbenannt, an anderer blieb `"chorus" if … else "plateau"`. Eine Schreibweise wählen.
- [ ] **4.** `dj_mix_analyzer.py:22-35` nutzt weiterhin die alten Namen — das Modul ist
      laut Audit toter Code außer `detect_mix_transitions`. Prüfen und entweder mitziehen
      oder als tot markieren.
- [ ] **5.** Commit: `fix(audio): align segment labels with the pacing weight map`

### Task 2.7 — Toter Motion-Schalter

**Dateien:** `src/pb_studio/pacing/advanced_pacing_engine.py:1829`,
`src/pb_studio/services/pacing_service.py:1264`

`enable_motion_matching()` setzt `self._use_motion_matching` — Grep findet **genau einen
Treffer, die Zuweisung selbst**. Kein Leser. `pacing_service.py:1264` ruft die Methode
produktiv auf und erzeugt damit nur den Logeintrag „Motion-Matching: aktiviert". Ein Nutzer,
der im Log nach der Wirkung seines Schalters sucht, findet eine Erfolgsmeldung für nichts.

- [ ] **1.** Entscheiden: Flag verdrahten **oder** Methode und Aufruf entfernen.
- [ ] **2.** Falls entfernen: prüfen, was `UseMotionMatching` in der UI dann noch bewirkt
      (laut Audit nur „advanced statt round-robin") und die Beschriftung anpassen.
- [ ] **3.** Commit: `fix(pacing): remove the no-op motion matching switch`

---

## Stufe 3 — Sicherheit, Wachstum, Laufzeit

### Task 3.1 — Recovery: `replace` an den Owner-Scope binden

**Datei:** `backend/recovery_bootstrap.py:174-179`, `_validate_delete_scope` bei `:196`

Für `restore_policy == "delete_if_present"` erzwingt der Code eine strenge Owner-Bindung mit
Dateinamen-Allowlist. Für `"replace"` — **den Default** — fehlt sie. Geprüft wird nur
„absolut" und „nicht im Control-Root". Erreichbar über `backend/main.py:32` auf **Modulebene**
— vor Config, Logging, App und jeder Middleware.

Kein Privilegien-Übergang (gleicher Benutzer), aber ein **Persistenz-Primitiv**: ein Prozess
mit Schreibrecht im Profil kann PB Studio dazu bringen, beim nächsten Start eine beliebige
Datei an beliebiger Stelle abzulegen — etwa im Autostart.

- [ ] **1.** Test analog zum bestehenden Delete-Scope-Escape-Test (`test_recovery_bootstrap.py:382`),
      aber für `replace`. **Muss rot sein** — dieser Fall ist ungetestet.
- [ ] **2.** `_validate_delete_scope` zu `_validate_owner_scope` verallgemeinern und **beide**
      Policies durchschicken.
- [ ] **3.** `pytest Tests/test_recovery_bootstrap.py --basetemp=.pytest_tmp_t31`
- [ ] **4.** Commit: `fix(recovery): bind replace targets to the owner scope`

### Task 3.2 — Die drei Begrenzer ohne Aufrufer

**Dateien:** `src/pb_studio/storage/embedding_cache.py:180`,
`src/pb_studio/data/vector_store.py:497` und `:521`,
`src/pb_studio/storage/recovery_generation.py`

- `enforce_size_limit()` — **0 Aufrufer**, während der Produzent bei jedem Import läuft.
- `mark_tombstoned` / `clean_tombstones` — **0 Aufrufer**. Der Docstring behauptet welche;
  die Outbox schreibt direkt in `_tombstoned_ids`, sodass der Kompaktierungs-Trigger
  (≥100 Tombstones **und** ≥20 %) nie greift. **Der FAISS-Index wird nie physisch bereinigt.**
- `request_restore_generation`, `plan_protected_retention`, `apply_protected_retention` —
  je 0 Aufrufer. Der Restore-Zweig läuft bei jedem Start, aber es gibt **keinen Weg, einen
  Restore anzufordern** und keinen, Generationen aufzuräumen. Jede enthält eine volle Kopie
  der 31,4-MB-Datenbank.

- [ ] **1.** Wächter-Test, der den **Produzenten** prüft: gibt es einen Aufruf von
      `enforce_size_limit` im Lifespan oder nach `store()`? (Nicht einen selbst injizierten
      Cache testen — das ist die dokumentierte Lehre aus 2026-08-07.)
- [ ] **2.** `enforce_size_limit` verdrahten, Limit aus `config.json`.
- [ ] **3.** Outbox über `mark_tombstoned` führen statt `_tombstoned_ids` direkt zu
      manipulieren — dann greift der Kompaktierungs-Trigger wieder und beide Methoden leben.
- [ ] **4.** Recovery-Retention verdrahten **oder** streichen. Ohne Aufräumpfad wächst
      `recovery-control` mit jedem Start/Shutdown-Paar.
- [ ] **5.** Commit: `fix(storage): wire the size limiters that had no callers`

### Task 3.3 — Frame-Sampling und Transcode

**Dateien:** `backend/routers/video_router.py:1701` (`_read_sample_frame`),
`src/pb_studio/rendering/render_service.py:681` (`_transcode_clip`)

> Der größte Laufzeithebel im Repo — und **beides ungemessen**. Vor dem Fix eine Messung
> anlegen, sonst ist der Erfolg nicht belegbar.

- **Frame-Sampling:** `while current_frame < candidate: cap.grab()` — vorwärts wird Frame
  für Frame dekodiert. Bei 120 Sample-Punkten über die volle Länge: **jedes Frame des Videos**.
  Der Kommentar sagt „Fast forward sequentially instead of using `CAP_PROP_POS_FRAMES`" —
  die Sequenzialität ist eine **bewusste** Änderung aus `patch.py`, der Preis wurde offenbar
  nicht gemessen. Erst klären, **warum** umgestellt wurde (vermutlich Genauigkeit bei
  Long-GOP), dann einen Kompromiss wählen: Keyframe-Seek plus kurzes Vorwärts-Grabben.
- **Transcode:** `_transcode_clip` hat **kein `-ss` und kein `-t`** (verifiziert: `cmd`
  enthält nur `-i`). Jeder Clip wird in voller Quelllänge all-intra bei 12 Mbit
  transkodiert; der Schnitt passiert erst im Concat-Demuxer.

- [ ] **1.** Messung anlegen: Analysedauer und Renderdauer für eine reale Datei, vorher/nachher.
- [ ] **2.** Frame-Seek mit Puffer; die Genauigkeitsfrage aus dem `patch.py`-Kommentar klären.
- [ ] **3.** `-ss`/`-t` mit Keyframe-Puffer, `inpoint`/`outpoint` in `_generate_concat_file`
      umrechnen. `Tests/test_release_repair_render_full_length.py:63` zementiert `-g 1` —
      all-intra bleibt für frame-genaues `inpoint` nötig, der Test ist mitzuziehen.
- [ ] **4.** `pytest Tests/test_release_repair_render_full_length.py Tests/test_video_pipeline_truth.py --basetemp=.pytest_tmp_t33`
- [ ] **5.** Commit: `perf(video): seek to sample frames and trim clips during transcode`

### Task 3.4 — RAM-Schutz für lange Mixe wiederherstellen

**Datei:** `backend/routers/audio_router.py:2528`

Der Arbeitsbaum entfernt `duration=600.0` beim `librosa.load` des Instrumental-Stems. Vorher
wurden maximal 10 Minuten geladen, jetzt die volle Datei: bei einem 2-Stunden-Mix
≈ 635 MB in einem einzigen Array, plus Resampling-Puffer. **Der Cap war eine bewusste
Schutzmaßnahme für den dokumentierten Kernanwendungsfall.** Kein Ersatz eingebaut.

- [ ] **1.** Cap wiederherstellen **oder** Chunking einbauen — und begründen, warum er
      entfernt wurde (vermutlich um die Tonart über den ganzen Mix zu bestimmen).
- [ ] **2.** Falls der volle Mix nötig ist: chunked laden und die Chroma-Vektoren mitteln.
- [ ] **3.** Commit: `fix(audio): restore the memory guard for long-mix key detection`

### Task 3.5 — Farbanalyse vom Event-Loop nehmen

**Datei:** `backend/routers/video_router.py:2267`, Aufruf bei `:1174`

`async def _run_color_and_caption_analysis` dekodiert Video und rechnet KMeans **direkt auf
dem Event-Loop** (verifiziert: blankes `await`, kein `to_thread`). Der gesamte Loop steht:
`/health` antwortet nicht, SSE-Keepalives laufen aus, der Client geht in Reconnect-Backoff.
**Sichtbar als „Backend nicht erreichbar" mitten in der laufenden Analyse.**

> ⚠️ Diese Funktion liegt in der laut CLAUDE.md für OBJ-76 **reservierten** Videoanalyse-Zone.
> **Vor der Änderung Freigabe einholen.**

- [ ] **1.** Freigabe einholen.
- [ ] **2.** Frame-Extraktion und KMeans in eine synchrone Hilfsfunktion ziehen, per
      `await asyncio.to_thread(...)` aufrufen. Der HTTP-/Caption-Teil bleibt async.
- [ ] **3.** Commit: `fix(video): move colour analysis off the event loop`

### Task 3.6 — Modell-Aktivierung auf einen Task begrenzen

**Dateien:** `backend/routers/models_router.py:865` (`activate_model`), `:935-943`;
`PBStudio.UI/ViewModels/ModelManagerViewModel.cs:301`

`activate_model` ohne `task`-Parameter schreibt das Modell in **jeden** capability-passenden
Task. Ein VLM meldet `{chat, vision}` — also alle sechs. Und die WPF ruft genau so auf.
**Ein Klick auf „Aktivieren" biegt still Chat, Tool-Use und HIRN um.**

Aktueller Stand in `config.json`: alle vier Text-Tasks zeigen auf `qwen2.5-vl-7b-instruct`,
ein 7B-Vision-Modell. Die gepflegten `task_preferences` sind dadurch Laufzeit-Totdaten.

- [ ] **1.** Test: `activate_model` ohne `task` darf nicht sechs Tasks setzen.
- [ ] **2.** Ohne expliziten `task` nur die Tasks der **primären** Capability setzen
      (VLM → Captioning).
- [ ] **3.** WPF: Task-Auswahl anbieten.
- [ ] **4.** `config.json` zurücknehmen — siehe Task 5.1.
- [ ] **5.** Release-Build + Commit: `fix(models): scope activation to matching tasks`

---

## Stufe 4 — Entscheidungen, keine Fixes

*Hier ist zuerst eine Festlegung nötig. Nicht blind umsetzen.*

### Task 4.1 — Trigger-Dedup: Kompromiss neu bewerten

**Datei:** `src/pb_studio/audio/streaming_analyzer.py:101` (`get_deduplicated`), Zeile 114

Der Vergleich läuft gegen `current_group[-1]` statt gegen den Gruppenanfang; eine Kette von
Events mit je ≤150 ms Abstand kollabiert auf **einen** Mittelwert (gemessen: 34 → 1 bei
16teln @128 BPM). Betrifft Onset, Kick, Snare und HiHat.

**Der Code dokumentiert das selbst:** „für Overlap-Jitter-Dedup gewollt … bei Problemen gegen
`current_group[0]` vergleichen." Es ist ein bewusster Kompromiss, kein Versehen.

- [ ] **1.** Entscheiden: ist der Verlust dichter HiHat-Muster bei ≥128 BPM akzeptabel?
- [ ] **2.** Falls nein: Dedup auf das bekannte Overlap-Fenster begrenzen statt wertbasiert
      zu gruppieren. **`Tests/test_streaming_analyzer.py:202-223` muss mit umgeschrieben
      werden** — der Test prüft den verketteten Mittelwert und würde bei einem Fix rot.
- [ ] **3.** Zusätzlich: der Nicht-Streaming-Pfad dedupliziert **gar nicht**. Zwei
      Datensemantiken je nach Dateilänge. Eine wählen.

### Task 4.2 — `update_video_analysis`: verdrahten oder löschen

**Datei:** `backend/app_state.py:1109`

177 Zeilen, **0 Produktions-Aufrufer** (verifiziert), 4 Tests. Produktion schreibt direkt über
`video_router.py:358`. Die dort gepflegten Invarianten — `has_embedding` aus `embedding_dim`
ableiten, `video_clips`↔`video_analysis_cache`-Spiegelung — **greifen im Produktionspfad nicht**.

- [ ] **1.** Entscheiden: verdrahten oder löschen.
- [ ] **2.** Falls löschen: die beiden Invarianten nach `video_router` retten, sonst gehen
      sie still verloren. Die 4 Tests mit entfernen — sie melden derzeit einen toten Pfad grün.

### Task 4.3 — Doppelte Vertragsschicht (T4.5)

87 NSwag-Typen / 4733 LOC generiert, **14 genutzt**, daneben 34 Handrecords. `CutListResponse`
existiert doppelt, die generierte (korrekte) Variante ist tot. **Das ist die Ursache beider
Feldverluste** (`rejected_clips`, `BrainStatsResponse`) — der generierte Pfad wird bei jeder
Schema-Änderung automatisch korrekt, der handgeschriebene muss manuell nachgezogen werden.

- [ ] **1.** Entscheiden: Handrecords durch `global using` auf die generierten Typen ersetzen,
      **oder** die NSwag-Generierung abschalten. Beide Auswege ändern die Contract-Pflege.

---

## Stufe 5 — Aufräumen

### Task 5.1 — Debug-Workarounds zurücknehmen

- [ ] `config.json`: die vier Text-Tasks auf ein Textmodell zurücksetzen (Task 3.6 zuerst,
      sonst schreibt der nächste Klick sie wieder um).
- [ ] `global.json`: `9.0.317` / `rollForward: latestPatch` → begründen oder auf
      `9.0.316` / `disable` zurück. In einem Projekt mit Supply-Chain-Gates ist `disable`
      üblicherweise Absicht.

### Task 5.2 — Umgebung gegen den Lock

**Gemessen:** torch `2.4.1+cpu` statt `2.11.0+cpu`, transformers `4.49.0` statt `5.5.4`,
hf-hub `0.36.2` statt `1.5.0`, starlette `1.0.0` statt `1.3.1`, setuptools `82.0.1` über dem
Pin `81.0.0`. Sechs Pakete aus dem Lock fehlen ganz. `torch-directml 0.2.5.dev240914` ist
installiert und steht in **keiner** Requirements-Datei.

- [ ] Entscheiden: Lock an die Realität anpassen (`scripts/lock_python_requirements.py generate`)
      **oder** venv neu bauen. Ein Clean-Install erzeugt sonst eine andere Umgebung als die,
      in der die Suite grün gemeldet wird.
- [ ] `torch-directml` dokumentieren oder deinstallieren.

### Task 5.3 — Stale Dokumentation

- [ ] CLAUDE.md: LUID `0x00000000_0x0001185b` → real ist **`0x00000000_0x00010c23`**
      (gemessen: `AMD Radeon RX 7800 XT`, 15.8 GB).
- [ ] `src/pb_studio/pacing/__init__.py:11-15` listet fünf **nicht existierende** Module.
- [ ] `src/pb_studio/rendering/__init__.py:1-9` nennt vier nicht existierende Klassen.
- [ ] `Tests/Validierung-Checkliste.md:116` fordert einen `libx264`-Fallback —
      **Widerspruch zu IRON RULE 4**.
- [ ] Docstrings, die Aufrufer behaupten, die es nicht gibt: `vector_store.mark_tombstoned`,
      `lmstudio_vision_wrapper._ist_warm`.

### Task 5.4 — Toter Code und Ballast

- [ ] `patch.py` und `function_inventory.json` löschen (Einweg-Artefakte, bereits angewandt).
- [ ] `tools/ffmpeg/bin/ffplay.exe` — **82,6 MB, null Referenzen**. Entfernen.
- [ ] `tools/ffmpeg/doc/` (34 HTML-Dateien, ~9 MB), Evidence-Blobs (~33 MB inkl. einer
      14,4-MB-`.tar.zst`), `Tests/__init__.py.bak`, `LM-Studio-Log_terminal.txt`.
- [ ] `scratch/` (17 Dateien) und `outputs/` in `.gitignore` aufnehmen.
- [ ] `.gitignore`: ~190 redundante `.pytest_tmp2/test_*current`-Einträge unter einer bereits
      vorhandenen Blanket-Regel.
- [ ] `ui_legacy_archived/` (3.843 LOC, 0 Importe, 12 gebrochene interne Imports) und die
      14 toten Module — als eigener Commit, nach den funktionalen Fixes.
- [ ] Vier tote `config.json`-Schlüssel: `app_name`, `version`, `ui`, `hardware.gpu_backend`.

---

## Stufe 6 — Übernahmen aus dem LTX-Desktop-Vergleich

Quelle: `Analyse_LTX_Desktop_vs_PB_Studio_AMD.md` und `Umsetzungplan_LTX_Uebernahme.md`
(Antigravity-Agent, 2026-08-29). **Gegen den Quelltext geprüft — zwei der vier Empfehlungen
sind bereits umgesetzt, zwei Faktenaussagen über PB Studio sind falsch.**

### Was der Bericht falsch sieht

| Aussage im LTX-Bericht | Befund am Quelltext |
|---|---|
| P1: „Health-Check in `PythonBridgeService.cs` integrieren" | **Existiert bereits.** `StartWatchdog()` (`PythonBridgeService.cs:355`) läuft periodisch (`while (!_isStopping)` + `Task.Delay`), prüft Health **und** Owner-Proof und startet den Prozess bei Verlust neu (`:423` „starte owned Prozess neu…"). |
| P3: „NSwag fest in `build.ps1` verankern" | **Existiert bereits.** `PBStudio.UI.csproj:42` — MSBuild-Target `BeforeTargets="CoreCompile"`, läuft bei **jedem** Build. |
| „Stem Separation: Demucs auf DirectML" | **Falsch.** `CLAUDE.md:297`: htdemucs läuft auf **CPU**, weil die gepinnte Umgebung PyTorch-CPU nutzt. DirectML greift nur für die ONNX-MDX-Pfade. |
| „Moondream2 Visual Tags" als aktives Merkmal | **Falsch.** `models/moondream_decoder.onnx` fehlt, der Moondream-Zweig ist unerreichbar. Tags kommen ausschließlich von LM Studio. |

Die beiden „bereits umgesetzt"-Punkte sind kein Vorwurf an den Bericht — sie zeigen nur,
dass er von außen auf das Repo geschaut hat. Für den Plan heißt es: **nicht anfassen.**

### Task 6.1 — NSwag-Empfehlung präzisieren (verschärft Task 4.3)

Der LTX-Bericht empfiehlt, den generierten Typvertrag verbindlich zu machen. Das ist richtig
— nur liegt das Problem woanders, als er vermutet.

NSwag **läuft** bei jedem Build und erzeugt 87 Typen (4733 LOC). Genutzt werden **14**.
Daneben stehen 34 handgeschriebene Records in `ApiClient.cs`. `CutListResponse` existiert
dadurch doppelt — die generierte Variante ist korrekt und **tot**, die handgeschriebene wird
benutzt und ist veraltet.

**Das ist die belegte Ursache beider Feldverluste** (`rejected_clips`, `BrainStatsResponse`):
der generierte Pfad wird bei jeder Schema-Änderung automatisch korrekt, der handgeschriebene
muss manuell nachgezogen werden — und wurde es zweimal nicht.

- [ ] **1.** Wächter-Test: für jeden handgeschriebenen Record in `ApiClient.cs` prüfen, ob ein
      generierter Typ gleichen Namens existiert. Bei Namensgleichheit die Felder vergleichen.
      **Muss für `CutListResponse` und `BrainStatsResponse` rot sein.**
- [ ] **2.** Entscheidung (identisch zu Task 4.3): Handrecords durch `global using` auf die
      generierten Typen ersetzen **oder** die Generierung abschalten. Halbe Sachen haben
      genau diese zwei Defekte produziert.
- [ ] **3.** Commit: `refactor(api): make the generated contract the single source of truth`

### Task 6.2 — Fakes statt Mocks (schließt C-18 und stützt das Testfundament)

Der stärkste Punkt der LTX-Analyse, und er trifft einen belegten Befund dieses Audits.

LTX kapselt schwere Seiteneffekte hinter Python-`Protocol`-Interfaces und **verbietet
`unittest.mock` per Test** (`test_no_mock_usage.py`). PB Studio hat kein solches Verbot:
**35 Testdateien nutzen `unittest.mock`/`MagicMock`** (gemessen).

Das verbindet sich direkt mit drei Audit-Befunden:

- **C-18:** `conftest.py:56-79` monkeypatcht `TestClient.request` **global** und injiziert die
  Owner-Capability in jeden Request. Die Sicherheitsgrenze ist für ~99,6 % der Suite aus.
- Die dokumentierte Lehre „Wiring-Guard statt Feature-Test": ein Test, der sich seine
  Abhängigkeit selbst injiziert, beweist nichts über Produktion.
- `Tests/test_vram_arbiter.py` prüft drei Methoden ausschließlich über `mock.assert_called*`
  — an einer Klasse mit **null** Produktions-Aufrufern.

- [ ] **1.** `Protocol`-Interfaces für die schweren Seiteneffekte definieren: ONNX-Inferenz
      (SigLIP, CLAP, RAFT), LM-Studio-HTTP, FFmpeg-Aufrufe.
- [ ] **2.** Leichte Fake-Implementierungen statt `MagicMock` — sie erzwingen, dass der Vertrag
      eingehalten wird, statt jeden Aufruf zu akzeptieren.
- [ ] **3.** `Tests/test_no_mock_usage.py` nach LTX-Vorbild — **zunächst als Warnung mit
      Allowlist** für die 35 Bestandsdateien, sonst blockiert der Wächter jede weitere Arbeit.
      Die Allowlist schrumpft mit jeder Migration.
- [ ] **4.** **C-18 zuerst:** die globale Capability-Injektion in `conftest.py` auf die Tests
      begrenzen, die sie brauchen. Die Umkehrung (`pytestmark = unauthorized_backend`)
      existiert bereits — sie gehört zum Default gemacht, nicht zur Ausnahme.
- [ ] **5.** `pytest Tests/ -q --basetemp=.pytest_tmp_t62`
- [ ] **6.** Commit: `test(harness): replace mocks with protocol fakes and scope the auth patch`

### Task 6.3 — Prompt-Enhancer für die FAISS-Suche (Feature, kein Fix)

**Vorbedingung: Task 2.4 muss erledigt sein.** Ein Prompt-Enhancer, der Freitext in eine
semantische Suche übersetzt, ist wertlos, solange der Reranker die Embeddings gar nicht
bekommt (C-05: fünf Leser, null Schreiber). Zuerst die Kette, dann die Bedienung.

Zweite Vorbedingung: `models/siglip_text.onnx` **fehlt**. Ohne Textencoder liefert
`encode_text` immer `None`, und jede Freitext-Suche fällt auf Motion-Ranking zurück. Das ist
zugleich der Grund, warum der Deadlock aus Task 2.5 heute nicht feuert — beide hängen an
demselben fehlenden Asset.

- [ ] **1.** Entscheiden, ob `siglip_text.onnx` bereitgestellt wird. **Wenn ja: Task 2.5 vorher
      abschließen**, sonst hängt die Cut-List-Generierung beim ersten Freitext-Suchlauf.
- [ ] **2.** Erst danach den Enhancer im CHAT- oder Director-Tab.
- [ ] **3.** Modellwahl beachten: `chat` zeigt derzeit auf ein 7B-**Vision**-Modell
      (Task 3.6). Für Prompt-Erweiterung ist das die schlechteste verfügbare Option.

### Nicht übernommen

**„Generative Keyframing UX"** — LTX generiert Videoinhalte, PB Studio schneidet vorhandenes
Material. Die Funktion hat in diesem Produkt keinen Anknüpfungspunkt.

---

## Abschluss-Gate

- [ ] Vollsuite **sequenziell**, mit eigenem basetemp:
      `PYTHONPATH=src .venv/Scripts/python.exe -m pytest Tests/ -q --basetemp=.pytest_tmp_final`
      — Referenz vor Beginn: **7 failed / 1497 passed / 13 skipped / 0 errors**
- [ ] `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release` → 0/0
- [ ] Native C#-Tests → 57/57
- [ ] `compileall backend src` → PASS
- [ ] **Live-Verifikation am laufenden Backend** für jeden Fix, der Nutzerverhalten ändert.
      Der gesamte Audit lief ohne laufendes Backend — das ist die größte offene Lücke.
- [ ] Obsidian-Vault (INDEX, log), CLAUDE.md und Memory nachziehen.

---

## Abdeckung

| Befund | Task | Status |
|---|---|---|
| C-01 Downbeats | 2.1 | offen |
| C-02 `_decomp` | — | **erledigt**, `b3f5ec8` |
| C-03 Varianz | 2.2 | offen |
| C-04 `rejected_clips` | 2.3 | Entscheidung offen |
| C-05 Embeddings | 2.4 | offen |
| C-06 Deadlock | 2.5 | offen — **nicht** per RLock |
| C-07 / C-08 VRAM | 3.2 (+ eigener Task) | offen |
| C-09 Transcode | 3.3 | offen, Messung zuerst |
| C-10 Frame-Sampling | 3.3 | offen, Messung zuerst |
| C-11 Event-Loop | 3.5 | offen, **Freigabe nötig** |
| C-12 Dedup | 4.1 | Entscheidung — dokumentierter Kompromiss |
| C-13 Subtrack-Raster | eigener Task | offen |
| C-14 `update_video_analysis` | 4.2 | Entscheidung offen |
| C-15 venv | 5.2 | Entscheidung offen |
| C-16 basetemp | — | **gestrichen**, Fix bricht pytest |
| C-17 GPU-Fake | — | **gestrichen**, auf dieser Maschine falsch |
| C-18 Security-Grenze | eigener Task | offen |
| H-Security Recovery | 3.1 | offen |
| H-Data Timeline/Save | 1.3, 1.4, 1.5 | offen |
| H-Storage Begrenzer | 3.2 | offen |
| H-Regler | 2.7 | offen |
| H-Modelle | 3.6 | offen |
| **Neu:** `mel_bands`-Duplikat | 1.1 | offen |
| **Neu:** `duration=600.0` | 3.4 | offen |
| **Neu:** Label-Backfill | 2.6 | offen |
| **Neu:** stale LUID | 5.3 | offen |
| LTX P1 Health-Watchdog | — | **bereits umgesetzt**, `PythonBridgeService.cs:355` |
| LTX P3 NSwag im Build | 6.1 | **läuft schon**; das Problem sind die Handrecords |
| LTX P2 Fakes statt Mocks | 6.2 | offen — schließt C-18 mit |
| LTX P4 Prompt-Enhancer | 6.3 | offen, **hängt an Task 2.4 und an siglip_text.onnx** |

**C-13 und C-18 haben in diesem Plan noch keinen ausgearbeiteten Task** — sie sind im Bericht
belegt, aber ich habe die Umsetzung nicht bis zum Schritt durchdacht. Das ist eine bekannte
Lücke, keine Auslassung.

---

## Nachtrag 2026-08-29 — aus der verworfenen Planfassung gerettet

Vor dem Löschen der älteren Fassung (`2026-08-29-audit-remediation-plan.md`,
Root, 1106 Z., Titel „Fully Verified & Validated") wurde sie vollständig gegen
dieses Dokument verglichen. Ergebnis: der weitaus größte Teil war redundant,
widerlegt oder bezog sich auf den uncommitteten `patch.py`-Stand. **Alle 15
Funktionsnamen ihrer Testcodeblöcke existieren in HEAD nicht** — die Tests wären
mit `ImportError` gescheitert, was der Plan als „erwartetes Rot" ausgab. Fünf der
genannten Dateipfade existieren ebenfalls nicht.

**Vier Befunde standen aber nur dort, sind am Quelltext in HEAD bestätigt und
fielen in diesem Dokument durch das Raster.** Die Codebeispiele der alten Fassung
waren auch bei diesen vieren erfunden; die Defekte selbst wurden unabhängig
nachgewiesen.

### Task 3.7 — Pacing lädt CLAP ohne VRAM-Buchführung (C-07)

**Dateien:** `backend/routers/pacing_router.py`, `src/pb_studio/services/pacing_service.py:103`,
`src/pb_studio/pacing/clip_selector.py:1286`, `src/pb_studio/ai/smart_director.py:287/418`

`with_gpu_task` kommt in `pacing_router.py` und `pacing_service.py` **0x** vor
(selbst nachgezählt). Ein Pacing-Lauf lädt über `SmartDirector.get_dominant_mood`
CLAP als ONNX-Session in den VRAM, ohne dass `VRAMBudgetManager` die Belegung je
sieht. Die seit 2026-08-07 verdrahtete Sensor-Gegenprobe ist für diesen Pfad blind.

Die Abdeckungstabelle dieses Dokuments verweist für C-07 auf „3.2 (+ eigener
Task)" — Task 3.2 behandelt aber ausschließlich `enforce_size_limit`, Tombstones
und Recovery-Retention, **kein Wort zu VRAM**. Der „eigene Task" existierte nicht.

- [ ] **1.** Wächter auf den **Produzenten**, nicht auf den Arbiter: läuft ein
      Pacing-Lauf mit aktiver Semantik durch `with_gpu_task`? Den Arbiter nicht
      mocken — Lehre vom 2026-08-07, ein Test mit selbst injizierter Abhängigkeit
      beweist nichts.
- [ ] **2.** Ort entscheiden: um den Router-Endpunkt (grob, aber ehrlich) oder um
      `get_dominant_mood`/`encode_text` im `SmartDirector`. Zweites kollidiert mit
      Task 2.5 — **danach einplanen**.
- [ ] **3.** `manage_vram`-Entscheidung dokumentieren. Von den drei bestehenden
      Aufrufen setzen zwei `manage_vram=False`; entweder dieselbe Begründung
      tragen oder echtes Budget führen.

### Task 2.8 — Tote obere Reglerbereiche (H-Regler)

**Dateien:** `advanced_pacing_engine.py:2024-2025` (auch `:1873/:1883/:2096/:2107`),
`pacing_models.py:31`, `DirectorView.xaml:231/246/261/290/314`

`PacingCut.__post_init__` klemmt `strength = max(0.0, min(1.0, strength))`. Die
Engine multipliziert vorher mit 0.9 (Kick) bzw. 0.85 (Snare). Der Slider läuft bis
2.0. Nachgerechnet:

| Regler | wirksam bis | toter Reglerweg |
|---|---|---|
| Kick | 1.111 | **44 %** |
| Snare | 1.176 | **41 %** |
| Beat | 1.000 | **50 %** |

Die obere Reglerhälfte verändert nichts, ohne jedes Signal an den Nutzer. Die
Abdeckungstabelle mappt „H-Regler" auf Task 2.7 — der behandelt aber nur den toten
`enable_motion_matching`-Schalter.

- [ ] **1.** Test: `kick_weight=2.0` muss eine andere Cut-Liste erzeugen als
      `kick_weight=1.2`. **Muss rot sein.**
- [ ] **2.** Entscheiden — Sliderweg auf den wirksamen Bereich zurücknehmen
      (billig, ehrlich) **oder** `strength` als unbeschränktes Gewicht führen und
      erst bei der Normalisierung klemmen. Nicht beides halb.
- [ ] **3.** Im selben Zug die vier weiteren Zeilen aus
      `FUNKTIONSAUDIT_2026-08-29.md` (Z. 415-421: `MinCutInterval`,
      `MaxCutInterval`, `trigger_settings.min_cut_interval` mit 0 Engine-Lesern) —
      gleiche Ursachenklasse.

### Task 2.9 — Stiller Degradationspfad im Pacing (H-Fake)

**Datei:** `src/pb_studio/services/pacing_service.py:1052`, `:1059-1062`, `:1394`,
`:1410-1413`, Fallback bei `:1481`

Vier Pfade fangen `Exception` und liefern `_generate_time_grid_fallback` als
**reguläres Ergebnis** zurück. Das Zeitraster arbeitet allein auf
`target_duration` — ohne Beats, Trigger, Struktur, Anker. Der Router meldet
`cut_count=N`, die UI zeigt „N Cuts generiert". **Ein Totalausfall der
musikalischen Analyse ist für den Nutzer von einem Erfolg nicht unterscheidbar**;
er steht nur im `backend.log`. In diesem Dokument bisher gar nicht vorhanden.

- [ ] **1.** Test: Engine wirft → die Antwort darf nicht wie ein normaler Erfolg
      aussehen. **Muss rot sein.**
- [ ] **2.** Herkunft mitliefern statt den Fallback zu streichen — er ist der
      letzte Rettungsanker. `generation_mode`/`degraded`-Feld in `CutListResponse`,
      vom Fallback gesetzt.
- [ ] **3.** WPF: Feld sichtbar machen (Schema, `openapi.snapshot.json`,
      `ApiClient.cs`, XAML, Release-Build). **Achtung:** genau diese Kette ist bei
      `rejected_clips` zweimal gerissen — Task 2.3/6.1 zuerst entscheiden.

### Task 3.8 — Synthetische Subtrack-Grenzen im 120-s-Raster (C-13)

**Datei:** `src/pb_studio/audio/subtrack_detector.py:56`, `:220-292`, `:173-175`

Nur für Mixe > 600 s. Pro 120-s-Chunk wird **ein** `librosa.beat.beat_track`
gerechnet und als `np.full(n_bins, tempo_value)` über den ganzen Chunk konstant
gehalten. Dadurch ist `s3 = |diff(tempo)|` (`:173-175`) überall exakt 0 **außer an
Vielfachen von 120 s**; `_normalize` hebt diese Einzelwerte auf 1.0, und
`W_TEMPO = 0.20` gibt ihnen ein Fünftel der fusionierten Novelty. Kein Overlap
zwischen den Chunks. **20 % der Novelty sind bei jedem langen Mix ein Artefakt des
Dekodierrasters** — und lange DJ-Mixe sind der dokumentierte Kernanwendungsfall.

Dieses Dokument benannte die Lücke („C-13 | eigener Task | offen"), hatte aber
keinen Task und keinen Dateizeiger.

- [ ] **1.** Test: synthetisches 15-Minuten-Signal mit konstantem Tempo → keine
      Grenze bei 120/240/360 s. **Muss rot sein.**
- [ ] **2.** Tempo interpolieren statt treppen (oder mehrere `beat_track`-Fenster
      je Chunk), Chunks mit Overlap laden — dann sind auch `onset_strength` und
      `chroma_cqt` an den Nähten nicht mehr angeschnitten.
- [ ] **3.** Gegenprobe an einer echten langen Datei: die Grenzen dürfen sich bei
      Änderung von `LONG_MIX_CHUNK_SEC` **nicht verschieben**. Das ist der
      eigentliche Beweis.

### Ausdrücklich NICHT übernommen

**C-10 (sequentielles `cap.grab()` statt `CAP_PROP_POS_FRAMES`)** — in HEAD nicht
vorhanden. `video_router.py` nutzt bei `:1673` und `:2253` bereits
`cap.set(cv2.CAP_PROP_POS_FRAMES, ...)`. Die Grab-Schleife existiert
**ausschließlich im uncommitteten `patch.py`-Stand**. Wer sie „repariert", fixt
eine fremde, nie committete Änderung — derselbe Fehler wie beim `mel_bands`-Fall
(`d1724f6`, revertiert in `1d9a8d4`). Solange über `patch.py` nicht entschieden
ist, ist Task 3.3 in diesem Punkt gegenstandslos.
