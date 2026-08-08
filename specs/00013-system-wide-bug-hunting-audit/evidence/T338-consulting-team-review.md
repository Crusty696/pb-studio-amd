# T338 — Consulting-Team-Wahrheitsreview

Status: DECIDED

Scope: ausschließlich gespeicherte lokale Evidenz zu T305–T337. Keine
Webquellen, keine neuen Produktannahmen und keine erneute Ausführung bereits
vollständig belegter Full-Length-Exporte.

## Executive verdict

**GO für den finalen Wahrheitsabgleich, noch kein GO für Push/Release.**

Die Reparaturevidenz trägt den PASS-Status der Implementierungs- und
End-QC-Gates bis T337. Der vollständige Abschlusslauf und der danach
auszuführende Release-Build bleiben das letzte T338-Gate. T339 bleibt für
Secret-Scan, Remote-Divergenzprüfung, zonierte Commits, Push und
Remote-SHA-Verifikation separat offen.

## Sieben Rollen

| Rolle | Urteil | Evidenz / Begründung |
|---|---|---|
| Lead | DECIDED | T305–T337 sind in `tasks.md` und `repair-progress.md` mit konkreten Belegen geschlossen. |
| Analyst | CONFIRMED | Root Cause wurde durch T308–T310 gegatet; Cycle 9 bestätigte zusätzlich den übersprungenen Router-Finalizer. |
| Domain Expert | CONFIRMED | Postfix-H.264 und -HEVC besitzen je 190.051 Frames, `progress=end`, Full-Decode und 106/106 visuelle Segmente. |
| Risk | OPEN bis Abschlusslauf | Der finale Gesamtlauf und der abschließende WPF-Release-Build dürfen nicht aus früheren Ergebnissen abgeleitet werden. |
| Devil's Advocate | CONFIRMED | Byteidentität allein wäre unzureichend; hier liegen zusätzlich vollständige Decode-, PTS-, Audio- und visuelle Prüfungen beider Codecs vor. |
| Technical Reviewer | CONFIRMED | Öffentliche DTOs/OpenAPI blieben beim T337-Fix unverändert; gezielte Regression 15/15 PASS. |
| Synthesizer | DECIDED | `.qc-passed` ist erst nach 100 % PASS aller T332–T338-Gates zulässig; Veröffentlichung bleibt bis T339 offen. |

## Findings und Gegenentwürfe

### HIGH — Historischer Marker-/Clean-Tree-Vertrag kollidiert mit der Task-Reihenfolge

`SC-069` koppelt `.qc-passed` historisch an einen leeren Arbeitsbaum. Der
freigegebene Reparaturplan erzeugt den Marker jedoch in T338 und committet erst
in T339. Ein buchstäblich leerer Arbeitsbaum ist daher vor T339 unmöglich,
zumal der neue Marker selbst zunächst uncommittet ist.

- Gegenentwurf A: Marker erst nach T339 erzeugen. Abgelehnt, weil dies der
  freigegebenen Reihenfolge und OR-330 widerspricht und einen weiteren Commit
  nach dem angeblich finalen Push erfordern würde.
- Gegenentwurf B: T338 und T339 zusammenlegen. Abgelehnt, weil dadurch
  Testwahrheit und Veröffentlichungswahrheit nicht mehr getrennt wären.
- Entscheidung: Die neuere Amendment-Regel OR-330 ist für den Reparaturzyklus
  maßgeblich: `.qc-passed` belegt ausschließlich 100 % PASS der End-QC-Gates.
  Clean-Tree, Push und Remote-SHA sind das nachgelagerte T339-/SC-072-Gate.
- Reversibilität: hoch; reine SDD-Klarstellung ohne Laufzeitwirkung.

### MEDIUM — Historische PASS-Abschnitte können als aktueller Status fehlgelesen werden

Der bisherige `qc-report.md` beginnt korrekt mit FAILED/REOPENED, enthält
darunter aber mehrere historische PASS-Snapshots. Beim finalen Abgleich muss
ein neuer autoritativer Abschnitt alle älteren Abschnitte ausdrücklich
superseden und nur kanonische T305–T338-Belege referenzieren.

- Gegenentwurf: Historische Abschnitte löschen. Abgelehnt; die
  Falsifikations- und Auditspur soll erhalten bleiben.
- Entscheidung: Historie erhalten, neuen autoritativen Gate-Abschnitt
  voranstellen.
- Reversibilität: hoch.

### MEDIUM — Release-GO darf nicht aus dem QC-Marker abgeleitet werden

T338 kann End-QC bestätigen, aber T339 kann noch an Remote-Divergenz D07,
Secret-Scan oder einem fehlgeschlagenen Push blockieren.

- Entscheidung: `qc-report.md` trennt **QC PASS** von **Publication OPEN**.
- Reversibilität: hoch.

## Steel-man der Gegenposition

Die stärkste Gegenposition lautet, den gesamten Abschluss bis nach T339 als
FAILED zu führen. Das verhindert jede verfrühte Releasebehauptung und hält den
historischen Clean-Tree-Vertrag wörtlich ein. Sie verwischt jedoch zwei
unterschiedliche Tatsachen: getestete Produktqualität und erfolgreiche
Veröffentlichung. Die getrennten Gates liefern die präzisere Wahrheit:
T338 = lokal gespeicherter QC-Nachweis, T339 = Commit-/Remote-Nachweis.

## Confidence

- Technische End-QC-Evidenz T305–T337: **hoch (0,98)**.
- T338-Abschluss vor beendetem Gesamtlauf/Build: **offen**.
- Push-/Remote-Zustand: **offen**, ausschließlich T339.

## Abbruchkriterium

Kein `.qc-passed`, wenn der aktuelle vollständige Testlauf, der abschließende
Release-Build oder ein sonstiges obligatorisches T338-Gate nicht zu 100 %
besteht. Ein T339-Blocker invalidiert nicht rückwirkend die lokale
QC-Evidenz, verhindert aber jede Release-/Push-Erfolgsaussage.
