# Verifikation 2026-11-08

- Hashlock: 42 direkte Pins, 130 exakt gebundene Wheels; genau acht Updates.
- Isolierte Vollinstallation aus requirements.txt erfolgreich, pip check ohne
  Konflikte. CPU-PyTorch 2.11.0 und NumPy 1.26.4 bewahrt.
- Nach isolierter Pruefung Update in Projekt-.venv installiert; Freezevergleich
  bestaetigt genau acht geaenderte Versionen, Zusatzpakete erhalten. pip check
  und CPU-Vertragspruefung auch dort bestanden. Kein Produktionsbackend mit
  Projektpfad vor Installation gefunden; kein App-Neustart ausgefuehrt.
- Deployment-Nachpruefung: 46 Security-/Lock-/CI-/SigLIP-Tests bestanden,
  6 Warnungen, 26.70 s; temp/sca-review-20261108/deployed-tests.log.
- Neuer SCA-Report und Validierung im Featureordner: keine unfreigegebenen
  Findings; drei exakte, bis 2026-12-08 befristete Ausnahmen.
- 149 gezielte Regressionen bestanden, 1 Skip (fehlende CLAP-Testaudiodatei),
  8 Warnungen. Aktiver Skip-Guard. Rohlog temp/sca-review-20261108/updated-tests.log.
- Negativlauf vor Erneuerung: zwei Datumskontrakte rot; vor finaler
  Ausnahmeersetzung: registrierter Ausnahmevertrag rot. Danach gruen;
  entfernte Transformers-Ausnahme wird in einem Negativfall geprueft.
- Spec00028 und Spec00040 fuer offene Phase mit bestehendem Validator ohne
  Findings. Keine neue Abschlussbehauptung fuer offene DTO-/GUI-Abnahme.
- GitHub-Gesamtlauf und Merge stehen noch aus; kein CI-PASS vorweggenommen.

- GitHub-CI-Nachlauf: 2237 passed, 35 skipped, 9 deselected, 1 failure; Ursache ist ein ungeguardeter Import des optionalen madmom im echten PF-Decoder-Test. Der Test nutzt nun importorskip; die Skip-Ausnahme ist auf genau diesen Node begrenzt und laeuft 2026-12-08 ab.
- Regressionen: Tests/test_release_ci_gate_regressions.py 8/8 bestanden. Die BeatNet-State-Tests bestehen lokal 9/9 mit installiertem madmom; der frische isolierte Dependency-Aufbau blieb unvollstaendig und wurde beendet, bevor der Skip im Clean-venv bestaetigt war. Vollstaendiger GitHub-Runner bleibt entscheidender Nachweis.

- Zweiter GitHub-Lauf: madmom-Testfehler beseitigt; 2236 passed, 36 skipped, 9 deselected, danach scheiterte der Recovery-Concurrency-Test an WinError 5 beim Ersetzen unter %TEMP%. Der Test schrieb entgegen der festgelegten Testisolation nicht in %LOCALAPPDATA%. Test nun auf ecovery_bootstrap.fixed_control_root() umgestellt; gezielter Windows-Lauf bestanden.
