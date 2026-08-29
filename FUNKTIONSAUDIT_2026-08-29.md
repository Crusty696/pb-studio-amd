# PB Studio — Vollständiger Funktionsaudit

**Stand:** 2026-08-29
**Branch:** `codex/obj76-runtime-truth` @ `8328d49` (Arbeitsbaum **schmutzig**: 892 Zeilen über 24 Dateien)
**Methode:** 15 read-only Forensik-Audits in zwei Teams, je Domäne vollständige Lektüre statt Stichprobe
**Umfang:** 64.164 LOC Python (376 Dateien), 18.423 LOC C# (86 Dateien), 19 XAML, 204 Testdateien

---

## 0. Wahrheitsgrenze — was dieser Bericht NICHT belegt

Diese Grenze steht bewusst vorne, nicht im Anhang.

- **Kein Live-Backend.** Backend (`8765`), LM Studio (`1234`) und Ollama waren während des gesamten Audits offline (`netstat`: kein Listener). Jede Aussage über Laufzeitverhalten ist aus gelesenem Code oder aus pytest abgeleitet, **nicht** aus einem laufenden System.
- **Keine WPF-Laufzeit.** Build und 57 native Tests belegen Kompilierbarkeit — nicht, dass eine Funktion für den Nutzer arbeitet. WPF-Bindings sind statisch geprüft; ein Binding auf den falschen Typ mit gleichem Namen bliebe unentdeckt.
- **Keine Modell-ID ist verifiziert.** LM Studio antwortete nicht. Sekundärbelege (Dateisystem, Server-Logs) sind als solche gekennzeichnet.
- **Ungelesene Zeilenbereiche:** `backend/routers/audio_router.py` 2134–2320, 2400–2482, 2585–2612.
- **Nicht gemessen:** alle Laufzeit- und Größenordnungsaussagen (Frame-Dekodierung, Transcode-Volumen, Recovery-Verzeichnis).

---

## 0b. Nachtrag — eigene Gegenprüfung und Umsetzung (2026-08-29, später)

Auf Nachfrage habe ich drei Aussagen, die ich aus Agentenberichten übernommen hatte,
selbst am Quelltext nachgeprüft. Ergebnis: zwei bestätigt, **eine Ursachenanalyse falsch**.

### Gegenprüfung aller 18 CRITICAL (2026-08-29, eigene Verifikation)

Jeder CRITICAL wurde am Quelltext gegengelesen. **15 bestätigt, 1 abgeschwächt, 2 falsch.**

| Befund | Ergebnis der Gegenprüfung |
|---|---|
| C-01 Downbeats | bestätigt — Signatur verlangt `audio_path`, Aufruf übergibt nichts |
| C-02 `_decomp` | bestätigt, **breiter** (siehe unten), **gefixt** |
| C-03 Varianz | bestätigt — `denom = (α+β)²(α+β+1)` ohne Prior; Router rechnet `a = r[3]+1.0` |
| C-04 `rejected_clips` | bestätigt — Schema 1, Producer **0**, Snapshot **0**, C#-Record **0**, Reflection 1 |
| C-05 Embeddings | bestätigt — 5 Treffer repo-weit, **alle `.get()`**, kein Schreiber |
| C-06 Deadlock | bestätigt — `threading.Lock()`, SmartDirector 6×, SigLIP 4×, `siglip_text.onnx` fehlt |
| C-07 Pacing ohne VRAM | bestätigt — `with_gpu_task` in `pacing_router`: 0 |
| C-08 VRAM schlafend | bestätigt — 3 Aufrufe, 2× `manage_vram=False`, dritter unerreichbar |
| C-09 Transcode | bestätigt — `cmd` enthält `-i`, kein `-ss`, kein `-t` |
| C-10 Frame-Sampling | bestätigt — `while current_frame < candidate: cap.grab()` |
| C-11 Event-Loop | bestätigt — `async def` + blankes `await`, kein `to_thread` |
| C-13 Subtrack-Raster | bestätigt (Agentenlektüre, nicht erneut gemessen) |
| C-14 tote Methode | bestätigt — nur die Definition, 0 Produktions-Aufrufer |
| C-15 venv | bestätigt — gemessen |
| C-18 Security-Grenze | bestätigt — globaler `TestClient.request`-Patch |
| **C-12 Dedup** | **abgeschwächt** — der Code dokumentiert den Trade-off selbst: „fuer Overlap-Jitter-Dedup gewollt … bei Problemen gegen `current_group[0]` vergleichen". Faktisch korrekt, aber bewusster Kompromiss, kein Versehen. |
| **C-16 basetemp** | **Ursache falsch** — siehe unten |
| **C-17 GPU-Fake** | **falsch auf dieser Maschine** — siehe unten |

### C-17 — falsch, der `try`-Block wurde übersehen

Die Fixture heißt `directml_adapter_contract_for_hardwareless_tests`; der Fake-Adapter
steht in einem `except DirectMLAdapterError`-Zweig. Auf dieser Maschine löst der echte
Adapter auf:

```
select_directml_adapter() ERFOLGREICH:
  name = AMD Radeon RX 7800 XT
  luid = 0x00000000_0x00010c23
  vram = 15.8 GB
=> der except-Zweig wird NICHT betreten, der Fake greift NICHT
```

**Die Tests laufen hier gegen die echte Karte.** C-17 gilt nur für Runner ohne AMD-GPU.
Nebenbefund: die LUID ist `0x00000000_0x00010c23`; CLAUDE.md führt mehrfach den
veralteten Wert `0x00000000_0x0001185b`.

### C-10 — Nuance

Der Code trägt den Kommentar „Fast forward sequentially instead of using
`CAP_PROP_POS_FRAMES`". Die Sequenzialität ist eine **bewusste** Änderung aus
`patch.py`, kein Versehen — der Laufzeitpreis wurde offenbar nicht gemessen.

### C-02 — bestätigt, breiter als berichtet, GEFIXT
Unabhängig verifiziert: `_decomp` gelesen, Aufrufstelle bestätigt, echte DB read-only
abgefragt (alle 5 Zeilen `type=dict, len=8`), Funktion gegen eine echte Zeile
ausgeführt → `[]`, `VERLUST: True`.

**Zusätzlich gefunden, im Audit nicht enthalten:** es gibt eine *zweite* Quelle
desselben HTTP 500. `media_json_schema.py:102` setzt
`blob.setdefault("spectral_data", {})` — und `{}` bricht `Optional[SpectralData]`
genauso wie `[]`, weil `SpectralData.clip_id` ein Pflichtfeld ist:

