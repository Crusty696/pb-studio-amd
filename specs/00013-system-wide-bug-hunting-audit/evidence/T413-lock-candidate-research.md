# T413 Lock-Kandidaten — Read-only Research

Status: `DESIGN VERIFIED / REPO CHANGE WAITING APPROVAL`

## Produkt-Lock

- Ziel: CPython 3.11, Windows x64, CPU-Torch-Familie; 130 Wheels.
- Resolver: 130 Einträge, 130 eindeutige Pakete, 0 Konflikte.
- Resolver-Report-SHA-256:
  `2480e8dd92861dd23f39070b880e991c219de16327c9b9cbd237bf949894f155`.
- Inventar-SHA-256:
  `16e50c68ae3db520d61e1b765a3383c3899be99ccaa682ac24760dd7dcf8b167`.
- Exakter OSV-Lauf: `pip-audit==2.10.1`; 130/130 Pakete geprüft.
- OSV-Report-SHA-256:
  `fad451c827768fe144d28f876c6fc555cb4326db8ea8b2ab0b14745045b1a5a3`.
- Ergebnis gegen die 69 Baseline-Advisory-Familien: 67 behoben, 2
  verbleibend, 0 unbekannt.
- Rest 1: `torch==2.11.0+cpu`, `CVE-2025-3000` /
  `GHSA-RRMF-RVHW-RF47` / `PYSEC-2025-194`; betrifft
  `torch.jit.script`, Fix `2.13.0`. Produktionssuche in `src/`, `backend/`
  und `scripts/` findet keinen Aufruf von `torch.jit.script`. Triage:
  `needs_review` mit mittlerer statischer Sicherheit, weil transitive Aufrufe
  des neuen 2.11-Stacks erst im frischen Ziel-Venv vollständig geprüft werden
  können.
- Rest 2: `setuptools==81.0.0`, `CVE-2026-59890` /
  `GHSA-H35F-9H28-MQ5C` / `PYSEC-2026-3447`; betrifft Unicode-Normalisierung
  bei macOS-sdist-Erstellung, Fix `83.0.0`. PB Studio zielt auf Windows x64
  und erzwingt Binär-Wheels. Torch 2.11 verlangt Setuptools `<82`. Triage:
  `not_actionable` mit hoher statischer Sicherheit für den Windows-Release.
- Keine anwendbare `SECURITY.md` wurde gefunden. Die lokale Policy-Basis sind
  der Windows-x64-/Wheel-Lockvertrag und die AMD-/Windows-Projektregeln; das
  Fehlen einer expliziten Security-Policy bleibt eine Proof-Lücke.
- Eine Ausnahme ist erst nach Freigabe zulässig, bindet exakt Paket, Version
  und Alias und läuft spätestens nach 30 Tagen ab. Für Torch bleibt der frische
  Install-/Import-/Runtime-Nachweis zwingende Auflage; die Ausnahme darf diese
  Prüfung nicht ersetzen.

## Security-Scanner-Lock

- Exakter Scanner: `pip-audit==2.10.1`.
- Closure: 29 offizielle, nicht zurückgezogene PyPI-Wheels; 0 sdists.
- Lock-SHA-256:
  `116cff7875527870582ee9c2e182752ae504c3f0887934978ee6e58141518ffe`.
- Offline-Dry-run mit `--require-hashes --only-binary=:all:`: PASS.
- Manipulierter SHA-256: erwarteter Hashfehler, Exit 1.
- Zehn Pin-Konflikte mit dem Produkt-Lock erfordern eine isolierte
  Scanner-Umgebung; Installation in das Produkt-Venv ist unzulässig.
- Resolver-Provenienz: pip 24.0; der erzeugte Lock enthält pip 26.2 als
  explizit gehashtes Scannerpaket. Die finale CI-Umsetzung muss Bootstrap und
  Scannerumgebung getrennt und reproduzierbar belegen.

## MCP-npm-Lock

- Exakte Direktpakete: `@upstash/context7-mcp==3.2.5` und
  `caveman-shrink==0.1.0`.
- Lockfile v3: 110 Paketknoten; alle aufgelösten Knoten besitzen SRI.
- Lock-SHA-256:
  `E6272534127A37B75A0FDDE2507E530BA47553C5BC38FA18017544A093057265`.
- Context7-SRI:
  `sha512-m+GIwQKBx2yCnLN7Et3wqkuTk1iPkMySQH2i6KiUf4B9wVI0tgtjeXRcDfFZPf5rnRA3gjYhr1FqQqMb9aSRnw==`.
- Caveman-SRI:
  `sha512-AH81oXnhBTRrqbolhq3vTMrJxP+Zgk5cTxMYatMVNGNALqqdviY+3sTkSxynCfZQfxNXUwAwi5mWSlrXxM4TkA==`.
- `npm ls --all`: PASS. Lokaler `npx --offline --no`-Start: PASS.
- Direkter Tarball-/Lock-SRI-Vergleich erkennt den manipulierten Context7-SRI.
- Echter `npm ci --ignore-scripts`-Tamperlauf in neuem Temp-Verzeichnis:
  erwarteter Exit 1 mit `EINTEGRITY`; gewünschter manipulierter SHA512 und
  tatsächlicher offizieller SHA512 werden exakt ausgewiesen.
- Manipulierter Lock-SHA-256:
  `3FEB11E1E72934813877AAC19FBD5F2BCA7C800D187B97713BEE0B989CF2F757`.
- npm-Fehlerlog-SHA-256:
  `B424E798006E942D280EA34FAA8F42FC75E6EE3C47AADC7BB6119E2F8C4C796D`.
- Codex kann projekt-relatives `cwd = "."` nutzen. Claude benötigt
  `${CLAUDE_PROJECT_DIR:-.}` bei Root-Start oder einen committed Wrapper für
  Starts aus Unterordnern.

Keine Repo-Abhängigkeit, kein Lock und keine MCP-Konfiguration wurde in dieser
Research-Phase verändert.
