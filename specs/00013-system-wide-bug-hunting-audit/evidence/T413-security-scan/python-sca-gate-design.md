# T413 — Python-SCA-Gate, Root-Cause und Upgrade-Machbarkeit

Stand: 2026-08-02  
Commit: `814d2389e3ab687253328ab844ff3498a787621f`  
Scope: read-only Repository-Analyse; externe Artefakte und Resolver-Dry-Runs; keine Installation, kein Lock- oder Produktcode-Edit.

## Ergebnis

Das aktuelle Python-SCA-Gate ist nicht releasefähig. PyPI-/`pip-audit` bricht an `torch==2.4.1+cpu` ab, während OSV den Lock vollständig verarbeitet, aber bekannte Schwachstellen meldet. Ein Abbruch darf nicht als sauberer Scan gelten; die 109 alias-behafteten Rohmeldungen dürfen zugleich nicht als 109 unabhängige Lücken gezählt werden. Bestehende Analyse normalisiert sie auf 69 eindeutige Advisories in 11 Paketen.

Release bleibt **BLOCKED**, bis das Gate fail-closed implementiert und der aktualisierte Lock erneut vollständig auditiert ist. Resolver-Erfolg ist weder Runtime-Kompatibilität noch ein sauberer SCA-Beleg.

## Root-Cause

`requirements.txt` bindet den lokalen PEP-440-Build `torch==2.4.1+cpu`. Dieser Build liegt im offiziellen PyTorch-CPU-Index, nicht unter derselben Versionskennung auf PyPI. Der Standarddienst von `pip-audit` ist `pypi`; `--no-deps` verhindert Abhängigkeitsauflösung, macht die externe `+cpu`-Distribution aber nicht zu einer PyPI-Version. Ergebnis: Dependency-Collection bricht ab, bevor ein vollständiges Urteil entsteht.

OSV kann Name und exakte Version direkt prüfen und verarbeitet die CPU-Index-Pakete. Seine IDs besitzen jedoch Aliasbeziehungen (`OSV`, `GHSA`, `CVE`, `PYSEC`), wodurch Rohzeilen ohne Alias-Normalisierung mehrfach gezählt werden können.

Offizielle Referenzen:

