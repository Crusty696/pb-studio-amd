# PB Studio — App-weite Zustandsaufnahme

**Stand:** 2026-08-30 · **Basis:** `codex/obj76-runtime-truth` @ `1d7d0d6`
**Methode:** vier read-only Fach-Aufnahmen (Backend, `src/pb_studio`, WPF, Infrastruktur/Tests),
danach jede tragende Behauptung von mir selbst am Quelltext gegengelesen.

## Wie dieser Bericht zu lesen ist

Jeder Befund trägt eine Herkunftsangabe. Das ist keine Formalie — in dieser
Sitzung war ein Agentenbefund nachweislich falsch (die Fingerprint-Feldnamen
galten als verdrahtet; der Grep zeigte null Produzenten), und in der Sitzung
davor waren von vier geplanten Reparaturen drei fachlich verkehrt.

| Marke | Bedeutung |
|---|---|
| **SELBST GEPRÜFT** | Ich habe den Beleg gelesen und zitiere ihn. |
| **AGENT, GEGENGELESEN** | Von einer Aufnahme gemeldet, von mir am Quelltext bestätigt. |
| **AGENT, UNGEPRÜFT** | Gemeldet, von mir *nicht* nachgelesen. Als Hinweis behandeln, nicht als Fakt. |

Nichts in diesem Bericht stammt aus einem Laufzeit-Experiment, außer wo
ausdrücklich anders vermerkt. Es wurde kein Test von den Aufnahmen ausgeführt.

---

## 0. Was deine Entscheidung braucht — und zwar zuerst

### E-1 · Die Skip-Allowlist verfällt am 31.08. und legt danach den **gesamten** CI-Lauf still
**SELBST GEPRÜFT.**

`config/pytest-skip-allowlist.json` hat 23 Einträge, davon **8 mit
`expires_on: "2026-08-31"`** und 15 mit `2026-09-30` (selbst ausgezählt). `scripts/pytest_release_guard.py:66-70` wirft bei
jedem abgelaufenen Eintrag `pytest.UsageError`, und zwar in `pytest_configure`
— also **bevor ein einziger Test läuft**. Nicht ein Test wird rot; die Session
startet nicht. Der Guard ist in CI aktiv (`ci.yml:85`).

Zusätzlich verfallen am **01.09.** zwei Einträge in
`config/python-sca-exceptions.json`; `scripts/security_gate.py:50-53` bricht
analog ab. **Nebenbei aufgefallen:** die torch-Ausnahme ist auf
`"version": "2.11.0+cpu"` ausgestellt — installiert ist 2.4.1+cpu (siehe E-4).
Ob die Ausnahme die tatsächlich installierte Version überhaupt abdeckt, habe
ich nicht geprüft.

**Warum ich das nicht selbst verlängert habe:** ein Ablaufdatum ist die
Rechenschaftsmechanik. Es stillschweigend weiterzuschieben ist genau das
Verstecken eines Signals, gegen das die ganze Ehrlichkeitsdirektive gerichtet
ist. Entweder die acht Skips werden aufgelöst, oder du verlängerst bewusst.
Beides ist deine Entscheidung, nicht meine.

### E-2 · Der Modus `downbeat_only` ist in der Oberfläche wählbar und liefert garantiert nichts
**SELBST GEPRÜFT, von zwei Aufnahmen unabhängig bestätigt.**

Die Kette ist an vier Stellen gleichzeitig durchtrennt:

1. `beat_detector.py:306` `get_downbeats()` — **null Aufrufer repo-weit**, auch keine Tests.
2. `audio_router.py:2138` `downbeats: list[float] = []` — die **einzige** Zuweisung in der Datei.
3. Alle vier Schreibstellen von `downbeat_provenance` setzen `"status": "unavailable"`; `pacing_service.py:389` verlangt `"measured"`.
4. `audio_router.py:2173/2219` schreiben hart `"beat_type": "beat"`; `pacing_service.py:369` sucht `downbeat|bar`.

