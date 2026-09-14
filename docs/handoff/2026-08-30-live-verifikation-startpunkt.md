# Startpunkt Live-Verifikation

**Stand:** 2026-08-30 · **Basis:** `codex/obj76-runtime-truth` @ `b9bae5b`
**Zweck:** In der nächsten Sitzung ohne Anlauf mit der Verifikation beginnen.

Sieben Fixes und zwei Features sind gebaut, getestet und gepusht — aber **nur
an Unit-Tests und synthetischem Material belegt**. Keiner davon wurde am
laufenden Backend mit echten Projektdaten gesehen. Genau das steht an.

---

## 0. Betriebsregeln — vor dem ersten Befehl lesen

Diese vier Punkte sind in dieser Sitzung teuer gelernt worden.

1. **Das Backend niemals hart beenden.** `Stop-Process -Force` ist hier ein
   Datenverlust-Ereignis: es lässt den `RUNTIME_DIRTY`-Marker stehen, und der
   nächste Prozess, der `backend.main` importiert — **auch jeder pytest-Lauf** —
   rollt daraufhin 398 Artefakte zurück, darunter `data/pb_studio.db`,
   349 Brain-Dateien und 30 `project.json`.
2. **Fertigsignal des Shutdowns ist nicht der Port.** Nach `POST /shutdown`
   verstummt `/health` sofort, aber die Abschaltung arbeitet noch **~28 s** am
   Snapshot. Fertig ist es, wenn
   `%LOCALAPPDATA%\PB_Studio\recovery-control\v1\RUNTIME_DIRTY` **verschwunden**
   ist. Darauf warten, nicht auf den Port.
3. **Jeder pytest-Lauf braucht ein eigenes `--basetemp`.** `--basetemp` niemals
   aus `pytest.ini` entfernen — ohne die Option legt pytest einen
   `pytest-current`-Symlink an, der auf dieser Maschine jeden Lauf mit
   `PermissionError [WinError 5]` bricht.
4. **DB-Zählstände vor und nach jedem Lauf prüfen.** Soll: 6 Projekte,
   711 Medien, `integrity_check: ok`. Bei Abweichung sofort stoppen.

---

## 1. Ausgangszustand, gegen den geprüft wird

| | Sollwert |
|---|---|
| Branch / HEAD | `codex/obj76-runtime-truth` @ `b9bae5b`, lokal == remote |
| Arbeitsbaum | sauber; untrackt nur `patch.py`, `function_inventory.json` |
| Vollsuite | **2 failed / 1585 passed / 13 skipped / 0 errors** (~25 min) |
| Die 2 Fehler | `test_audit_sdd_gate` (nach jedem Commit rot), `test_t357::…lhm_backup_restore…` (gitignorierter Ordner, in keinem Clone grün) |
| WPF Release | 0 Warnungen / 0 Fehler |
| Datenbank | 6 Projekte, 711 Medien, `integrity_check: ok` |
| Recovery-Generation | `20260830T173403884243Z-d9e9873b47dd4507b148a5d3b12e14e9`, DIRTY geräumt |
| venv | aus `requirements.txt` neu gebaut: torch 2.11.0+cpu, transformers 5.5.4 |
| `BEATNET_AVAILABLE` | **`False`** — so gewollt, madmom steht nicht im Lock |

Schnellprüfung:

```powershell
cd C:\Users\david\Documents\Pb_studio_AMD_version
git status --short
git rev-parse HEAD; git rev-parse origin/codex/obj76-runtime-truth
$env:PYTHONPATH = (Join-Path (Get-Location) "src")
.\.venv\Scripts\python.exe -c "import sqlite3;c=sqlite3.connect('data/pb_studio.db');print(c.execute('SELECT COUNT(*) FROM projects').fetchone(), c.execute('SELECT COUNT(*) FROM media').fetchone(), c.execute('PRAGMA integrity_check').fetchone())"
```

---

## 2. Backend starten und sauber beenden — der Rahmen für alles Weitere

**Starten** (Owner-Capability selbst setzen, damit sie für die Requests bekannt ist):

```powershell
$cap = [Convert]::ToBase64String((1..32 | ForEach-Object {Get-Random -Max 256}))
$env:PBSTUDIO_OWNER_CAPABILITY = $cap
Start-Process powershell -ArgumentList @("-NoProfile","-File",".\launch.ps1","-BackendOnly","-NoPause") -WindowStyle Hidden
# ~40 s warten (Ollama 15 s + LM Studio 20 s Timeout), dann:
curl.exe -s http://127.0.0.1:8765/health
```

**Sauber beenden:**

```powershell
curl.exe -s -X POST -H "X-PBStudio-Owner-Capability: $cap" http://127.0.0.1:8765/shutdown
# JETZT warten, bis der Marker weg ist (nicht auf den Port!):
while (Test-Path "$env:LOCALAPPDATA\PB_Studio\recovery-control\v1\RUNTIME_DIRTY") { Start-Sleep 2 }
```

---

## 3. Die Verifikationsliste, nach Wert geordnet

### V-1 · Downbeat-Ableitung an echter Musik  ⭐ wichtigster Punkt

