# T413-S7 Finaler Release-Kandidatenlauf

**Status:** PASS bis auf commitgebundene Clean-Provenienz
**Datum:** 2026-08-02

## Security-Diffscan und Workflow-Fix

- Codex-Security-Scan `23377e48-56a4-4275-a6ae-bdd4101d8486` prüfte 23/23
  geänderte oder stützende Security-Dateien gegen Snapshot
  `codex-security-snapshot/v1:sha256:5b85c90b87968c3efec3157a825ff0ed6087c7b5d1bd065fdb2982cea3ad3e66`.
- Ergebnis: 0 reportable Security-Findings. Zwei echte, fail-closed
  Release-Blocker wurden dynamisch bestätigt: akzeptierter `pip-audit`-Exit 1
  blieb in `$LASTEXITCODE` und wurde vom GitHub-PowerShell-Epilog erneut als
  Fehler ausgegeben.
- Fix: Beide akzeptierten Audit-Pfade enden erst nach Status-/Reportprüfung mit
  `exit 0`. Unerwartete Exitcodes, fehlende Reports und nachgelagerte
  Exception-/Fixture-Validierung bleiben fail-closed.
- Regression: 28/28 Python-SCA-Gate-Tests PASS. Der Test führt beide echten
  YAML-`run`-Blöcke mit Exit-1-Fake-Scanner aus: ohne Fix Exit 1, mit Fix Exit 0.
- Unabhängiger Post-Fix-Review: PASS; kein Gate-Bypass oder Fail-open-Pfad.

## Finale automatisierte Qualitätsgates

| Gate | Ergebnis | Beleg |
|---|---|---|
| Python-Gesamtsuite | PASS | 1.207 Outcomes, 0 Failures, 0 Errors, 11 genehmigte Skips; Coverage 62,116 % |
| Python JUnit | PASS | `C:\tmp\pb-t413-python-quality-20260802-final-b1\pytest.xml`, SHA-256 `21fe8db171aea9f83b4a59020ed53aec9d792980b4db2576bfb4e713c07dd6d4` |
| Python Coverage | PASS | `coverage.json`, SHA-256 `6e91ba27b559b24ba33460b1668477dd0b6514f792c780d0490033e54c243f69` |
| Skip-Policy | PASS | 0 ungeprüfte Skips; SHA-256 `34dd9065fb4c9958d18f50cec17ea04799cdf8e51cee07e1fee89e9169d1bec3` |
| .NET Locked Restore | PASS | SDK 9.0.316; UI und Testprojekt lockgebunden |
| Native C#-Tests | PASS | 42/42, 0 fehlgeschlagen, 0 übersprungen |
| WPF Release Publish | PASS | 26 Dateien, 0 Warnungen/Fehler |
| WPF Release ZIP | PASS | 5.452.607 Bytes; SHA-256 `c48e5a12046465b808e25e35559e367b5813c9ae5f42a584a19ebb8626ed3f62` |

## Finale Supply-Chain-Gates

| Gate | Ergebnis | Beleg |
|---|---|---|
| Secret/History | PASS | 1.486 Textdateien, 4.017 History-Blobs, 0 aktive Funde, 15 exakt erlaubte Treffer; SHA-256 `e16745cb0c444954446c86124b269c07522a2241f89d459e7851682c51ea3dc3` |
| Secret-Negativfixture | PASS | 7/7 Regeln erkannt; SHA-256 `1b6f0b850e2112c9ba15fb4f90d69fe936dba4c0d5589bcce5738f4abd75f627` |
| Python-SCA | PASS | 130 Pakete; 2 eindeutige Advisories; 2 exakte Ausnahmen bis 2026-09-01; 0 ungelöst |
| Python-SCA-Report | PASS | SHA-256 `02d66962b072919dd167ecdb0cefb26ea8daecc6656959c134bd156e6496f84e` |
| Python-SCA-Receipt | PASS | SHA-256 `f34ce6a7e400e5c2842715d4b72522009a436cf24f6901285839462ae8534338` |
| NuGet-SCA UI/Tests | PASS | 0 vulnerable; SHAs `8dafd0904c930ae88f2dce686fc29ae9bde04d1506e9d17c9b2f5cd29a59f5fc` / `8c520034932a809fedf9e603efdeb766adbc0e2873d043fa9efdeabaadd44a2c` |
| NuGet-Negativfixture | PASS | Newtonsoft.Json 12.0.1 erkannt; SHA-256 `ed4235875b4f53c476145a369e0402c4288a4a137749fa024e889888b1d10d60` |
| MCP/npm | PASS | 110 Lock-/Runtime-Knoten, 0 Vulnerabilities, Lock v3 verifiziert |

## Abschlussbedingung

T413 bleibt bis zum sauberen Kandidaten-Commit und einem für exakt diesen SHA
erzeugten Manifest mit `release_eligible=true` offen. Danach folgen T414
QC-/Brain-/Marker-Konvergenz und ein letzter sauberer Provenienznachweis.