```
spectral_data=None  -> OK
spectral_data={}    -> FEHLER: spectral_data.clip_id
spectral_data=[]    -> FEHLER: Input should be a valid dictionary
```

**Umgesetzt.** `_decomp` ist jetzt typerhaltend und normalisiert leere Container auf
einen feldrichtigen Leerwert (`[]` für Listenfelder, `None` für Objektfelder);
unlesbare Blobs werden geloggt statt still verworfen. Regressionstest
`Tests/test_app_state_ai_data_compression.py` — **vor** dem Fix 3 rot (Datenverlust,
None→[], stilles Schlucken), **nach** dem Fix 6/6 grün. Nachbarschaft 57/57 grün.
End-to-End gegen das echte Schema geprüft: echte DB-Zeile → `SpectralData`, beide
Leerfälle → `None`.

### C-16 — Fakten stimmen, **Ursachenanalyse war falsch**
Verifiziert: `--basetemp=.pytest_tmp2` ist relativ und geteilt, `conftest.py` setzt
`AppState` tatsächlich nicht zurück, `shutil.rmtree` steht an 8 Produktionsstellen.

**Aber die Ursachenkette stimmt nicht.** Zwei eigene Messungen:
1. Die fünf angeblich betroffenen Tests laufen allein: **6 passed in 28,64 s**.
2. pytest **löscht ein vorhandenes `--basetemp` beim Sessionstart komplett** —
   Markerdatei hineingelegt, pytest gestartet, Marker weg.

Die weit näherliegende Erklärung ist das Audit selbst: während des 36-Minuten-Laufs
liefen sieben weitere Agenten mit pytest, alle mit dem geteilten `basetemp` aus
`pytest.ini`. **Die Zahl „10 failed / 2 errors" ist mit hoher Wahrscheinlichkeit ein
Messartefakt meines eigenen Vorgehens.** Der Agent hatte seine Erklärung selbst als
unbewiesene Hypothese gekennzeichnet; die Verdichtung in der Empfehlung hat daraus
eine Tatsache gemacht. Das war mein Fehler, nicht seiner.

### C-16 — der naheliegende Fix ist FALSCH
Ich habe `--basetemp` aus `pytest.ini` entfernt. **Danach lief kein einziger Test mehr:**

```
PermissionError: [WinError 5] Zugriff verweigert:
  ...\Temp\pytest-of-david\pytest-current
```

Ohne explizites `--basetemp` legt pytest einen `pytest-current`-**Symlink** an; das
verlangt unter Windows Entwicklermodus oder Adminrechte. **Die Option steht genau
deshalb dort.** Zurückgenommen. Stattdessen ist die Einschränkung jetzt in `pytest.ini`
dokumentiert: wer parallel testet, muss ein eigenes `--basetemp` übergeben.

**Konsequenz für die Priorisierung:** C-16 ist kein Blocker und keine Vorbedingung.
Ein sequenzieller Lauf war immer sauber. Die einzige belastbare Stufe-0-Maßnahme
war C-02 — und die ist umgesetzt.

---

## 1. Bilanz

| Schwere | Anzahl |
|---|---|
| CRITICAL | 18 |
| HIGH | 61 |
| MEDIUM | 74 |
| LOW | ~90 |
| **Summe** | **~243** |

**Toter Code:** ≈5.480 LOC ≈ **10 % der Python-Codebasis**. Davon 3.843 in `ui_legacy_archived/`.
**Repo-Ballast:** ~300 MB getrackte Fremdkörper.

### Testlage — sauberer Lauf, nichts parallel (27:08 min)

```
7 failed · 1497 passed · 13 skipped · 0 errors
```

**Der erste Lauf war kontaminiert** (10 failed / 1492 passed / 2 errors, 36:26 min):
während der 36 Minuten liefen sieben weitere Audit-Agenten mit pytest, alle mit dem
geteilten `--basetemp` aus `pytest.ini`. Die Differenz geht exakt auf:
2 errors + 3 failures verschwunden = 5, und 1492 + 5 = 1497 — genau die fünf Tests,
die als basetemp-Kollision identifiziert wurden. Quantitativ belegt, siehe §0b.

Die verbliebenen **7 Fehler sind alle echt und zuordenbar**:

| Test | Ursache |
|---|---|
| `test_openapi_snapshot_drift` | C-04 — `rejected_clips` fehlt im Snapshot |
| `test_viewmodel_binding_wiring` | C-04 — drei ungebundene ObservableProperties |
| `test_video_pipeline_truth` ×3 | `FakeCapture` ohne `.grab()` nach Router-Umbau |
| `test_audit_sdd_gate` | SDD-Marker nicht aktuell für HEAD (bekannt) |
| `test_t357_gpu_wpf_nullability` | fehlender LHM-Backup-Ordner (Umgebung) |

**Fünf der sieben stammen aus dem uncommitteten `patch.py`-Stand.** Nimmt man den
zurück, bleiben zwei.

Der Referenzwert aus dem Vault (1291 bzw. 1494/13/2) **stimmt nicht mehr**.
Native C#: **57/57**. WPF Release: **0 Warnungen / 0 Fehler**.

---

## 2. Der Kernbefund

**Die Ketten brechen fast ausschließlich an der Übergabestelle zwischen zwei Domänen, praktisch nie innerhalb einer.**

Jede Domäne für sich ist überwiegend solide gebaut. Die Beta-Bernoulli-Mathematik stimmt. Der SGD-Gradient im Projector ist korrekt. Die FAISS-Persistenz ist eine saubere 3-Datei-Generation mit Journal. Die Owner-Capability ist kryptografisch einwandfrei. Die Post-Render-Validierung ist streng und ehrlich.

Und trotzdem:

| Producer | Consumer | Bruch |
|---|---|---|
| `beat_detector.get_downbeats(path)` | `audio_router.py:2255` ruft ohne Argument | `TypeError`, verschluckt |
| Router schreibt `"available"` | `pacing_service.py:389` prüft `"measured"` | Vokabular |
| SigLIP schreibt Vektor in FAISS + Brain-Cache | `clip_selector.py:591` liest `af["audio_embedding"]` | Schlüssel existiert nicht |
| `video_router` schreibt `result["motion"]["motion_category"]` | `pacing_router.py:984` liest Top-Level | immer `"medium"` |
| `pacing_schemas` definiert `rejected_clips` | C#-Record kennt es nicht, Reflection liefert `null` | 3 Ebenen |
| Backend liefert `archived_observations` | `ApiClient.cs:1516` verwirft es | UI zeigt es nie |
| `embedding_cache.store()` läuft bei jedem Import | `enforce_size_limit()` hat 0 Aufrufer | wächst unbegrenzt |
| `VectorOperationOutbox` tombstoned direkt | Kompaktierung sitzt in `mark_tombstoned` (0 Aufrufer) | Index nie bereinigt |

