# T333 – Full Suite und Release-Build

Status: CONFIRMED

## Root Cause und Reparaturzyklen

- Der erste Gesamtlauf reproduzierte 28 Fehler bei 1004 PASS. Bestätigte
  Produktursachen waren fehlertoleranter Missing-Media-Restore, Pfadstatus im
  Audio-Import, fehlender `hmac`-Import, vor Bestätigung ablaufende
  Chat-Autorisierung und die ignorierte kanonische `centroid_curve`.
- Die übrigen Fehler waren veraltete Testverträge oder fehlende
  Test-Isolation für Medienkatalog, Render-Validierung, Stem-Root und
  Shutdown-Zustand.
- Gezielter Reparaturzyklus 2 schloss 10/11 Fälle. Reparaturzyklus 3 schloss
  den letzten normalisierten Brain-Pace-Fall. Der danach ausgeführte
  betroffene Cluster bestand 145/145 Tests.

## Full Suite

- Ergebnis: `1032 passed, 11 skipped, 46 warnings, 0 failed`.
- Laufzeit: `497.86 s`.
- Coverage: `21084` Statements, `7895` nicht abgedeckt, `63%`.
- Vollständiges Log:
  `T333-full-suite-rerun-20260729T1100.out.log`
  (SHA-256 `B81C520162E275DB6891D2AC7C6461BFF21BB5FC9BBFCD49ECE6D0A7EB6883A5`).
- Stderr war leer:
  `T333-full-suite-rerun-20260729T1100.err.log`
  (SHA-256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`).
- Coverage-Report:
  `T333-coverage-rerun-20260729T1100.log`
  (SHA-256 `6A6C70AF5F112D744B7180DE8C0EB74FB916A400AB56C3252B8124C368BA336A`).

## Skip-Audit

Alle 11 Skips sind CONFIRMED und begründet:

- 1 deprecated Ollama-Vision-Testmarker; der aktive LM-Studio-Wrapper besitzt
  eine eigene Testsuite.
- 2 optionale CLAP-Integrationen; lokales ONNX-Modell beziehungsweise
  Beispielaudio fehlen.
- 4 optionale SigLIP-Text-/Modellintegrationen; Vision-Verträge und
  Fallbackpfade wurden ausgeführt.
- 1 optionales manuell annotiertes Subtrack-Akzeptanzset; der synthetische
  Detector-Cluster wurde ausgeführt.
- 3 optionale Waveform-Medienintegrationen; Unit- und Downsampling-Verträge
  wurden ausgeführt.

Kein Skip verdeckt einen ausgefallenen Release-Vertrag. Modell- und
GUI-Laufzeitverifikation bleibt zusätzlich T337 zugeordnet.

## Warning-Audit

- Bibliothekswarnungen betreffen Python-3.13-Deprecations, synthetisch kurze
  Audiofenster, OpenMP-Koexistenz und einfarbige K-Means-Testdaten.
- Eine `PytestUnhandledThreadExceptionWarning` war produktseitig:
  PowerShell-Ausgabe konnte ungültige Konsolenbytes enthalten. Alle
  SystemMonitor-PowerShell-Reader verwenden jetzt `errors="replace"`.
- Der gezielte Warnungs-als-Fehler-Lauf bestand 3/3:
  `T333-system-monitor-warning-rerun.log`
  (SHA-256 `E45B32A373E3CC1F7D0DCAEAA6D12520070A022C8393FA8D00952DB8514C91B8`).
- Ein dritter identischer Full-Suite-Lauf ist gemäß Anti-Loop-Regel nicht
  zulässig. Der Nachweis besteht deshalb aus Full Suite PASS vor der eng
  begrenzten Reader-Änderung und dem vollständigen betroffenen
  Warnungs-Cluster PASS danach.

## Release-Build

- `dotnet build PBStudio.UI\PBStudio.UI.csproj -c Release --nologo`
- Ergebnis: PASS, 0 Warnungen, 0 Fehler.
- Log: `T333-wpf-release-build-20260729T1100.log`
  (SHA-256 `82DC8E08A05E649E70F2400E644CBF4346A4F3D90516D0572F6C11A4942B36EE`).

## Gate

- T333: PASS / CONFIRMED.
- `.qc-passed` bleibt bis zum vollständigen T338-Gate unzulässig.
