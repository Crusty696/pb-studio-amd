# T370 Governance-Bootstrap-Preflight – 2026-07-31

## Status

`IN_PROGRESS` – nicht-destruktive Wahrheitsbasis gesichert. T370 ist noch
nicht PASS; aktive OBJ-72-SDD-Artefakte und exakte Archivkopien fehlen.

## Git-Basis

- Branch: `00013-system-wide-bug-hunting-audit`
- HEAD: `044fa13c70f8880d0c64d78d24667b49ea8f3eb4`
- Remote-Feature-Branch: bytegleich zu HEAD
- Abstand zu `main`: 71 lokale Commits
- Working Tree: bestehende pytest-Scratchordner sowie neuer Audit,
  Reparaturplan, Ledger- und Claude-Evidenzänderungen; kein sauberer
  Release-Snapshot

## Kanonischer historischer OBJ-71-Stand

Quelle für das unveränderte Archivpaar:
`669d9d320774261d6881437760431f7d86ab2b85`.

| Artefakt | Bytes | SHA-256 | Git-Blob |
|---|---:|---|---|
| `spec.md` | 47.807 | `f9a3a816fd153f11ca5704e69308f1ddd417ebd02630d5f2853075f6eb6c543a` | `297c467e7a8d87d5a5e0a6fd76e79d5f43917e6c` |
| `plan.md` | 33.035 | `0ee2e4e30eae12323fe10e9fc11085f63250f219d5e5177eeb7bd80b37f1e98f` | `e87c090ba5f370ec466dfe3ac0546182adfbd357` |
| `tasks.md` | 37.773 | `3b3be044962dc9051e0c6d4fb97b72b2226417e6d18ffb3be519f5a922440e22` | `ebe3b01c061d094650ac24a99cd4d161238a31c2` |
| `.completed` | 312 | `816a8204724153c60d8ccde571c68ab4f0667cea15689055d52c0b9a96ed5254` | `18dffd49bc98b47608b89625e9ffd05b48890506` |
| `.qc-passed` | 332 | `e9917cee36484feecf4b226dca42a8a65d9e1833c42e5e2b9ab7a3906ce9082b` | `084eacbb64b4f0201bf2af66e35374477502f6ff` |
| `qc-report.md` | 22.220 | `a2447a209825a322aed2265f633e74ed80bc225afe1df9f89362cb427fe5d8f3` | `8c6e1214e6ef69cfdbf1c0dde7f1d5486e5445ec` |

Alle sechs Working-Tree-Artefakte sind bytegleich zu HEAD. Die Marker schließen
ausschließlich OBJ-71/T340–T369 ab und sind für OBJ-72 keine PASS-Evidenz.

## Neue Ausgangsbelege

| Artefakt | Bytes | SHA-256 |
|---|---:|---|
| `FULLSTACK_AUDIT_PB_STUDIO_2026-07-31.md` | 18.275 | `91738411a5a1f278f87303c9c5e9f050922571126a6fcb892b5e8248390a1eea` |
| `proposed-repair-plan-2026-07-31.md` | 41.131 | `178f1198b0612985def42ac850f4ea05c13e1c089930cd8b393487935e1c8423` |

## Bestätigte Gate-Lücken

1. `spec.md` überschreitet mit 47.807 Bytes das 10.240-Byte-Limit.
2. Aktive `spec.md`, `plan.md` und `tasks.md` registrieren OBJ-72/T370–T415
   nicht.
3. `checklists/` fehlt.
4. `qc-report.md` beginnt mit historischer OBJ-71-Freigabe und enthält weitere
   widersprüchliche historische Statusabschnitte; ein aktueller additiver
   `REOPENED / NOT RELEASE-READY`-Header fehlt.
5. Feature-Branch-CI, geschützter Main, Clean-Checkout-Beweis,
   Secret-/Python-/NuGet-SCA, SBOM und Attestation fehlen.

## Historische Requirement-Namensräume

- OBJ-69: FR-251–310, SC-068–069, T228–304
- OBJ-70: FR-311–325, SC-070–072, T305–339
- OBJ-71: FR-326–336, SC-073–075, T340–369
- OBJ-72: konfliktfrei ab FR-337, SC-076 und T370

Audit-Bezeichnungen C-/H-/M-/L-* werden nicht als Requirement-Definitionen
umgedeutet; neue Anforderungen erhalten neue FR-/SC-IDs.

## Nächster Gate-Schritt

1. Exakte additive Archivkopien und Hashmanifest für OBJ-71 erzeugen.
2. Aktive OBJ-72-Spec ≤10.240 Bytes, Plan, Tasks und Checklist registrieren.
3. Danach Markerinvalidierung und aktueller QC-Reopen-Header – nur nach
   ausdrücklicher Freigabe.

Bis dahin: keine Produktimplementierung und keine PASS-Markierung für T370.