**Die Tests sind fast durchgehend domänenintern** — und decken damit genau die Stellen nicht ab, an denen es bricht.

---

## 3. CRITICAL (18)

### C-01 · Downbeat-Erkennung permanent tot — dreifach gebrochen

`backend/routers/audio_router.py:2255`

```python
downbeat_times = detector.get_downbeats()                       # ohne Argument
def get_downbeats(self, audio_path: str | Path) -> List[float]  # beat_detector.py:306
```

Live reproduziert: `TypeError: ... missing 1 required positional argument: 'audio_path'`.
`BEATNET_AVAILABLE` ist auf dieser Maschine **True** — madmom 0.16.1 installiert, Downbeats wären verfügbar.
`git diff` zeigt die Zeile als `+`: **im uncommitteten Stand neu hinzugefügt und von Anfang an tot.**

Drei unabhängige Brüche in derselben Kette:

1. Falscher Aufruf → `TypeError`, gefangen von `except Exception` (`:2277`)
2. Router schreibt `status: "available"`, `pacing_service.py:389` prüft auf `"measured"`
3. `beats` wird nach dem Anhängen der Downbeats nie sortiert (grep `beats.sort`: 0 Treffer), `beat_count` (`:2591`) zählt doppelt

**Wirkung:** `beat_trigger_mode="downbeat_only"` verwirft ALLE Beats → leere Cut-Liste. Jeder Beat bekommt `base = 0.7` statt `1.0`. `prefer_downbeats` wirkungslos.
**Ein Fix an nur einer Stelle macht es schlimmer**, nicht besser.

### C-02 · zlib-Diff zerstört `spectral_data` — zwei Fehlerwirkungen, unabhängig gefunden

`backend/app_state.py:1385-1396` (uncommittet)

```python
def _decomp(val):
    if not val: return []
    if isinstance(val, list): return val
    if isinstance(val, str): ...
    return []          # dict landet HIER
```

| Eingabe | Wirkung |
|---|---|
| `None` | → `[]` → Pydantic `ValidationError` → **HTTP 500** bei `/audio/analyze` |
| `dict` | → `[]` → **stiller Datenverlust** |

Gegen die Live-DB reproduziert: alle **5 vorhandenen Clips** mit `spectral_data` haben `type=dict, len=8`. `DATA LOSS: True`.
Folge: Bass-Curve-Injektion tot, Spectral-Stage rechnet jedesmal neu, Brain-Achsen ohne Spektralkontext.
**Fix:** `if isinstance(val, (list, dict)): return val`

### C-03 · `get_variance()` liefert exakt 0.0 für jedes einseitig bewertete Bucket

`src/pb_studio/brain/weight_store.py:249` rechnet `Var(Beta(α,β))` **ohne** den Laplace-Prior, den `_compute_posterior_mean` (`:236`) verwendet.

```
unberührt   (α=0,  β=0): posterior=1.0     variance=0.25
1 Klick     (α=0.5,β=0): posterior=1.0     variance=0.0
12× perfect (α=24, β=0): posterior=0.9615  variance=0.0
```

**Die Learning-Session rankt genau die Kontexte ans Ende, die zu lernen begonnen haben.** Aktives Lernen konvergiert nie.
`brain_router.py:475-480` rechnet für `/brain/stats` die **richtige** Formel. Drei Stellen, zwei Formeln.
Kein Test fängt es: alle 12 Sampler-Tests nutzen `empty_weights`.

### C-04 · `rejected_clips`/`rejection_reasons` — Kette auf drei Ebenen halbfertig

- `backend/schemas/pacing_schemas.py:113-114` definiert die Felder
- `pacing_router.py` **befüllt sie nirgends** (grep: 0 Producer)
- `PBStudio.UI/openapi.snapshot.json`: fehlen
- `ApiClient.cs:1475`: fehlen im Record
- `DirectorViewModel.cs:380/383` liest sie **per Reflection** → `GetProperty()` liefert garantiert `null`

`RejectedClipCount` ist konstant 0, `RejectionSummary` konstant `""`. Die Reflection umgeht exakt die Compilerprüfung, die den Fehler sofort gezeigt hätte.
**Zwei Guard-Tests sind deswegen rot** — beide 2026-08-05 gegen genau dieses Muster gebaut.

### C-05 · Brain-Reranker entscheidet ohne Semantik-Achse

`clip_selector.py:591-592` liest `audio_embedding`/`video_embedding` aus Dicts, die diese Schlüssel nie tragen. Grep über `backend/`+`src/`: **ausschließlich Leser, kein Schreiber.**
`feature_adapter.py:426` → `("unavailable", "audio_and_video_embeddings_missing")` bei **jedem** Kandidaten.
Zusätzlich `pacing_service.py:521`: `selector.brain_context_keys = [""]` — hart auf Level 0, die gesamte Backoff-Hierarchie wirkt nur in der **nachgelagerten** Annotation.
**Folge:** Timeline und Brain-Feedback zeigen Semantik-Scores für eine Auswahl, die ohne Semantik getroffen wurde. Das vergiftet spätere Lernrunden.

### C-06 · Latenter Selbst-Deadlock auf `gpu_inference_lock`

`src/pb_studio/core/gpu_lock.py:13` ist `threading.Lock()` — nicht reentrant.
`smart_director.py:883/916/1467/1526` hält ihn und ruft darin SigLIP-Methoden, die denselben Lock erneut nehmen (`siglip_wrapper.py:217/277`).
Feuert heute nur nicht, weil `models/siglip_text.onnx` **fehlt** und `encode_text` bei `:265` vorher zurückkehrt.
Dieselbe Falle ist für CLAP in `smart_director.py:555-557` erkannt und korrekt vermieden — für SigLIP nicht angewandt.
**Sobald das Asset bereitsteht, hängt die Cut-List-Generierung.**

### C-07 · Pacing erreicht DirectML ohne jede VRAM-Buchführung

`pacing_router.py` enthält **null** `with_gpu_task`. Zwei belegte Ketten laufen trotzdem in ONNX-Inferenz:

