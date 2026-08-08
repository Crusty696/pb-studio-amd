# Claude-Code-Controller-Setup – 2026-07-31

## Ergebnis

`READ_ONLY_SMOKE_VERIFIED` für den Windows-nativen Headless-Controller und
einen ticketgebundenen Repository-Read. Dies ist kein PASS eines
OBJ-72-Reparaturtasks und kein Nachweis für Builder-Schreibisolation.

## Verifizierte Umgebung

- Claude Code: `2.1.212`, native `win32-x64`
- Node.js: `v24.15.0`
- tmux/psmux: `3.3.6`
- Claude `doctor`: keine Installationsprobleme
- Authentifizierung: aktiv über `claude.ai`; keine Zugangsdaten gespeichert
  oder in Evidenz übernommen

## Controller-Nachweis

Isolierter Lauf:

- `claude -p`
- `--safe-mode`
- minimales Systemprompt
- `--tools ""`
- `--permission-mode plan`
- `--no-session-persistence`
- `--output-format json`
- `--max-budget-usd 0.05`
- `--effort low`

Ergebnis: `CLAUDE_CONTROLLER_READY`, Exitcode `0`, gemeldete Kosten
`0.002339 USD`.

## Repository-Read-Nachweis

- Ticket: `OBJ-72-CLAUDE-SETUP-READ`
- CWD: `C:\Users\david\Documents\Pb_studio_AMD_version`
- Start: `2026-07-31T08:23:46.2843514+02:00`
- Ende: `2026-07-31T08:23:51.6272711+02:00`
- Exitcode: `0`
- Modell: `haiku`
- Tools: ausschließlich `Read`
- Ziel: nur die ersten zwei Zeilen von
  `proposed-repair-plan-2026-07-31.md`
- Ergebnis:
  `CLAUDE_READ_READY | # Vorgeschlagener Reparaturplan 2026-07-31`
- Gemeldete Kostenäquivalenz: `0.0246469 USD`
- Claude-Prozesse vor/nach dem Lauf: `17` / `17`
- Git-Status wurde im selben Lauf vor/nachher als exakt gleich verglichen:
  `true`
- Git-Status-SHA-256 nach dem Lauf:
  `7b6bd25b45474a2af1b6259e97faf2247a28a8d57ce0a8acb315e158b2b8e4a0`
- Sanitized Raw-JSON-SHA-256:
  `1b21d50c4601a27766cbe9cf06c1f4addb9607bb45b094546436d0d89ffab3ea`
- Maschinenlesbares Receipt:
  `claude-controller-readonly-receipt-2026-07-31.json`

Sanitisierter Startvertrag:

```text
claude -p <ticket-prompt>
  --model haiku
  --output-format json
  --safe-mode
  --disable-slash-commands
  --system-prompt <minimal-read-only-prompt>
  --tools Read
  --disallowedTools Write,Edit,Bash,Agent,WebFetch,WebSearch,Glob,Grep
  --permission-mode plan
  --max-budget-usd 0.08
  --effort low
  --no-session-persistence
```

## Begrenzter Treiberbefund

`claude-session-driver` `4.0.0` wurde mit vorhandener Zustimmung, Claude-Binary
und separatem Worker-Verzeichnis gestartet. Die tmux-Workersitzung existierte
nach 30 Sekunden nicht mehr; CSD meldete
`Worker session failed to start within 30 seconds`. Es wurden keine
Worker-Artefakte oder Projektdiffs erzeugt. Da WSL nicht installiert ist und
der native tmux/psmux-Pfad die interaktive CSD-Sitzung nicht stabil hält, wird
dieser Start nicht wiederholt.

## Betriebsvertrag

- Teamleiter bleibt einziger Scheduler, Merge- und PASS-Owner.
- Claude läuft bis zu einer bewusst freigegebenen WSL/tmux-Lösung über
  Windows-natives `claude -p`.
- Standard ist read-only mit expliziter Tool-Allowlist.
- Schreibaufträge benötigen Ticket, disjunkte Zone, temporären Git-Worktree,
  konkrete Dateigrenze und einen Pfad-Allowlist-Diff-Gate.
- Shared Files, Webzugriff und Claude-Subagenten bleiben gesperrt.
- Jeder Lauf erhält Zeit-, Ausgabe- und `--max-budget-usd`-Grenzen.
- Budget-/Auth-/Timeout-Fehler lösen keinen automatischen Retry aus.
- Ergebnisse werden anhand realer Dateien, Git-Diff und Verify-Artefakte
  unabhängig geprüft.
