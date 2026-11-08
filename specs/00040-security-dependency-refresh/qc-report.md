# QC-Bericht

## Authoritative OBJ-1 Gate

- **Overall result:** **REOPENED / NOT RELEASE-READY**.

Lokale Pruefungen laufen, finale
GitHub-Pflichtchecks und Merge noch offen. Keine Abschluss-/QC-PASS-Marker.

## Vorliegende Belege

Siehe `docs/security-review-2026-11-08.md`. Lockvalidierung und isolierte
Installation erfolgreich; pip check sauber und CPU-Torch-Vertrag bestaetigt.
Frischer SCA-Bericht: keine unfreigegebenen Befunde nach drei exakten Ausnahmen.

## Offen

Gezielte Tests der neuen Umgebung, finale acht CI-Checks und regulaerer Merge.
Keine neue Produkt-/GUI-/Medienabnahme Gegenstand dieses Auftrags.

## Python CI Nachlauf

- CI auf 301d98c: 2237 passed, 35 skipped, 9 deselected, 1 failed. Ein echter PF-Decoder-Test importierte das optionale madmom ohne Guard.
- Enger Skip ueber pytest.importorskip plus exakt passende, befristete Allowlist-Regel hinzugefuegt. Regressionstest fuer Gatevertraege: 8/8 bestanden. BeatNet-State-Tests lokal mit madmom: 9/9 bestanden.
- CI-Nachweis nach Fix und Merge offen; Spec bleibt NOT RELEASE-READY.

- Zweiter CI-Lauf beseitigte den optionalen madmom-Importfehler, fand danach einen WinError 5 im Recovery-Paralleltest unter %TEMP%. Testziel auf den isolierten LOCALAPPDATA-Control-Root umgestellt; gezielter Windows-Test bestanden. Vollstaendiger GitHub-Nachweis noch offen.

- Dritter CI-Nachlauf reproduzierte WinError 5 beim parallelen Replace auch unter isoliertem LOCALAPPDATA. Begrenzter Retry fuer Windows Access-Denied/Sharing-Violation implementiert. Simulierte Retry-Regression und Konkurrenztest lokal bestanden; finale CI-Verifikation offen.

- Dritter voller Lauf bestand 2238 Tests; Gate stoppte bei 20 nicht freigegebenen optionalen madmom-Skips des DBN-Adaptermoduls. Modulregel eng und befristet aufgenommen; Regression sichert Owner, Ablaufdatum und Grund. Erneuter Voll-CI-Lauf offen.