- [pip-audit CLI und Security Model](https://pypi.org/project/pip-audit/)
- [pip-audit Repository](https://github.com/pypa/pip-audit)
- [PyTorch CPU-Versionen](https://pytorch.org/get-started/previous-versions/)
- [Offizieller Torch-CPU-Index](https://download.pytorch.org/whl/cpu/torch/)

## Befund am bestehenden Gate

`.github/workflows/security.yml` nutzt den hashgepinnten Action-Commit, `requirements.txt`, `require-hashes`, `no-deps`, `--strict` und anschließend `scripts/security_gate.py pip-audit-report`. Positiv: Fehler der Sammlung und bekannte Lücken sollen den Job stoppen; die Negativ-Fixture prüft `urllib3==1.26.5`.

Verbleibende Lücken:

1. Standard-PyPI-Dienst kann externe `+cpu`-Version nicht vollständig prüfen.
2. `--minimum-dependencies 100` beweist keine exakte Lock-Abdeckung. Fehlende, zusätzliche oder doppelte Pakete können unerkannt bleiben.
3. Validator prüft Report-Schema und Vulnerability-Zahl, aber nicht exakte `(canonical_name, version)`-Gleichheit mit `requirements.txt`.
4. Alias-IDs werden nicht als zusammenhängende Identitätsmenge normalisiert.
5. Negativ-Fixture beweist Vulnerability-Erkennung, aber nicht getrennt das Scheitern bei fehlenden/falschen Hashes.
6. Tests für Report-Inventar, Alias-Dedupe und negative Lock-Integrität fehlen.

## Ziel-Design: fail-closed ohne Skips

### Gate A — Lock-Integrität

Zuerst Repository-Vertrag ausführen:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
.\.venv\Scripts\python.exe scripts\lock_python_requirements.py verify
```

Pflichtausgang:

- Direct- und Transitiv-Lock stimmen überein.
- Jede Anforderung ist exakt gepinnt und besitzt erlaubte SHA-256-Hashes.
- Vendor-Wheels und CPU-Index-Artefakte entsprechen Manifest/Hash.
- Torch/Torchvision/Torchaudio bilden eine erlaubte CPU-Familie.
- Keine CUDA-/ROCm-/NVIDIA-/Triton-Pakete.

### Gate B — vollständiger OSV-Audit

`pip-audit` auf feste Version pinnen und ohne Resolver/PyPI-Distribution-Lookup ausführen:

```powershell
python -m pip_audit `
  --vulnerability-service osv `
  --require-hashes `
  --no-deps `
  --disable-pip `
  --strict `
  --aliases=on `
  --desc=off `
  --progress-spinner=off `
  --format=json `
  --output artifacts\python-pip-audit-osv.json `
  --requirement requirements.txt
```

Begründung: Offizielle CLI erlaubt `--disable-pip` bei gehashten Anforderungen oder `--no-deps`. OSV prüft auch Versionen aus dem offiziellen CPU-Index. Keine Abhängigkeit darf übersprungen oder in eine PyPI-Teilmenge ausgelagert werden.

### Gate C — exakter Inventar- und Advisory-Validator

`security_gate.py` muss zusätzlich fail-closed prüfen:

- Lock-Inventar parserseitig kanonisieren (`packaging.utils.canonicalize_name`).
- Exakte Mengengleichheit `Lock == Report` über `(name, version)`; fehlend, zusätzlich, doppelt oder unparsebar = Fehler.
- Lock-Datei-SHA-256, `pip-audit`-Version, Provider `osv` und Action/Tool-Commit in Receipt speichern.
- Aliasgraph bilden: Advisory-ID plus `aliases` als verbundene Komponente; Komponenten zählen, Roh-IDs trotzdem vollständig erhalten.
- Kein Advisory ohne explizit freigegebene Ausnahme. Ausnahme bindet kanonisches Paket, exakte Version, mindestens eine Alias-ID, Begründung, Owner und Ablaufdatum; abgelaufen/mismatch = Fehler.
- Netzwerk-/Schema-/Provider-/Collection-Fehler = Fehler, niemals „clean“.

Die aktuelle Schwelle `--minimum-dependencies 100` bleibt höchstens Zusatz-Sanity-Check; Freigabebeleg ist exakte Mengengleichheit.

### Gate D — zwei echte Negativ-Fixtures

1. **Lock-Integrität:** Kopie einer kleinen Fixture mit fehlendem oder falschem Hash. Erwartung: Gate A/B scheitert vor Freigabe.
2. **Vulnerability-Erkennung:** hashgebundenes `urllib3==1.26.5` über denselben OSV-/`disable-pip`-/`no-deps`-Pfad. Erwartung: Audit Exit `1`; Report enthält exakt Paket/Version und mindestens eine normalisierte Advisory-Komponente.

Der Workflow darf für Report-Erzeugung `continue-on-error` verwenden, muss danach aber sowohl den erwarteten Action-Ausgang als auch den Report validieren. Fehlender oder leerer Report = Fehler.

## Upgrade-Machbarkeit

### Kandidat Torch 2.13

**Nicht als kohärente PB-Studio-Familie auflösbar.** Offizieller CPU-Index bietet `torch==2.13.0+cpu` und `torchvision==0.28.0+cpu`, aber kein `torchaudio==2.13.0+cpu`; Torchaudio endet bei 2.11.0. Der Windows-cp311-Dry-Run scheitert deshalb erwartungsgemäß.

Beleg: `resolver-torch213.log`, `torch-index-versions.log`, `torchvision-index-versions.log`, `torchaudio-index-versions.log`.

### Kandidat Torch 2.11 + Transformers 5.5.4

Offiziell kohärente CPU-Familie: `torch==2.11.0+cpu`, `torchvision==0.26.0+cpu`, `torchaudio==2.11.0+cpu`. Erster Dry-Run fand den echten Konflikt `torch 2.11.0+cpu requires setuptools<82`, während PB Studio `setuptools==82.0.1` pinnt.

Letzter angepasster Windows-cp311-Dry-Run löst vollständig, Exit `0`, mit:

- `setuptools==81.0.0`
- `transformers==5.5.4`
- `huggingface-hub==1.5.0` (`transformers 5.5.4` verlangt `>=1.5,<2`)
- `tokenizers==0.22.2` (`transformers 5.5.4` verlangt `>=0.22,<=0.23`)
- NumPy bleibt `1.26.4`; CPU-only Torch-Familie bleibt AMD-Regeln-konform.

Beleg: `resolver-torch211-transformers554.log`, `resolver-torch211-transformers554-adjusted.log`, `resolver-torch211-transformers554-adjusted.json`, [Transformers 5.5.4 PyPI-Metadaten](https://pypi.org/pypi/transformers/5.5.4/json), [Transformers v5.5.4 Release](https://github.com/huggingface/transformers/releases/tag/v5.5.4).

**Nicht bewiesen:** Kandidat ist noch nicht installiert, runtime-getestet, gehasht oder gegen aktuelle OSV-Daten auditiert. Insbesondere Torch 2.11 beseitigt nicht automatisch Advisories, deren Fix erst 2.13 oder gar nicht verfügbar ist.

## Code- und Testauswirkungen

Sicher anzupassen:

- `requirements-direct.txt`: sechs zusammenhängende Pins (`torch*`, Transformers, Hub, Setuptools).
- `scripts/lock_python_requirements.py`: hart codierte Torch-Familie.
- `scripts/verify_cpu_torch_runtime.py`: erwartete Versionen und PASS-Text.
- `requirements.txt`: ausschließlich neu generieren; neue Hashes und Transitiv-Pins.

Statische Importflächen, die nach Installation real geprüft werden müssen:

- `src/pb_studio/video/moondream.py`: `CodeGenTokenizerFast`.
- `src/pb_studio/ai/moondream_pytorch.py`: `AutoModelForCausalLM`, `AutoTokenizer`, `PreTrainedModel`, `trust_remote_code`, Compatibility-Patches für `all_tied_weights_keys` und SDPA.
- `src/pb_studio/ai/clap_pytorch.py` und `clap_wrapper.py`: `ClapModel`/`ClapProcessor`.
- `src/pb_studio/ai/siglip_wrapper.py`: `AutoTokenizer`.
- `src/pb_studio/audio/separator.py`: Torch, Torchvision-Stub, Demucs/audio-separator-Binär-/API-Kompatibilität.

Bestehende Tests decken viele Wrapper nur mit Mocks oder assetabhängigen Skips ab. Mindest-QC nach realer Installation:

1. `scripts/verify_cpu_torch_runtime.py` inklusive CUDA-Paket-/Runtime-Negativprüfung.
2. Import-Smoke aller oben genannten Transformers-Klassen ohne Download.
3. `Tests/test_separator.py`, `test_torchvision_stub.py`, `test_audio_long_mix_truth.py`, `test_stem_progress.py` plus echter kurzer htdemucs-CPU-Lauf.
4. `Tests/test_clap_wrapper.py`, `test_c01_semantic_audio_directml.py`, `test_siglip_video.py`, `test_video_pipeline_truth.py` plus lokale Asset-Smokes.
5. Voller `pytest Tests/ -q`, WPF Release-Build, Fresh-Install und erneuter OSV-Gate-Lauf auf exakt demselben Commit/Lock.

## Umsetzungsreihenfolge

1. Gate A–D und Validator-Unit-Tests implementieren.
2. Upgrade-Closure in `requirements-direct.txt` ändern; Generator-/Runtime-Vertrag synchronisieren.
3. Lock reproduzierbar neu erzeugen und Hash-/CPU-Vertrag prüfen.
4. Kandidaten-Lock durch vollständigen OSV-Audit schicken; keine Skips, exakte Inventargleichheit.
5. Erst danach Runtime-/Hardware-/Fresh-Install-QC. Release nur bei sauberem Audit oder formal genehmigten, exakten, zeitbegrenzten Ausnahmen.

## Loop-Guard und Artefakte

Resolver-Budget eingehalten: zwei begründete Familienversuche, danach Stopp. Kein Retry ohne neue Eingangsdaten. Der zweite 2.11-Lauf war nur die einmalige Korrektur der im ersten Lauf nachgewiesenen Closure-Konflikte.

Artefaktordner: `artifacts/03_sca/`

- `resolver-torch213.log`
- `resolver-torch211-transformers554.log`
- `resolver-torch211-transformers554-adjusted.log`
- `resolver-torch211-transformers554-adjusted.json`
- `requirements-direct-torch213-impossible.txt`
- `requirements-direct-torch211-transformers554-adjusted.txt`
- `constraints-torch211-transformers554-adjusted.txt`
- `torch-index-versions.log`, `torchvision-index-versions.log`, `torchaudio-index-versions.log`
- `transformers-index-versions.log`