- `pacing_service.py:105` → `smart_director.classify_audio` → `clap_wrapper.py:250` `session.run`
- `clip_selector.py:1297` → `smart_director.encode_text` → `siglip_wrapper.py:277`

Serialisiert ja (über `gpu_inference_lock`), aber **keine Reservierung, keine Eviction, keine Telemetrie.**

### C-08 · Die VRAM-Reserve/Commit/Release-Logik ist in Produktion schlafend

Genau **drei** produktive `with_gpu_task`-Aufrufe:

- `video_router.py:1147` — `manage_vram=False`
- `audio_router.py:1680` — `manage_vram=False`
- `video_router.py:2492` — VRAM aktiv, aber **unerreichbar** (`moondream_decoder.onnx` fehlt)

Der gesamte Reservierungscode inkl. Retry, Sensor-Abgleich und Eviction läuft im heutigen Betrieb **nie**.

### C-09 · Jeder Clip wird in voller Quelllänge transkodiert

`render_service.py:681-705` — `_transcode_clip` hat **kein `-ss` und kein `-t`**. Der Schnitt passiert erst im Concat-Demuxer.
`_check_needs_normalization` liefert für praktisch jedes reale Video `True` (jeder Audio-Stream erzwingt es, `:592`).
**60 Cuts über 15 Quelldateien à 5 min, Ziel 3 min → ~75 min Encodier-Material, ~6,7 GB Temp, zwei verlustbehaftete Encodes pro Frame.**

### C-10 · Frame-Sampling dekodiert das gesamte Video sequenziell

`video_router.py:1716-1725` springt nur rückwärts mit `CAP_PROP_POS_FRAMES`; vorwärts Frame für Frame `cap.grab()`.
Bei `MAX_MOTION_SAMPLES = 120` über die volle Länge: **jedes einzelne Frame wird dekodiert.** 5 min @ 30 fps = 9000 `grab()` für 120 verwertete Frames.
Dasselbe Muster in `_run_color_and_caption_analysis:2307` und `visual_curves.py:65`.
**Wahrscheinlich der dominante Zeitanteil der Analyse — nicht die GPU.** (Größenordnung geschätzt, nicht gemessen.)

### C-11 · Event-Loop-Blockade in der Farb-/Caption-Analyse

`video_router.py:2267`, aufgerufen mit direktem `await` bei `:1174`. Eine `async def`-Funktion dekodiert Video und rechnet KMeans **direkt auf dem Event-Loop**. Kein `to_thread`.
**Folge:** Der gesamte Loop steht. `/health` antwortet nicht, SSE-Keepalives (15 s) laufen aus, der Client geht in Reconnect-Backoff.
**Sichtbar als „Backend nicht erreichbar" mitten in der laufenden Analyse.**
⚠️ Liegt in der für OBJ-76 reservierten Zone — Änderung nur mit Freigabe.

### C-12 · `_BeatAccumulator.get_deduplicated` vernichtet dichte Trigger

`streaming_analyzer.py:114` vergleicht gegen `current_group[-1]` statt gegen den Gruppenanfang → eine Kette von Events mit je ≤150 ms Abstand kollabiert auf **einen** Mittelwert.

```
16tel-HiHats @128 BPM:  34 Events → 1 Wert
8tel @140 BPM:          20 Events → 20 Werte  (korrekt)
```

Betrifft `onset_acc`, `kick_acc`, `snare_acc`, `hihat_acc`. **Für jeden Techno-/House-Mix ab 128 BPM haben die HiHat- und Onset-Regler nichts zu gewichten.**
Der Nicht-Streaming-Pfad dedupliziert gar nicht → zwei Datensemantiken je nach Dateilänge.
**Ein Test zementiert den Bug:** `Tests/test_streaming_analyzer.py:202-223` prüft den verketteten Mittelwert und würde bei einem Fix rot.

### C-13 · Sub-Track-Erkennung von synthetischem 120-s-Raster verzerrt

`subtrack_detector.py:175-178` + `:291`: `_bounded_chunk_features` legt pro 120-s-Chunk **einen** Tempowert ab und broadcastet ihn. `s3[1:] = abs(diff(tempo))` ist überall null außer an den Chunk-Grenzen. Nach `_normalize` sind diese Spikes 1.0, Gewicht `W_TEMPO = 0.20`.
**Jeder lange Mix bekommt einen 20 %-gewichteten Grenzhinweis bei 120 s, 240 s, 360 s — unabhängig von der Musik.** Das ist der einzige Pfad, den DJ-Mixe nehmen.

### C-14 · `AppState.update_video_analysis` — 177 Zeilen ohne Produktions-Aufrufer

```
grep -rn "update_video_analysis" --include=*.py .
  backend/app_state.py:1109  (Definition)
  Tests/test_app_state_truth_source.py:121
  Tests/test_video_embedding_persist.py:36,47,83,85
```

Produktion schreibt direkt über `video_router.py:358`. Die dort gepflegten Invarianten — `has_embedding` aus `embedding_dim`, `video_clips`↔`video_analysis_cache`-Spiegelung — **greifen im Produktionspfad nicht**. Vier Tests melden einen toten Pfad grün.

### C-15 · venv weicht massiv vom Lock ab

| Paket | `requirements.txt` | installiert |
|---|---|---|
| torch | `2.11.0+cpu` | **`2.4.1+cpu`** |
| torchvision | `0.26.0+cpu` | **`0.19.1+cpu`** |
| transformers | `5.5.4` | **`4.49.0`** |
| huggingface-hub | `1.5.0` | **`0.36.2`** |
| starlette | `1.3.1` | **`1.0.0`** |
| setuptools | `81.0.0` | **`82.0.1`** (höher als Pin) |

Die Umgebung wurde **nie** mit `pip install --require-hashes -r requirements.txt` erzeugt.
**CLAUDE.md §5 „LOCKED VERSIONS: PyTorch (CPU) 2.11.0+cpu" ist falsch.**
Ein Clean-Install erzeugt eine **andere** Umgebung als die, in der die Suite grün gemeldet wurde.
Zusätzlich: `torch-directml 0.2.5.dev240914` installiert, in **keiner** Requirements-Datei.

### C-16 · Die Testsuite zerstört ihr eigenes Temp-Verzeichnis