Die UI bietet den Modus an (`DirectorViewModel.cs:55`, gebunden in
`DirectorView.xaml:415-419`) mit dem Tooltip „benötigt Downbeat-Erkennung".

**Wichtig, weil es die naheliegende Reparatur ausschließt:** der bisher in
CLAUDE.md geführte Fix („Pflichtargument nachreichen") ist falsch.
`get_downbeats(audio_path)` ruft `self._estimator.process(audio_path)` — einen
**zweiten vollständigen BeatNet-Lauf** über die ganze Datei, zusätzlich zu dem
aus `detect_beats`. `BeatDetector.scan()` liefert Beats und Downbeats in einem
Durchlauf und ist der richtige Ansatzpunkt.

Entscheidung: Kette schließen oder den Modus aus der Oberfläche nehmen. Ein
Modus, der wählbar ist und nichts tut, ist die schlechteste der drei Optionen.

### E-3 · Toter Code in erheblichem Umfang — löschen oder als Legacy kennzeichnen?
**AGENT, teilweise gegengelesen.**

Das ist eine Architekturentscheidung, keine Defektmeldung. Ich habe nur den
Zustand belegt.

| Einheit | Zustand | Prüfung |
|---|---|---|
| `services/analysis_service.py`, `generation_service.py`, `media_service.py`, `video/engine.py` | null Produktionsaufrufer; einzige Importeure liegen in `ui_legacy_archived/` | **SELBST GEPRÜFT** |
| SyncMode-Planer der Pacing-Engine (`plan_cuts`, `_plan_beat_sync`, `_plan_hybrid_sync`, `_plan_emotional_sync`, `_identify_downbeats`) | nur über `GenerationService` erreichbar, also über die tote Schicht; 12 Tests schützen ihn | AGENT, UNGEPRÜFT |
| `core/vram_arbiter.py` (264 Z.) | null Produktionsaufrufer; `backend/main.py:213` benennt das im Kommentar | **SELBST GEPRÜFT** (Vorsitzung) |
| `video/video_embedder.py` | null Aufrufer, auch keine Tests; gelesen werden nur drei Konstanten | AGENT, UNGEPRÜFT |
| zweite ClipSelector-API (`add_clip`, `select_by_similarity`, `select_by_motion`, `select_by_energy`, `analyze_all_clips`) | live ist ausschließlich `_select_by_motion` | AGENT, UNGEPRÜFT |

**Der Grund, warum das mehr ist als Ballast:** vier verschiedene
Motion-Normalisierungen existieren nebeneinander (`/10.0`, `*8.0`, `/50.0`,
adaptiv). Drei davon liegen in totem Code. Wer einen dieser Pfade reaktiviert,
bekommt stillschweigend eine andere Skala.

### E-4 · Die installierte Umgebung ist nicht die gelockte — dreimal stärker als dokumentiert
**AGENT, UNGEPRÜFT im Detail; die vier bekannten Abweichungen SELBST GEPRÜFT (Vorsitzung).**

14 Versionsabweichungen, 13 zusätzlich installierte Pakete, 6 gepinnte aber
fehlende. Unter anderem torch 2.4.1 statt 2.11.0, transformers 4.49 statt
5.5.4, torchvision 0.19.1 statt 0.26.0. CI installiert `--require-hashes` und
misst damit **eine andere Umgebung als jeder lokale Lauf**. Entscheidung: Lock
an die Realität anpassen oder venv neu bauen. Beides hat Folgen, keins ist
autonom zu treffen.

---

## 1. Was ich in dieser Sitzung bereits behoben habe

| Commit | Befund | Beleg |
|---|---|---|
| `1d7d0d6` | **Phasennamen vergifteten `stage_status` dauerhaft.** `motion_embedding`, `colors_captions`, `persistence` sind keine Stage-Namen; ein einziges dort gelandetes `"failed"` machte den Clip für immer zu „nicht analysiert" — auch `force=True` heilte es nicht. | SELBST GEPRÜFT, 10 neue Tests, 65 Regressionstests |
| `1d7d0d6` | `audio_key_detector.py:46` importierte `pb_studio.config` — ein Modul, das nie existierte. Vom bare-except geschluckt. | SELBST GEPRÜFT, beide Pfade liefern nachgemessen denselben Wert |
| `dda7530` | **Eigene Regression.** Mein SDK-Pin auf 9.0.317 hätte den CI-Build gebrochen (`latestPatch` rollt nur vorwärts, CI installiert 9.0.316). Jetzt 9.0.316 als Untergrenze — beide Seiten erfüllt. | SELBST GEPRÜFT, lokaler Release-Build 0/0 |
| — | **DB-Index war beschädigt** (`row 604/605 missing from index idx_media_status`). Backup, `REINDEX`, `integrity_check: ok`. 6 Projekte / 711 Medien unverändert. | SELBST GEPRÜFT |

**Vollsuite nach diesen Aenderungen:** **2 failed / 1558 passed / 13 skipped /
0 errors** (24:35, sequenziell, eigenes `--basetemp`). Das Plus von 10
gegenueber dem Lauf davor sind exakt die zehn neuen Tests aus `1d7d0d6`.
Dieselben zwei Fehler wie vorher, beide Infrastruktur:

- `test_audit_sdd_gate` — der Marker `specs/00019-…/.qc-passed` pinnt
  `commit_sha 20792e75`, und `scripts/validate_sdd.py:665` verlangt Aktualitaet
  fuer HEAD. Der Test ist damit **nach jedem Commit** rot und traegt im
  Arbeitsalltag kein Signal.
- `test_t357::test_lhm_backup_restore_copy_reproduces_exact_file_set_and_hashes`
  — loest ueber eine Evidence-Datei den Ordner
  `tools/LibreHardwareMonitor.backup-20260730T0515+0200` auf. Der faellt unter
  `.gitignore:62 /tools/*`, war nie getrackt und existiert nicht mehr. Der Test
  kann in **keinem** Clone je gruen werden.

Datenbank vor und nach jedem Lauf dieser Sitzung: 6 Projekte, 711 Medien,
`integrity_check: ok`.

---

## 2. Backend — offene Befunde

### B-1 · `/project/open` meldet `has_timeline: true` für eine Timeline, die es gerade verworfen hat
**AGENT, GEGENGELESEN.** `project_router.py:360-373` setzt bei jedem Fehler
`state.set_timeline([])` und loggt nur eine Warnung; `:793` rechnet aber
`bool(meta.get("has_timeline") or has_timeline)` — der stale Wert aus
`project.json` gewinnt. HTTP 200, Timeline im RAM leer. Der Fehler zeigt sich
erst als `400 "Keine Timeline für Rendering vorhanden"`.

### B-2 · Ein fertig gerendertes Video wird als „Rendering fehlgeschlagen" gemeldet
**AGENT, GEGENGELESEN.** `render_router.py:1484-1508` setzt COMPLETED, nachdem
`render_service.py:385` die Datei final abgelegt hat. Erst danach läuft die
Queue-Buchhaltung (`:1117`), die bei jedem DB-Problem `PersistenceError` wirft
— gefangen vom pauschalen Handler `:1223`, der den Zustand mit `FAILED`,
`run_id=None`, `evidence_path=None` überschreibt. Ein Buchhaltungsfehler nach
erfolgreichem Artefakt darf kein `failed` sein. Ob die Queue-Persistenz real
scheitert, ist ohne Lauf nicht entscheidbar — der Codepfad ist es.

### B-3 · `/video/motion/{id}` erfindet für nie analysierte Clips `motion_category: "medium"`
**AGENT, GEGENGELESEN.** `_load_persisted_video_analysis` gibt `{}` zurück, nie
`None`; beide Detail-Endpunkte prüfen aber `if analysis is None:`. Ergebnis:
HTTP 200 mit einer erfundenen Bewegungsklasse statt 404.

### B-4 · `motion_category` — verschachtelt geschrieben, top-level gelesen, und der Leser hat selbst keinen Leser
**AGENT, GEGENGELESEN.** Einziger Writer schreibt ins `motion`-Subdict;
`pacing_router.py:985` liest top-level und bekommt für **jeden** Clip den
Literal-Default `"medium"`. Und `motion_category` kommt in `src/` überhaupt
nicht vor — das Feld wird nie gelesen.

### B-5 · `has_audio_embedding` / `has_video_embedding` sind permanent `False`
**SELBST GEPRÜFT.** Je genau ein Writer, beide schreiben `False`. Für Audio
wird das Embedding real gespeichert, das Flag zieht nicht nach. Daneben
existiert das *funktionierende* `has_embedding`. Zwei Namen für dieselbe Sache,
einer davon tot.

### B-6 · `/brain/stats` liefert drei Herkunftsfelder, die die UI nicht deserialisiert
**AGENT, GEGENGELESEN, von zwei Aufnahmen unabhängig.**
`weight_semantics_version`, `archived_observations`, `migration_reason` stehen
im Schema und im Snapshot, fehlen im C#-Record. CLAUDE.md führt seit 2026-08-06
„Brain-Herkunft sichtbar" — der Endpunkt meldet sie, die UI verwirft sie.

### B-7 · Zwei Klassen heißen `StatusResponse`, beide sind `response_model`
**AGENT, GEGENGELESEN** — mit hartem Beleg im committeten Snapshot:
`backend__routers__chat_router__StatusResponse` neben
`backend__schemas__common__StatusResponse`. Modulverkettete Namen, die jeder
Generator so übernimmt.

### B-7a · Etwas schreibt zur Laufzeit in `config.json` — Schreiber nicht identifiziert
**SELBST BEOBACHTET, Ursache OFFEN.**

Ich hatte die `task_overrides` in `config.json` bewusst auf dem HEAD-Stand
belassen (`qwen3.5-9b`); `git status` war beim Push um 22:5x sauber. Um
**23:09:07** stand exakt die verworfene Änderung wieder in der Datei — alle
vier Chat-Aufgaben auf `qwen2.5-vl-7b-instruct`, also auf das Vision-Modell.
Ich habe sie nicht geschrieben.

**Der Mechanismus, der so etwas ermöglicht, ist belegt:**
`ConfigManager.set()` (`config_manager.py:154-157`) schreibt über
`save_config()` die **gesamte** In-Memory-Konfiguration zurück. Wer also
irgendeinen Abschnitt setzt — etwa `health_router.py:99` das VRAM-Limit unter
`hardware` — persistiert dabei auch jede fremde Veränderung an `ai`. Und
`ConfigManager` ist ein Singleton (`__new__`, `_instance`): wer ihn zuerst
real instanziiert, legt `config_file` auf die Repo-Datei fest.

**Was ich ausgeschlossen habe** (je eigener Lauf mit Hash-Vergleich vorher/nachher):
`test_t357_models_router_persistence.py`, `test_model_registry.py`,
`test_t357_model_inventory_receipts.py`,
`test_t357_gpu_wpf_nullability_contracts.py`, `test_config_manager.py`,
`test_config_manager_paths.py` — alle sechs lassen die Datei unverändert. Auch
ein vollständiges `--collect-only` über alle 1572 Tests ändert nichts, ein
Schreibvorgang beim Modulimport ist damit ausgeschlossen. Das laufende Backend
war zum fraglichen Zeitpunkt bereits beendet.

**Damit korrigiere ich eine eigene frühere Einordnung:** ich hatte die
`config.json`-Änderung dem `patch.py`-Stand zugerechnet. Ob sie von dort stammt
oder von diesem unbekannten Laufzeit-Schreiber, ist **offen**. Die Entscheidung,
sie nicht zu übernehmen, bleibt davon unberührt richtig — ein Vision-Modell als
globales Chat- und Tool-Use-Modell ist ohne Beleg ein Rückschritt.

**Warum das zählt:** eine Anwendung, die die Konfigurationsdatei des Nutzers
ungefragt umschreibt, macht jede bewusste Einstellung unzuverlässig. Der
nächste Schritt wäre ein Schreib-Wächter auf der Datei während eines
Vollsuite-Laufs.

### B-8 · `media.status` trägt vier unvereinbare Vokabulare
**AGENT, UNGEPRÜFT.** `completed|partial|failed` vs. `analyzed` (auch beim
Import, vor jeder Analyse) vs. `pending` vs. `analyzing|error|ready`.
`update_status` validiert nichts. — **Eigene Beobachtung dazu:** genau der
Index `idx_media_status` war heute zweimal beschädigt. Ein Zusammenhang ist
naheliegend, aber **nicht belegt**.

---

## 3. WPF — offene Befunde

### W-1 · Der Binding-Wächter erzeugt nachweisbare Falsch-Grüns
**SELBST GEPRÜFT — ich habe beide Fälle nachgestellt.** `test_viewmodel_binding_wiring.py` matcht
`f"Binding {prop}"` als **Substring** gegen alle XAML-Dateien **zusammen** und
ordnet jede Klasse einer Datei dem Datei-Stem zu. Folgen, jeweils belegt:

- **Präfix-Falschgrün.** Eigene Gegenprobe über alle `Views/*.xaml`:
  `"Binding IsLoading"` als Substring → **True**; wortgenau
  (`Binding IsLoading(?![A-Za-z0-9_])`) → **False**. Die Treffer sind
  ausnahmslos `IsLoadingSuggestions` (`DirectorView.xaml:700`),
  `IsLoadingClips` (`VideoLibraryView.xaml:176`), `IsLoadingThumbnails` (`:237`),
  `IsLoadingScenes` (`:560`) und `IsLoadingWaveform` (`AnchorView.xaml:153`).
  Vier echte `IsLoading`-Properties gelten damit als gebunden und sind reine
  Schreib-Senken.
- **Klassenübergreifendes Falschgrün.** `Binding CurrentStep` existiert
  wortgenau — aber nur in `AudioLibraryView.xaml:321` und
  `VideoLibraryView.xaml:639`. In `DirectorView.xaml` kommt es **nicht** vor.
  Da der Wächter alle XAML aneinanderhängt, gilt `DirectorViewModel.CurrentStep`
  als gebunden. Der KI-Regie-Tab zeigt den SSE-Schritt nicht, zwei andere
  Analyse-Tabs schon.

Der Wächter ist damit schwächer, als CLAUDE.md ihn führt. **Das ist der
wichtigste Befund der WPF-Aufnahme**, weil er die Verlässlichkeit aller anderen
Binding-Aussagen betrifft.

### W-2 · Drei Einträge in `INTENTIONALLY_UNBOUND` sind sachlich falsch etikettiert
**AGENT, UNGEPRÜFT.** `AnchorViewModel.VideoClipId` („keine weitere
Verwendung") wird gelesen; ein ersatzloses Entfernen verlöre still die
Anker→Clip-Zuordnung beim Speichern. Ebenso `TimelineViewModel.HorizontalOffset`
(Virtualisierung) und `ModelManagerViewModel.CompletedBytes`/`TotalBytes`. Der
Test prüft die *Existenz* eines Eintrags, nie seinen Inhalt.

### W-3 · `force` ist von der Oberfläche aus nicht erreichbar
**SELBST GEPRÜFT.** Repo-weiter Grep über `PBStudio.UI/**/*.cs`: `"force"`
kommt ausschließlich in `obj/Generated/ApiTypes.g.cs` vor — also nur in den
generierten DTOs, die dieser Aufrufpfad gar nicht benutzt. Kein
handgeschriebener Aufruf sendet das Feld. Weder `/audio/analyze` noch `/video/analyze` bekommen von
der WPF ein `force`-Feld. `video_router.py:152` nennt „explicit force"
ausdrücklich als den Weg, eine `"unavailable"`-Stage neu zu fahren — den die UI
nicht hat. Eine Neuanalyse ist damit aus der App heraus nicht auslösbar.

### W-4 · `LastErrorDetail` ist veränderlicher Zustand auf einem Singleton
**AGENT, UNGEPRÜFT.** `IApiClient` ist Singleton, alle 16 ViewModels sind
transient und teilen die Instanz. `GetAsync<T>` setzt das Feld weder noch räumt
es auf — nach einem fehlgeschlagenen GET liest ein Konsument den Detailtext
eines *früheren* POST.

---

## 4. Infrastruktur und Testqualität

### I-1 · `test.bat` kann per Konstruktion nicht grün durchlaufen
**AGENT, UNGEPRÜFT.** Der Wrapper startet nach pytest immer den GUI-Agenten,
der `Tests/media/test_video.mp4` und `test_audio.wav` lädt. Das Verzeichnis
existiert nicht, und `.gitignore` schließt `*.mp4`, `*.wav` und `media/` aus —
die Fixtures **können nie eingecheckt werden**. `-NoGui` ist nicht
durchreichbar.

### I-2 · Die Testsuite hat ein messbares Beweiskraftproblem
**AGENT, UNGEPRÜFT.** 38 von 202 Testdateien importieren keine Zeile aus
`pb_studio`/`backend`, sondern lesen Quelltext als Zeichenkette; 24 davon sind
die `test_wpf_*_contract.py`-Familie, deren einziger Import `pathlib.Path` ist.
Ein Feldname in einem Kommentar erfüllt ihre Assertions.

Konkrete Fälle, die ohne das Feature grün blieben: vier `assert True` in
`test_pacing_progress_events.py`; `test_vram_arbiter.py` assertiert gegen einen
selbst eingeschleusten Mock einer Klasse ohne Produktionsaufrufer;
`test_vector_store.py` umgeht elfmal `__init__` und leitet Ergebnisse aus selbst
gesetzten Mock-Attributen ab.

Dazu **Skip genau im Defektfall**: `test_timeline_integrity.py:251-255` skippt,
wenn die Cut-Liste leer ist — also genau im `downbeat_only`-Nullfall aus E-2.

### I-3 · Sechs pytest-Einstiegspunkte ohne eigenes `--basetemp`
**AGENT, UNGEPRÜFT.** `pytest.ini` warnt ausdrücklich davor; umgesetzt ist es in
genau einem Runner. Das ist die Ursache der falschen „10 failed"-Messung im
Audit vom 29.08.

### I-4 · `coverage_run_v2.bat:14` startet nicht
**SELBST GEPRÜFT.** Die Zeile lautet
`coverage run -c .coveragerc -m pytest …`. In
`.venv/Lib/site-packages/coverage/cmdline.py` ist die Konfigurationsdatei
ausschließlich als `--rcfile` definiert (Zeile 290); ein Optionsobjekt `-c`
existiert dort nicht. optparse bricht ab, `-m pytest` wird nie erreicht.

### I-5 · 270 getrackte Dateien, die `.gitignore` ausschließt
**AGENT, UNGEPRÜFT.** Darunter `tools/ffmpeg` (44, inkl. `ffmpeg.exe`) und
`tools/LibreHardwareMonitor` (42). Die Kommentare in `.gitignore` beschreiben
nicht den tatsächlichen Repo-Inhalt.

### I-6 · Vier tote `config.json`-Schlüssel
**SELBST GEPRÜFT.** `app_name` (`"PB Studio (AMD Premium)"`), `version`
(`"1.0.0-amd"`), `hardware.gpu_backend` (`"directml"`) und `ui` (`{}`) haben
außerhalb des DEFAULTS-Literals in `config_manager.py` keinen Leser. Die
15 `version`-Treffer im gezielten Grep sind sämtlich andere Dinge
(DB-Schemaversion, Render-Payload-Version), kein Zugriff auf den
Konfigurationsschlüssel. Dieselbe Kategorie, die die T4.6-Aufräumung für sechs
andere Schlüssel bereits erledigt hat.

Nebenbefund zu `hardware.gpu_backend`: der Wert steht auf `"directml"`, wird
aber nie gelesen — die DirectML-Bindung entsteht ausschließlich im Code. Ein
Schlüssel, der aussieht, als könne man damit umschalten, und es nicht kann.

---

## 5. Was nachweislich in Ordnung ist

Damit die Liste nicht nur Mängel zeigt — diese Punkte wurden geprüft und halten:

- **Keine Iron-Rule-Verstöße.** Kein CUDA, kein ROCm, kein `pynvml`, kein
  NVENC im Quellcode; alle 13 Fundstellen sind Kommentare, die deren Abwesenheit
  dokumentieren. Alle DirectML-Sessions gehen über **eine** Setzstelle
  (`directml_adapter.py:428-429`), die beide Pflichtflags setzt, mit
  Gegenprüfung auf `:459-460`. Keine Session ohne beide Flags gefunden.
- **Keine C#-Reflection, kein `dynamic`.** Alle 34 `GetProperty`-Treffer sind
  `JsonElement`. Der Präzedenzfall aus dem `patch.py`-Stand wiederholt sich nicht.
- **Kein XAML-Binding auf einen im Projekt unbekannten Namen.**
- **Kein toter Converter**; alle neun Klassen sind referenziert.
- **SSE ist vollständig verdrahtet:** alle acht publizierten Eventtypen sind im
  Progress-Filter und haben C#-Handler.
- **Der Stem-Cache-Marker** validiert Größe, mtime, Frames, Samplerate, Kanäle
  und Rolle — sorgfältiger als der Ruf des Repos.
- **`OwnerCapabilityMiddleware`** ist sauber default-deny.
- **`scripts/run_python_quality_gate.ps1`** ist gut gebaut: eigenes basetemp,
  Temp-Diff vorher/nachher, Pfad-Guard gegen Fremdlöschung.
- **`requirements-direct.txt` und `requirements.txt`** sind driftfrei (42/42).

---

## 6. Grenzen dieser Aufnahme

- **Es wurde nichts ausgeführt.** Kein Test, kein Backend, keine GPU-Inferenz
  von den vier Aufnahmen. Jede Laufzeitaussage ist als Herleitung gekennzeichnet.
- **Die Aufruferzählungen sind grep- und AST-basiert.** `getattr(obj, name)`,
  Registry-Dispatch und `importlib` sind damit nicht erfasst. Vor jeder Löschung
  von totem Code ist das nachzuholen.
- **Nicht abgedeckt:** `models_router.py` (42 KB) und `brain_router.py` (33 KB)
  außer der Feldproduktion, `recovery_bootstrap.py`, `rendering/`, `utils/`,
  `PBStudio.UI/Controls/` und `Helpers/`, das C#-Testprojekt
  `PBStudio.UI.Tests/`.
- **Die Onset-Parameterdivergenz** aus CLAUDE.md (Cache/Stem/Fallback mit drei
  Parametersätzen) wurde lokalisiert, aber **weder bestätigt noch widerlegt**.
- Die mit **AGENT, UNGEPRÜFT** markierten Befunde habe ich nicht selbst
  nachgelesen. Sie sind Hinweise, keine Fakten.