**Warum:** Das Verfahren ist nur an synthetischem Material belegt. Es findet die
am stärksten akzentuierte Taktposition — **nicht zwingend den Taktanfang**. Bei
dominanter Snare auf 2 und 4 kann es danebengreifen; der Kontrastvergleich
verweigert dann meist, ausgeschlossen ist eine Fehlzuordnung nicht.

**Vorgehen:** einen echten Track über `/audio/import` + `/audio/analyze` fahren,
dann im Ergebnis prüfen:

- `downbeat_provenance.status` → `"derived"`, `synthetic: true`, `derived_count > 0`
  *(oder* `"unavailable"`*, wenn sich keine Taktposition abhebt — das ist
  ebenfalls ein korrektes Ergebnis, kein Fehlschlag)*
- Abstand aufeinanderfolgender Downbeats ≈ `4 × 60/BPM`
- die markierten `beats` mit `beat_type == "downbeat"` liegen hörbar auf der Eins

**Gegenprobe, die den eigentlichen Wert hat:** `beat_trigger_mode="downbeat_only"`
über `/pacing/generate` — liefert es jetzt eine **nicht leere** Cut-Liste?
Vorher war sie garantiert leer.

Am besten mit zwei Stücken: eines mit klarem Kick auf 1, eines mit dominanter
Snare auf 2 und 4. Das zweite ist der ehrliche Härtefall.

### V-2 · FR-362-Degrade am laufenden Backend

Videoclips ohne Tonspur auswählen, `use_key_matching` aktivieren,
`/pacing/generate` fahren. Erwartet: HTTP 200, `degradations` enthält
`key_matching`, und die Statuszeile der KI-Regie zeigt
„ohne Wirkung: Tonart-Matching (0/N Clips bewertbar)". Vorher blockierte
derselbe Fall mit 422.

### V-3 · `audio_key`: Kein-Ton ≠ Detektorfehler

`/video/analyze` auf einen Clip **ohne** Tonspur: `stage_status.audio_key ==
"unavailable"` und **kein** Eintrag in `stage_errors`. Danach derselbe Clip mit
einem provozierten Detektorfehler: `"failed"` **mit** Eintrag.

### V-4 · Heilung der Phantom-Stage-Schlüssel

Nur relevant, wenn in der DB noch Clips mit vergifteten Schlüsseln liegen:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3,json;c=sqlite3.connect('data/pb_studio.db');
rows=[r for r in c.execute('SELECT id, ai_data FROM media') if r[1]];
bad=[r[0] for r in rows if any(k in str(r[1]) for k in ('motion_embedding','colors_captions','persistence'))];
print('betroffene Clips:', len(bad), bad[:10])"
```

Sind welche dabei: einen davon erneut analysieren und prüfen, dass
`analysis_status` wieder `completed` erreichen kann. Sind keine dabei, ist V-4
gegenstandslos — dann bitte so vermerken statt „verifiziert" zu schreiben.

### V-5 · Die WPF gegen das neue Backend

Die App wurde in dieser Sitzung **nie** gestartet — nur das Backend. Nach dem
venv-Neubau (transformers 4.49 → 5.5.4 ist ein Major-Sprung) gehört ein
vollständiger Start mit allen zwölf Tabs dazu.

### V-6 · Entscheidung über die zwei Dauerroten

Kein Testlauf, eine Entscheidung. `test_audit_sdd_gate` ist nach *jedem* Commit
rot (der Marker pinnt einen SHA), der LHM-Backup-Test kann in **keinem** Clone
grün werden (gitignorierter, nie getrackter Ordner). Solange beide so bleiben,
gewöhnt sich jeder an rote Läufe — das kostet mehr, als die Defekte wert sind,
die sie melden sollen.

---

## 4. Was ausdrücklich **nicht** gilt

Damit niemand auf alten Annahmen aufbaut:

- **BeatNet liefert nichts.** madmom 0.16.1 wirft auf NumPy ≥ 1.24 bei *jeder*
  Datei; librosa ist der reale Beat-Lieferant. `BEATNET_AVAILABLE: False` ist
  der gewollte Zustand, kein Defekt.
- **Die LUID ist keine Geräteidentität.** DXGI vergibt sie pro Boot. Vier
  verschiedene Werte stehen im Repo, alle waren zu ihrer Zeit richtig.
- **`SmartDirector` ist lebendig**, entgegen älteren Notizen — er liefert den
  SigLIP-Text-Encoder. Nur `generate_timeline` ist unerreichbar.
- **Etwas, das `config.json` überschreibt, gibt es nicht mehr als Rätsel:** es
  war der Recovery-Bootstrap nach einem unsauberen Abbruch. Aufgeklärt.

---

## 5. Offene Kleinigkeiten, wenn Zeit bleibt

- `has_audio_embedding` wird nach der Analyse nie aktualisiert (zwei Stellen).
- `"peak"` fehlt in `STRUCTURE_INTENSITY_MULTIPLIERS` und fällt auf 0.8.
- Der Binding-Wächter hat zwei belegte Falschgrün-Klassen (Substring statt
  Wortgrenze; Datei- statt Klassenzuordnung).
- `.venv-pre-lock-20260830` und `.venv-lock` sind Wegwerfstände und können nach
  eigener Prüfung gelöscht werden.

Vollständige Befundlage: `ZUSTANDSAUFNAHME_2026-08-30.md`.