`pytest.ini` setzt `--basetemp=.pytest_tmp2` — ein **relativer, geteilter, repo-lokaler** Pfad.
**5 von 12 Fehlern** haben diese eine Ursache: `FileNotFoundError` beim Schreiben in ein frisch angelegtes `tmp_path`. Alle fünf laufen isoliert grün.
`Tests/conftest.py:82` setzt `AppState` **nicht** zurück; Produktionscode löscht Bäume an 7 Stellen (`project_router.py:151`, `recovery_generation.py:952`).
**Verursacher nicht abschließend identifiziert.** Solange das gilt, ist jede Zahl aus der Suite — grün wie rot — nur bedingt belastbar.

### C-17 · Die Suite beweist nichts über die GPU

`Tests/conftest.py:25-53` injiziert per autouse-Fixture einen **erfundenen** DirectML-Adapter (`luid="0x00000000_0x00000001"`, „AMD DirectML Test Adapter", 8 GB).
Der einzige echte Hardware-Kontrakt (`test_t357_gpu_wpf_nullability_contracts.py:261`) ist hinter `PBSTUDIO_RUN_T357_HARDWARE=1` geskippt.
**IRON RULE 1 ist testseitig unbelegt.** Eine grüne Suite auf einer NVIDIA-Maschine ohne AMD-GPU wäre genauso grün.

### C-18 · Die Default-Deny-Sicherheitsgrenze ist für ~99,6 % der Suite abgeschaltet

`Tests/conftest.py:56-79` monkeypatcht **`TestClient.request` global** und injiziert in jeden Request die Owner-Capability.
Nur `Tests/test_owner_capability_global.py` (6 Tests) nimmt sich aus.
**Ein Regress, der eine Route versehentlich öffentlich macht, wird von 1500 Tests nicht bemerkt.**

---

## 4. Ausgewählte HIGH (61 gesamt)

### Sicherheit

- **Beliebiger Dateischreibzugriff vor jeder Authentifizierung.** `recovery_bootstrap.py:174-179`: für `restore_policy == "replace"` (Default) fehlt die Owner-Scope-Bindung, die für `delete_if_present` streng erzwungen wird. Erreichbar über `main.py:32` — Modulebene, vor Config, Logging, App und Middleware. Kein Privilegien-Übergang, aber ein **Persistenz-Primitiv**: ein Prozess mit Schreibrecht im Profil kann PB Studio dazu bringen, beim nächsten Start eine beliebige Datei an beliebiger Stelle abzulegen. Testlücke: es gibt Tests für Delete-Scope-Escape, aber **keinen** für `replace`.

### Datenverlust ohne Signal

- **Timeline ist bis zum manuellen Save flüchtig.** `close_project` speichert nicht, `_activate_project` auch nicht, Pacing schreibt nur nach RAM. Save-on-Exit existiert, Save-on-Switch nicht. **Wer nach einem Pacing-Lauf das Projekt wechselt, verliert die Timeline ersatzlos.**
- **Parallel-Save-Race.** `project_router.py:700` nutzt **feste** Stage-Dateinamen. A's `finally`-unlink löscht B's Stage, B wirft, B's Rollback überschreibt A's committeten Save. Fix-Vorlage steht 200 Zeilen tiefer: `set_anchors` nutzt `uuid4()`. `ProjectService.SaveProjectAsync` läuft als einzige Projektoperation **ohne** `_projectTransitionGate`.
- **`GET /project/anchors` liefert 200 + leere Liste bei defekter Datei.** UI kann „kaputt" nicht von „keine Anker" unterscheiden → Nutzer setzt neue → `POST` überschreibt via `os.replace` → **Datenverlust ohne Signal**.
- **`_brain_singleton.py:79-81`** verschluckt `unbind_project_state()`. `state_conn` bleibt an die state.db des **geschlossenen** Projekts gebunden → `/brain/feedback` schreibt Lerndaten ins falsche Projekt. HTTP 200 auf `/project/close`.
- **`vector_store.py:184-196` + `:817-828`** verschlucken den letzten FAISS-Persistenzpunkt. Alle seit dem letzten Write hinzugefügten Embeddings gehen verloren: ohne Log, ohne Exit-Code, ohne UI-Signal.

### Unbegrenztes Wachstum

- **`embedding_cache.py:180` `enforce_size_limit()` hat 0 Aufrufer.** Der Produzent läuft bei jedem Import.
- **FAISS-Kompaktierung unerreichbar.** `mark_tombstoned` / `clean_tombstones`: 0 Produktions-Aufrufer. Der Docstring behauptet Aufrufer — falsch, die Outbox schreibt direkt in `_tombstoned_ids`. **Der Index wird nie physisch bereinigt.**
- **Recovery-Generationen ohne Aufräumpfad.** `request_restore_generation`, `plan_protected_retention`, `apply_protected_retention`: je 0 Aufrufer. Der Restore-Zweig läuft bei jedem Start, aber es gibt **keinen Weg, einen Restore anzufordern**. Jede Generation enthält eine volle Kopie von `pb_studio.db` (31,4 MB).

### Wirkungslose Bedienelemente

Sechs Regler wirken nur über einen Teil ihres Wegs:

| Regler | Toter Bereich | Ursache |
|---|---|---|
| `BeatWeight` 0–2 | Downbeats ab **1.0** | `PacingCut.__post_init__` clamped |
| `KickWeight` 0–2 | ab **1.11** (~45 %) | ×0.9 vor Clamp |
| `SnareWeight` 0–2 | ab **1.18** (~41 %) | ×0.85 |
| `MinCutInterval` 0.1–5.0 | **untere Hälfte** | `min_clip_length` erneut angewandt |
| `MaxCutInterval` 1–30 | **8–30** | `min(max_clip_length, …)` |
| `trigger_settings.min_cut_interval` | **komplett** | 0 Engine-Leser |

- **`enable_motion_matching()` ist ein No-Op mit Aufrufer.** Setzt `_use_motion_matching` — grep findet genau 1 Treffer, die Zuweisung selbst. `pacing_service.py:1264` ruft es produktiv auf und erzeugt nur den Logeintrag „Motion-Matching: aktiviert".
- **`beat_trigger_mode="strong_only"` degeneriert** ohne Beat-Stärken exakt zu `downbeat_only`. Zwei ComboBox-Einträge, dieselbe Cut-Liste.
- **`IsLoading` in 4 ViewModels deklariert, in 0 von 19 XAML gebunden** (+ `ProjectOverview.IsBusy`).
- **`include_audio=false` ist über die UI nicht auslösbar** — Backend vollständig implementiert und getestet, C#-Record hat das Feld, aber kein XAML-Element setzt es.

### Fake-Erfolg

- **Jede Exception im Pacing degradiert stumm auf ein Zeitraster.** Vier Pfade fangen `Exception` → `_generate_time_grid_fallback` (ignoriert Beats, Trigger, Struktur, Anker). Der Router meldet `cut_count=N`, die UI zeigt „N Cuts generiert". **Erfolgsmeldung für eine Timeline ohne jeden Musikbezug.**
- **Waveform: Fehler wird als leerer Erfolg ausgeliefert.** `audio_router.py:2650` gibt `[]` zurück → HTTP 200 mit leeren `bands`. Der 500er-Zweig des Endpunkts ist unerreichbar.
- **Samplerate-Fallback wird persistiert.** `audio_router.py:1881/1885` fällt still auf `44100`/`2` zurück und **schreibt das als Clip-Metadatum**. Eine 48-kHz-Datei wird dauerhaft als 44,1 kHz geführt — falsche Zeitbasis in allen Beat-Berechnungen.

### Modellauswahl

- **`config.json` `task_overrides` zeigt für alle sechs Tasks auf `qwen2.5-vl-7b-instruct`** — inkl. `chat`, `chat_tool_use`, `brain_explanation`. Chat und Tool-Use laufen auf einem 7B-**Vision**-Modell, die gepflegten `task_preferences` sind Laufzeit-Totdaten.
  **Ursache ist ein UI-Defekt:** `models_router.py:935` schreibt bei `activate_model` ohne `task` das Modell in *jeden* capability-passenden Task; `ModelManagerViewModel.cs:301` ruft genau so auf. **Ein Klick auf „Aktivieren" biegt still Chat, Tool-Use und HIRN um.**
- **`/models/available` liefert strukturell immer eine leere Liste.** `refresh(downloadable_candidates=…)` hat 0 Produktions-Aufrufer.
- **Brain-Narrator hat 30 s Timeout**, der Vision-Wrapper für dasselbe Problem 165 s. Der Fix von 2026-08-07 wurde nur auf einen der beiden Pfade angewandt.
- **Der dokumentierte 3-Stufen-Fallback läuft nicht.** `select_best_for_task` hat genau einen Nicht-Test-Aufrufer, und der liegt im als Test-Hook markierten Zweig. 11 öffentliche Funktionen dadurch tot.

### Sicherungen, die nie greifen

| Ort | Was es tut | Aufrufer |
|---|---|---|
| `recovery_barrier.py:89` | erzwingt Snapshot-Lease, wirft `RecoveryBusyError` | **nur Test** |
| `cross_modal_projector.py:639` | atomarer V1-Rollback, 22 Zeilen | **nur Test** |
| `lmstudio_vision_wrapper.py:92` `_ist_warm` | Docstring: „used by concurrent analysis workers" | **nur Test** — Produktion nutzt `_ist_warm_unlocked` |

### Frontend/Backend-Vertrag

- **`/health/vram` schneidet 4 Felder still ab.** `get_stats()` liefert 11 Keys, `VramBudgetStats` deklariert 8 → `adapter_index/luid/name`, `physical_vram_mb` werden von FastAPI **ohne Log** verworfen. Genau die Felder, die belegen, auf welcher Karte das Budget gilt.
- **Doppelte Vertragsschicht (T4.5).** 87 NSwag-Typen / 4733 LOC generiert, **14 genutzt**, daneben 34 Handrecords. `CutListResponse` existiert doppelt, die generierte (korrekte) Variante ist tot. **Das ist die Ursache beider Feldverluste** — T4.5 ist kein Architekturgeschmack mehr.
- **`BeatMarkerViewModel.cs:38`** leitet Taktnummern aus `Index` ab, obwohl Downbeats unsortiert ans Listenende gehängt werden. Erster Downbeat bekommt Index ~360 → Label „91", viermal wiederholt. Kehrt einen dokumentierten Entscheid („keine synthetische Taktnummer") ohne Begründung um.

