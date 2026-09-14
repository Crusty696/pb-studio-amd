# Security-Ausnahmen Prüfung & Entscheidung (T018)

Datum: 2026-09-12
Verzeichnis: `config/`

## Audit & Prüfung
1. **Bestandsaufnahme der Konfigurationsdateien**:
   - `config/security-exceptions.json`: Enthält `entries: []` (0 Ausnahmen; vollständig sauber).
   - `config/python-sca-exceptions.json`: Enthält 3 dokumentierte Ausnahmen:
     - `torch` 2.11.0+cpu (CVE-2025-3000, Ablauf 2026-09-29): `torch.jit.script` wird im Shipped-Code nicht verwendet.
     - `setuptools` 81.0.0 (CVE-2026-59890, Ablauf 2026-09-29): macOS sdist Betroffenheit greift nicht auf Windows Wheel-Only Deployment.
     - `transformers` 5.5.4 (CVE-2026-9856, Ablauf 2026-09-29): `save_pretrained` entfernt, ausschließlich `local_files_only` Loads.
   - `config/secret-scan-allowlist.json`: 8 Einträge, alle strikt beschränkt auf synthetische Test-Fixtures in `Tests/security/fixtures/seeded-secret.txt` mit echten SHA256-Prüfsummen (Ablauf 2026-12-31).
2. **Regressionstests**:
   - `Tests/test_t329_security_regressions.py` verifiziert Path-Traversal-, Media-Policy-, LHM-Hash-Gate- und Injection-Schutz: 11 von 11 Tests bestanden (100% grün).
3. **Entscheidung**:
   - Alle Security-Ausnahmen sind fachlich begründet, zeitlich befristet und durch automatisierte Tests abgedeckt.
   - Keine unberechtigten oder veralteten Security-Ausnahmen vorhanden.
   - Status: BEIBEHALTEN & BESTÄTIGT.
