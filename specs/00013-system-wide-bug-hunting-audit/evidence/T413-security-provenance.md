# T413 Security- und Provenienz-Gate

Status: `IN PROGRESS / NOT RELEASE-READY`  
Baseline-SHA: `814d2389e3ab687253328ab844ff3498a787621f`  
Scan-ID: `6ec79e8a-abb1-47b3-a304-3170a12a247e`

## Versiegelter Vollscan

- Zielinventar: 1.683/1.683 Dateien; 1.445 Text/Code vollständig, 238
  Binärdateien per Typ/Größe/SHA geprüft; 0 fehlend/unprüfbar/doppelt.
- Ergebnis: 17 reportable Findings (1 MEDIUM, 16 LOW), 1 deferred,
  8 nach Attack-Path-Validierung verworfen; 0 HIGH/CRITICAL.
- Höchster Befund: festes Backend-Port-Attach ohne Besitzbeweis kann die
  Owner-Capability an einen fremden lokalen Prozess senden.
- Deferred: Legacy-Pickle-Migration; kein unterstützter Angreiferpfad zum
  Ablegen der Datei bewiesen. Die Migration wird trotzdem gehärtet.
- Manifest-SHA-256:
  `D0EE1E2118391F649EB3DD7C3DE3AE7DF508592AD34618B77AC8A0BEC07DCFB2`
- Findings-SHA-256:
  `9B960D05AEC9927341D647B7A86859A84F1BB4F0F028F1A3B13FE797CF5014AD`
- Coverage-SHA-256:
  `B411071DB407BC24BA9374BF0796D35E15893A3885B92E3EA62CF4D5013DBF70`
- Report-SHA-256:
  `4CA80135CFF5C73D58A9606D944D1B1D612230224048FC17171576E848369C7C`
- Versiegelte Artefakte: `evidence/T413-security-scan/`.

## Repository-Gates auf Baseline-SHA

| Gate | Ergebnis | Beleg |
|---|---|---|
| Secret Scan | PASS | 1.451 tracked Textdateien, 232 Binär-Skips, 3.965 History-Objekte, 7/7 Negativregeln |
| NuGet-SCA | PASS | beide Produktionsgraphen sauber; verwundbare Newtonsoft.Json-Fixture erkannt |
| Python-SCA | BLOCKED | PyPI-Provider bricht an `torch==2.4.1+cpu`; OSV findet normalisiert 69 Advisories in 11 Paketen |
| SBOM/Provenienz | BLOCKED | kein verifiziertes WPF-Publish-Artefakt; `release_eligible=false` erwartungsgemäß |

## Reparatur- und Abschlussmatrix

| Paket | Status | Abschlussbeleg |
|---|---|---|
| S1 Backend-Identität/Default-Deny | PASS | Backend 6/6, WPF 9/9, Harness 10/10; finaler unabhängiger Review PASS |
| S2 Chat-Logminimierung | PASS | Tool-/Prompt-/Antwort-/Exception-Inhalte fehlen im Live-Log; 2/2 fokussiert PASS |
| S3 Timeline-Limits | PASS | 144.000 Einträge und 128 MiB vor Parse; 4/4 fokussiert PASS |
| S4 Legacy-Migration | PASS | Restricted Unpickler, Strict JSON, atomarer Publish; 22/22 fokussiert PASS; Re-Review PASS |
| S5 exakter Python-SCA/Lock | IN PROGRESS | OSV-/Inventar-/Alias-Gate; Lock-Upgrade freigabepflichtig |
| S6 MCP-Pin/Integrität | WAITING APPROVAL | exakte npm-Versionen/Integritäten verifiziert; Lockdesign ausstehend |
| S7 finaler Lauf | WAITING | Voll-/Diff-Scan, Secrets, SCA, SBOM, Publish und Provenienz auf finalem SHA |

T413 darf erst `[X]` werden, wenn S1–S7 PASS sind, der erneute Scan keine
offenen Releaseblocker besitzt und das Provenienzmanifest für exakt denselben
sauberen Commit `release_eligible=true` ausweist.