### Betrieb

- **LHM-Env-Vars fehlen in 8 Skripten.** `runtime_contract.bat` setzt `PBSTUDIO_LHM_MANIFEST_SHA256`/`PBSTUDIO_LHM_SHA256` nicht — nur `runtime_contract.ps1 -ApplyEnvironment` tut das. `run_quick_tests.bat`, `run_audit_tests.bat`, `AUDIT_FIX_VERIFY.bat`, `coverage_run_v2.bat`, `_cowork_run.bat`, `run_long_stress.bat` und beide Stress-Skripte starten Python direkt → **GPU-Telemetrie in all diesen Läufen tot.**
- **GUI-Testzweig tot.** `run_full_test.ps1:44` startet `run_ui.py` — existiert nicht. `test.bat` ruft ohne `-NoGui` auf → 30 s Timeout → `[FAIL]`.
- **`launch.ps1` u. a.: UTF-8 ohne BOM** mit 18 Umlaut-Zeilen → Mojibake unter PS 5.1.
- **`_extract_waveform` hasht die gesamte Datei bei jedem Lesezugriff.** Bei 2-h-WAV drei komplette Dateilesungen für 24 KB Nutzlast.
- **Nach Stem-Separation bleiben BPM/Key/Beats stale.** Beat-Tracking nutzt den Drums-Stem, Key-Detection den Instrumental-Stem — aber nur die Subtrack-Detection wird neu gerechnet. Auch ein erneutes `/audio/analyze` ohne `force` rechnet nicht neu.
- **Projektwechsel-Leck in der UI.** Die drei State-Services sind `AddSingleton`, ihre `Clear()`-Aufrufer ausschließlich **transiente** ViewModels. Wer in Projekt A nur den HIRN-Tab benutzt und dann wechselt, liest in `BrainViewModel.cs:274` die Timeline aus Projekt A.

---

## 5. Toter, doppelter und überflüssiger Code

### Vollständig tote Module (≈1.430 LOC allein in Video)

`ai/moondream_pytorch.py` (420, zudem CPU-PyTorch = IRON-RULE-1-Widerspruch) · `ai/video_specialist.py` (588) · `ai/clap_pytorch.py` (306, **während ein Test seine Nichtbenutzung erzwingt**) · `video/visual_curves.py` (107) · `video/auto_tagger.py` (92) · `video/thumbnail_generator.py` (93) · `video/ollama_vision_wrapper.py` (47) · `services/audio_service.py` (74) · `audio/stem_runner.py` (56) · `utils/profiling.py` (34) · `core/compression.py` (20) · `storage/embedding_repository.py` (429) · `core/vram_arbiter.py` (264) · `models/timeline.py` (Duplikat)

