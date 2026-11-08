# Sicherheitsausnahmen und Merge-Gates — 2026-11-08

## Auftrag und Entscheidung

Nutzerfreigabe: bestehende Sicherheitsausnahmen pruefen und nur soweit
vertretbar erneuern; danach Pflichtchecks und regulaerer Merge von PR 34.
Paketupdates/Installationen laut nachfolgender Nutzerkorrektur erst nach der
parallel laufenden Projektbereinigung.

Die bestehenden Ausnahmen wurden zunaechst fuer 30 Tage bis 2026-12-08
revalidiert. Nach dem Paketupdate entfaellt die Transformers-Ausnahme.
Stattdessen wird genau eine neue setuptools-Ausnahme fuer den nachweislich
ungenutzten Legacy-Installationspfad aufgenommen (siehe unten). Damit bleiben
drei exakt gebundene Ausnahmen. Loader, 30-Tage-Grenze und Branchschutz bleiben.

## Erneute Bewertung

| Paket | Advisory | Aktueller Befund | Entscheidung |
|---|---|---|---|
| torch 2.11.0+cpu | [GHSA-rrmf-rvhw-rf47](https://github.com/advisories/GHSA-rrmf-rvhw-rf47) | Betroffen ist torch.jit.script; keine Nutzung in src/, backend/ oder scripts/. CPU-Pins bleiben erhalten. | Befristete Ausnahme fuer genau diesen Befund vertretbar; kein allgemeiner Torch-Sicherheitsnachweis. |
| setuptools 81.0.0 | [GHSA-h35f-9h28-mq5c](https://github.com/advisories/GHSA-h35f-9h28-mq5c) | macOS-sdist/Unicode-Normalisierung; Produktziel Windows x64, requirements.txt erzwingt Wheels. | Befristete Ausnahme fuer diesen Befund vertretbar. Neuer, anderer setuptools-Befund bleibt gesperrt. |
| transformers 5.5.4 | [GHSA-xrqw-3rrv-vx5w](https://github.com/advisories/GHSA-xrqw-3rrv-vx5w) | Kein save_pretrained in src/, backend/, scripts/; Produkt-Loads in CLAP, SigLIP und Moondream mit local_files_only=True. | Befristete Ausnahme fuer diesen Schreibpfad vertretbar. Neuer, anderer Transformers-Befund bleibt gesperrt. |

Quellen: aktuelle Advisory-Seiten und Codeabgleich am 2026-11-08. Gepatchte
Versionen existieren; die Ausnahmen ersetzen keinen spaeteren kompatibilitaets-
geprueften Dependency-Update. Keine Behauptung, transitive Bibliotheken seien
vollstaendig frei von diesen APIs oder die Pakete insgesamt sicher.

## Frischer CI-Scan

GitHub Run 42429938619, Python-SCA-Job 128576395470, Artefakt 13596583038.
Der Report umfasst 130 Abhaengigkeiten und 63 unterschiedliche Advisory-IDs in
zehn Paketen. Drei IDs entsprechen den bestehenden Ausnahmen, 60 nicht.
Die vorherige Validierung brach bereits an der ersten abgelaufenen Ausnahme ab
und verdeckte damit die weiteren Findings. Erneute Auswertung nach Fristkorrektur
lehnt den Produktionsbericht weiterhin korrekt ab.

| Paket | Gesperrter Stand | Befunde | Fixversion laut Scan |
|---|---|---:|---|
| anyio | 4.13.0 | 2 | 4.14.2 |
| certifi | 2026.4.22 | 1 | 2026.10.18 |
| filelock | 3.29.0 | 9 | 4.2.1 |
| fsspec | 2026.4.0 | 1 | 2026.6.0 |
| msgpack | 1.2.1 | 1 | 1.2.3 |
| pillow | 12.3.0 | 41 | 13.0.0 |
| setuptools | 81.0.0 | 2 | 84.1.0 |
| torch | 2.11.0+cpu | 1 | 2.13.0; CPU-Vertrag vorerst bewahrt |
| transformers | 5.5.4 | 2 | 5.10.0 |
| urllib3 | 2.7.0 | 3 | 2.8.0 |

Diese Liste ist ein Updatekandidat, kein Kompatibilitaets- oder Installationsbeleg.
Die 60 neuen Befunde werden nicht pauschal freigegeben.

## Umgesetzter Update nach Bereinigungsabschluss

Abschluss des Chats "Alle Projekte radikal bereinigen" bestaetigt; dessen
Dokument-/Spec00028-Korrekturen separat als ebbd882 gesichert. Keine offenen
Produktabnahmen aus dieser Bereinigung als bestanden umgedeutet.

Der vorhandene Resolver aktualisiert exakt acht von 130 Pins: anyio 4.14.2,
certifi 2026.10.18, filelock 4.2.1, fsspec 2026.6.0, msgpack 1.2.3,
Pillow 13.0.0, Transformers 5.10.4 und urllib3 2.8.0. Alle anderen Pins und
Hashbindungen bleiben gleich. Transformers 5.10.0 ist laut PyPI zurueckgezogen;
stattdessen nicht zurueckgezogenen Patch 5.10.4 verwendet.

Setuptools 84.1.0 ist mit CPU-Torch 2.11.0 nicht aufloesbar: dessen echte
Paketmetadaten verlangen setuptools<82. Kein erzwungener Resolver-Bypass.
Setuptools 81.0.0 bleibt daher mit zwei begruendeten Ausnahmen:

- Bestehender macOS-sdist-Befund wie oben.
- [GHSA-xmj3-9gf7-h52w](https://github.com/advisories/GHSA-xmj3-9gf7-h52w):
  Schreibpfad ueber setuptools.wheel.Wheel.install_as_egg. Kein entsprechender
  Aufruf, easy_install oder setuptools.wheel-Import in Produkt, Setup, Scripts
  oder Workflows. Setup und CI nutzen modernes pip install --require-hashes mit
  Wheel-only-Lock. Exakte Ausnahme fuer setuptools 81.0.0 bis 2026-12-08;
  bei spaeterem CPU-Torch-Update erneut bewerten. Keine allgemeine Freigabe
  beliebiger Wheel- oder Legacyinstallationen.

Frischer OSV-Lauf mit gepinntem pip-audit 2.10.1: nur die drei freigegebenen
Advisorys verbleiben, Gate PASS fuer 130 Pakete. 60 vorherige Befunde sind durch
Updates entfernt (darunter der alte Transformers-Befund); ein neu bewerteter
setuptools-Befund ersetzt die entfallene Transformers-Ausnahme. Belege:
`specs/00040-security-dependency-refresh/audit.json` und `audit-validation.json`.

## Skip-Gate

Der zweite rote CI-Job (128576395420) scheiterte vor Testausfuehrung an der
abgelaufenen pytest-Skip-Liste. Alle bisherigen Eintraege mit den zugehoerigen
Tests abgeglichen: 20 weiterhin existierende Hardware-, Modell-, Codec-,
Generated-DTO- oder bedingte Legacy-Skips bis 2026-12-08 erneuert. Drei ueberholte
Ausnahmen entfernt: gesamtes test_trigger_settings_full_wiring.py und beide
TestGenerateFromTimeline-Eintraege. Dort existieren keine Skipaufrufe mehr.
Keine neuen Wildcards und keine zusaetzlichen Skips; der Release-Guard bleibt aktiv.
Legacy-Skips bleiben explizite Testluecken, keine bestandenen Funktionstests.

## Pruefung und Grenzen

- Vor Konfigurationsaenderung: beide angepassten Datumskontrakte rot.
- Nach Aenderung: 37 Tests in test_t413_python_sca_gate.py und
  test_release_ci_gate_regressions.py mit aktivem scripts.pytest_release_guard
  bestanden, 6 Warnungen, 11.10 s.
- Lokale Rohbelege: temp/sca-review-20261108/red.log, green.log,
  revalidation.log und heruntergeladener CI-Report. Configs vorher gesichert.
- Neue Umgebung vollstaendig aus dem Hashlock installiert: pip check sauber,
  CPU-PyTorch-Pruefung bestanden, 42 direkte Pins und 130 Wheels validiert.
- Anschliessend dieselben acht Updates in der Projekt-.venv installiert;
  Freezevergleich, pip check und CPU-Vertrag bestanden, Zusatzpakete erhalten.
  Installationsbelege: temp/sca-review-20261108/install.log und deploy.log.
- Nach finaler Ausnahmeaenderung: 149 gezielte Tests bestanden, 1 wegen fehlender
  CLAP-Testaudiodatei uebersprungen, 8 Warnungen, 91.63 Sekunden. Release-Guard
  aktiv. Neue Negativpruefung bestaetigt: alte Transformers-Schwachstelle wird
  ohne die entfernte Ausnahme wieder abgewiesen.
- Vorhandener WPF Release-Build und 91 native Tests betreffen unveraendertes C#.
  Finale GitHub-Suite prueft den neuen Dependency-Stand vollstaendig.
- Keine Produktcodeaenderung, kein App-Neustart und keine neue GUI-/Medienabnahme.
  PR 34 bleibt bis gruenen Pflichtchecks ungemergt.

## CI-Nachlauf am 08.11.2026

Der erste vollstaendige PR-Lauf hatte 2237 Python-Tests bestanden, 35 genehmigte Skips, 9 Deselections und einen Fehler: der optionale madmom-Import im echten BeatNet-PF-State-Test war nicht abgefangen. Der Test ueberspringt diesen optionalen Fall nun, wenn madmom fehlt. Eine exakte Skip-Freigabe fuer diesen einzelnen Test ist bis 2026-12-08 befristet; synthetische State-Tests laufen weiter. Der Gatevertragstest besteht lokal 8/8; der BeatNet-State-Test besteht lokal 9/9 mit madmom installiert. Finale Clean-CI-Verifikation steht aus.

## Zweiter CI-Nachlauf am 08.11.2026

Der Fix fuer den optionalen madmom-Import beseitigte den ersten CI-Fehler. Der zweite volle Lauf bestand 2236 Tests und meldete danach WinError 5 in 	est_atomic_json_write_uses_independent_temp_files_under_concurrency, weil der Test %TEMP% statt des isolierten %LOCALAPPDATA%-Recovery-Control-Roots verwendete. Der Test nutzt jetzt ixed_control_root(); gezielter Windows-Test bestanden. Erneuter vollstaendiger CI-Lauf offen.

## Dritter CI-Nachlauf am 08.11.2026

Der Recovery-Concurrency-Fehler blieb auch am isolierten LOCALAPPDATA-Pfad reproduzierbar: Windows verweigerte einen zeitgleichen atomaren Replace (WinError 5). ackend/recovery_bootstrap.py wiederholt nun nur Access-Denied/Sharing-Violations begrenzt dreimal mit kurzen Verzoegerungen. Sonstige OSErrors werden unveraendert weitergereicht. Gezielte Regression mit zwei simulierten Sperren und anschliessendem Erfolg sowie Paralleltest bestanden lokal. Vollstaendige CI-Pruefung dieses Fixes steht aus.

## Skip-Gate-Nachlauf am 08.11.2026

Der dritte vollstaendige Python-Lauf bestand 2238 Tests, scheiterte danach allein an 20 ungefreigebenen Skips in 	est_beatnet_compat.py. Alle Faelle nutzen madmom.features.downbeats.DBNDownBeatTrackingProcessor; madmom ist laut optionaler Requirements-Datei eine source-built optionale Abhaengigkeit. Fuer genau dieses Modul wurde eine befristete Ausnahme bis 2026-12-08 dokumentiert und eine Gate-Regression ergaenzt. Erneuter vollstaendiger CI-Lauf offen.
