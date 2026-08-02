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
| Python-SCA | VALIDATOR PASS / LOCK BLOCKED | pip-audit 2.10.1/OSV bindet 124/124 Lock-Pakete; 109 Rohmeldungen werden zu 69 Advisories in 11 Paketen normalisiert; Produkt- und Scanner-Locks sind freigabepflichtig |
| SBOM/Provenienz | BLOCKED | kein verifiziertes WPF-Publish-Artefakt; `release_eligible=false` erwartungsgemäß |

### Python-SCA-Nachweis

- Scanner: exaktes `pip-audit==2.10.1`, Provider OSV, lokale Ausführung
  ohne falschen GitHub-Action-Claim.
- Report: 124/124 Lock-Pakete, 109 Rohmeldungen, 69 eindeutige Advisories
  in 11 Paketen, 0 angewendete Ausnahmen.
- Lock-SHA-256:
  `7c40a190f86199a4ee21f8050f8e0d83913dd6601226c32d31809ada3111e903`.
- Report-SHA-256:
  `ccd114cc777ae6983db365e602062296c6182e5421dd5a7bcfd64779485c9211`.
- Artefakte: `evidence/T413-python-sca/`.
- Auflösbarer Windows-cp311-CPU-Kandidat: 130 Wheels; Torch-Familie
  `2.11.0+cpu/0.26.0+cpu/2.11.0+cpu`, Transformers `5.5.4`,
  Hugging Face Hub `1.5.0`, Tokenizers `0.22.2`, Setuptools `81.0.0`.
  Resolverkonflikte: 0. Ein frischer OSV-Lauf und reale Laufzeittests sind
  nach der freigabepflichtigen Lock-Regeneration zwingend.

## Reparatur- und Abschlussmatrix

| Paket | Status | Abschlussbeleg |
|---|---|---|
| S1 Backend-Identität/Default-Deny | PASS | Backend 6/6, WPF 9/9, Harness 10/10; finaler unabhängiger Review PASS |
| S2 Chat-Logminimierung | PASS | Tool-/Prompt-/Antwort-/Exception-Inhalte fehlen im Live-Log; 2/2 fokussiert PASS |
| S3 Timeline-Limits | PASS | 144.000 Einträge und 128 MiB vor Parse; 4/4 fokussiert PASS |
| S4 Legacy-Migration | PASS | Restricted Unpickler, Strict JSON, atomarer Publish; 22/22 fokussiert PASS; Re-Review PASS |
| S5 exakter Python-SCA/Lock | VALIDATOR PASS / WAITING APPROVAL | Inventar-, Alias-, Hash-, Scanner- und Provenienz-Gates implementiert; Produkt- und Scanner-Locks freigabepflichtig |
| S6 MCP-Pin/Integrität | WAITING APPROVAL | exakte npm-Versionen/Integritäten und Offline-/Tamper-Design verifiziert; neuer npm-Lock freigabepflichtig |
| S7 finaler Lauf | WAITING | Voll-/Diff-Scan, Secrets, SCA, SBOM, Publish und Provenienz auf finalem SHA |

T413 darf erst `[X]` werden, wenn S1–S7 PASS sind, der erneute Scan keine
offenen Releaseblocker besitzt und das Provenienzmanifest für exakt denselben
sauberen Commit `release_eligible=true` ausweist.