### `ui_legacy_archived/` — 18 Dateien, 3.843 LOC

0 Importe. PyQt6 gar nicht installiert. **12 interne Imports gebrochen** (zeigen auf `pb_studio.ui.widgets.*`, existiert nicht). Der Baum wäre nicht einmal lauffähig.

### ~700 LOC toter Pacing-Code

`advanced_pacing_engine.py:129-774` (`SyncMode`, `plan_cuts`, vier `_plan_*_sync`) — erreichbar nur über `smart_director` → `generation_service` → `ui_legacy_archived/main_window.py`.
`clip_selector.py:1382-1566` — 9 Methoden auf `clip_cache`, das produktiv nie befüllt wird → geben immer `[]` zurück.

### Divergierende Duplikate

**Onset-/Drum-Trigger dreifach implementiert**, mit abweichenden Parametern:

| Parameter | `audio_router.py:2337` (Cache) | `engine:1863` (Stem) | `engine:2077` (Fallback) |
|---|---|---|---|
| `preemphasis` | ja | **nein** | ja |
| `n_mels` | **adaptiv** (≥4) | **128** | **64** |
| `n_fft` | **adaptiv** | 2048 | 2048 |
| `delta` | **nicht gesetzt** | gesetzt | gesetzt |
| `backtrack` | nein | **True** | nein |

Cache-Pfad und Live-Fallback arbeiten **beide auf dem Vollmix** und liefern trotzdem unterschiedliche Trigger-Zeitpunkte.
**CLAUDE.md behauptet „gleiche librosa-Parameter wie der Live-Fallback" — nach Code-Lage nicht zutreffend.**
(Parameterdivergenz belegt; Abweichungsgröße **nicht gemessen**.)

Weitere: SHA-256-Dateihash **6×** implementiert (3 zeichengleich, 1 in UPPER); Migrations-Parsing **verbatim** in 2 Modulen inkl. desselben Fix-Kommentars; `_atomic_write` 3×.

### Repo-Ballast (~300 MB)

`tools/ffmpeg/bin/ffplay.exe` — **82,6 MB, null Referenzen** · `tools/ffmpeg/doc/` 34 HTML-Dateien (~9 MB) · Evidence-Blobs ~33 MB inkl. einer 14,4-MB-`.tar.zst` · `Tests/__init__.py.bak` · `LM-Studio-Log_terminal.txt` (316 KB) · `scratch/` mit 17 Wegwerf-Skripten (nicht ignoriert)
`.gitignore` listet `*.exe` und `/tools/*` — greift nicht, weil bereits getrackt. Dazu ~190 redundante `.pytest_tmp2/…`-Einträge.

### Tote Konfiguration

`app_name`, `version`, `ui`, `hardware.gpu_backend` (rein dekorativ — die DirectML-Wahl läuft über `directml_adapter_policy`).
Env-Vars ohne Leser: `PBSTUDIO_USE_ROUTER_FINALIZER`, `PBSTUDIO_LMSTUDIO_URL`, `PBSTUDIO_OLLAMA_URL`; `PBSTUDIO_BACKEND_URL` ohne Producer.

### Ein kaputter Import im Produktivcode

`video/audio_key_detector.py:46` importiert `pb_studio.config` — heißt `config_manager`. Von `except Exception` verschluckt. Ein funktionierender Fallback greift, **aber die geschriebene Absicht wird nie ausgeführt.**

---

## 6. Was nachweislich gut ist

Das gehört genauso in einen ehrlichen Bericht.

- **IRON RULES: 0 Verstöße im Code.** Alle 4 ONNX-Session-Erzeugungen setzen beide Flags, zentral über `directml_adapter.py:428-429`. `enforce_directml_session()` liest sie **an der realisierten Session zurück** und wirft bei Abweichung — echter Schutz, kein Docstring-Versprechen. Kein CUDA/ROCm/pynvml/NVENC. Nur `h264_amf`/`hevc_amf`/`av1_amf`, dreifach verriegelt plus Pre-commit-Hook.
- **Sicherheit:** null `shell=True`, null SQL-Injektion, null unsichere Deserialisierung, null hartkodierte Secrets, null Wildcard-CORS. Alle 66 Routen enumeriert — genau zwei ungeschützt, beide bewusst. Owner-Capability: 32 Byte CSPRNG, Übergabe per Environment (nicht Kommandozeile), `os.environ.pop()` beidseitig, `hmac.compare_digest`, `AllowAutoRedirect=false` überall, Loopback-Pinning. Der Concat-Escape für FFmpeg ist die **korrekte** `av_get_token`-Form.
- **Pfad-Sicherheit** zentral in `media_path_policy.py`: NUL, UNC, `\\?\`, `://`, ADS-Doppelpunkte, gemappte Netzlaufwerke, **Reparse-Points pro Pfadkomponente** — und beidseitig in C# gespiegelt. Kein Traversal gefunden.
- **Der Legacy-Pickle-Pfad ist vorbildlich abgesichert:** `_RestrictedMetadataUnpickler` lehnt jedes `GLOBAL`-Opcode ab, Struktur wird nachvalidiert, ein `__reduce__`-Angreifer-Test beweist es.
- **Datenintegrität live gemessen sauber:** FAISS `ntotal=500` = `meta=500` = `vector_map=500`, **0 Orphans in beide Richtungen**, `quick_check: ok`, Outbox 500/500 completed. Für alle 5 Projekte stimmen DB-Blob und `project.json` **exakt** überein.
- **FAISS-Persistenz:** 3-Datei-Generation mit `.bak`, Journal und `_recover_incomplete_snapshot`. Das sauberste Stück Code im gesamten Audit.
- **Post-Render-Validierung:** Codec, Auflösung, Containerdauer ±1 Frame, Framezahl ±1, True-Peak ≤ −1 dBTP, Endstille gegen Quelle. Wenn `render_timeline` zurückkehrt, ist das Artefakt verifiziert.
- **Cancel ist echt**, nicht nur ein Flag: Prozess-Kill an allen 6 Subprozess-Stellen, keine Lücke gefunden.
- **`PythonBridgeService`** nutzt ein Kill-on-Close-JobObject — kein verwaister uvicorn bei WPF-Absturz.
- **Alle 11 SSE-Event-Typen** passieren den Filter und haben einen C#-Handler. Die Regressionen von 2026-07-09 und 2026-08-05 sind repariert und bleiben es.
- **Alle 33 Chat-Tools** registriert, Endpunkte existieren, `destructive`-Klassifikation erzwungen, Confirmation-Broker stream-gebunden mit Einmal-Autorität. Kein totes Tool. Prompt-Injection über den Agenten ist wirksam abgesichert.
- **SigLIP-Dimension 1152 ist sauber.** `_fit_to_size` existiert nicht mehr, Defaults kommen aus den Embedder-Modulen, `_project` lehnt Abweichungen ab statt still zu kürzen. Der Fall von 2026-07-10 kann nicht wiederkehren.
- **Fake-Erfolg im Video-Tagging ist behoben.** `completed` nur bei Tags **und** ohne Timeout; Scene-Detection wirft bei leerem Ergebnis; Null-Norm-Embeddings werfen.
- **0 TODO/FIXME/HACK/XXX** im gesamten Produktionscode. **0 auskommentierte Codeblöcke** (Python und C#, per Dekommentierung + `ast.parse` geprüft).
- **8 echte Wiring-Guards**, zwei davon haben in diesem Lauf tatsächlich Defekte gefunden.
- **Blocking in async:** alle schweren Backend-Pfade laufen über `asyncio.to_thread` — mit der einen Ausnahme C-11.

---

## 7. Empfohlene Reihenfolge

**Stufe 0 — bevor irgendetwas anderes passiert**

1. **C-16**: `--basetemp` aus `pytest.ini` entfernen, `AppState` in der autouse-Fixture zurücksetzen. Solange die Suite ihre eigenen Ergebnisse verunreinigt, ist jede Messung nur bedingt belastbar.
2. **C-02**: `_decomp` reparieren. Ohne das ist ein Commit von `app_state.py` ein Datenverlust-Commit gegen die vorhandene DB.
3. **C-15 entscheiden**: Lock an die Realität anpassen oder Umgebung neu bauen. CLAUDE.md §5 korrigieren.

**Stufe 1 — Datenverlust und Sicherheit**

4. Recovery `replace`-Owner-Scope binden (+ Regressionstest)
5. `_brain_singleton` und `vector_store` Fehler sichtbar machen (Cross-Project-Korruption, Embedding-Verlust)
6. Timeline-Save vor Projektwechsel; `uuid4()`-Stage-Namen im Save-Pfad
7. `enforce_size_limit` verdrahten; FAISS-Kompaktierung über `mark_tombstoned` führen

**Stufe 2 — sichtbare Funktionsdefekte**

8. **C-01 als Einheit**: `get_downbeats(path)` + `beats.sort()` + `beat_count` + Vokabular `available`/`measured`
9. **C-03** Varianzformel angleichen — **vorher** einen Regressionstest mit befülltem Store schreiben, der ohne Fix rot ist
10. **C-04** entscheiden: Kette vollständig durchziehen oder ersatzlos zurücknehmen
11. **C-12** Dedup korrigieren — und `test_streaming_analyzer.py:202-223` mit umschreiben, sonst blockt der Test den Fix

**Stufe 3 — Performance**

12. **C-10/C-09**: Frame-Seek statt Voll-Dekodierung; `-ss`/`-t` im Transcode. Größter Hebel im Repo.
13. **C-11**: Farbanalyse in `to_thread` (⚠️ OBJ-76-Zone, Freigabe nötig)

**Stufe 4 — Aufräumen**

14. ~5.480 LOC toter Code, ~300 MB Repo-Ballast, 4 tote Config-Schlüssel
15. `patch.py` löschen (Einweg-Skript, bereits angewandt)
16. T4.5 entscheiden — die doppelte Vertragsschicht hat zwei belegte Defekte produziert

---

## 8. Anmerkung zum uncommitteten Arbeitsstand

**Nicht committfähig.** Übereinstimmendes Urteil von vier unabhängigen Agenten.

Der Diff ist **maschinell erzeugt**: `patch.py` (untracked, Repo-Root) ist ein String-Replace-Skript, dessen Zielstrings byte-identisch mit dem heutigen `git diff` sind. Das erklärt die Schadensklasse:

- `spectral_analyzer.py:158` — **Duplikat-Key `mel_bands` mit 12 statt 16 Spaces Einrückung**. Kein Syntaxfehler (letzter gewinnt), aber `mel_db.tolist()` wird zweimal materialisiert — bei 60-min-Mix ~40 Mio. Floats, für Daten die **niemand liest**.
- `DirectorViewModel.cs:380` — **Reflection statt Typänderung**, umgeht den Compiler.
- Drei neue tote Ketten: `AudioStageDTO`, `provider_/model_/attempt_receipt`, `mel_bands`.
- **Zwei projekteigene Guard-Tests rot** — beide gegen genau dieses Muster gebaut.

Fünf getrennte Baustellen, davon **eine** (FR-362 Degradations-Meldung) sauber, dokumentiert und getestet. Die ließe sich isoliert committen, sobald `rejected_clips` entweder vollständig durchgezogen oder zurückgenommen ist. Baustellen 2–5 sind ungetestet; `config.json` und `global.json` gehören gar nicht in diesen Stand.

---

## 9. Team-Aufstellung

**Team A — Consulting-Team (8 Domänen-Analysten):** Audio · Video/Vision · Pacing/KI-Regie · Brain · GPU/VRAM/DirectML · Render/Export · LLM/Chat/Modelle · Projekt/Persistenz

**Team B — Forensik-Team (7 Querschnitts-Spezialisten, direkt geführt):** WPF-Frontend · Backend-Kern & API-Vertrag · Dead-Code & Duplikate · Test-Qualität · Security & Robustheit · Infrastruktur & Build · `audio_router`-Restaudit (nachbeauftragt)

**Kreuzvalidierung:** Fünf Befunde wurden von zwei oder mehr Agenten unabhängig gefunden (C-02, C-04, C-05, das `patch.py`-Muster, die Guard-Test-Fehlschläge). Ein Widerspruch zwischen zwei Agenten (Downbeat-Reparatur) wurde am Quelltext selbst aufgelöst — der zweite Agent hatte das `try/except` gesehen und daraus fälschlich „repariert" geschlossen.

Mehrere Agenten haben ihre eigenen Werkzeuge korrigiert und das offengelegt: 353 → 8 verwaiste Module, 489 → 21 tote Funktionen, 88 → 12 ungenutzte Imports, 50 → 0 auskommentierte Blöcke.
