# T337 Cycle 10 — Active-Render-Dialogversuch

Status: OPEN

## Ergebnis

Der Release-Binary erreichte den sichtbaren Partial-Zustand eines realen
H.264-AMF-Jobs:

- Task: `ac8c7c50`
- Queue-Job: `7f83a97f-b3cf-4245-afdf-8cae5482a7ab`
- Ziel: `t337_project_switch_cancelled_cycle10.mp4`
- Zielartefakt veröffentlicht: nein
- Screenshot: `screenshots-cycle-10-project-switch/export-running-partial-progress.png`

Das direkte Öffnen des nativen Projektordnerdialogs während des laufenden
Renders erzeugte kein neues Top-Level-Fenster. Failure-Signatur:
`RuntimeError: Project dialog did not open: []`.

## Begrenzung und Cleanup

Der Harness beendete WPF und Backend fail-closed. Weil das Backend hart
beendet wurde, blieb genau ein testzugehöriger FFmpeg-Kindprozess aktiv.
PID und Commandline wurden gegen den eindeutigen Cycle-10-Zielstamm
verifiziert; nur dieser Prozess wurde beendet.

Erhaltener Stagingbeleg:

- Pfad:
  `C:\Users\david\Documents\PBStudio\ReleaseQC_20260728_1245\output\.t337_project_switch_cancelled_cycle10.7f83a97f-b3cf-4245-afdf-8cae5482a7ab.e81910d8ba554f2181733bed1d92242f.partial.mp4`
- Bytes: `731.381.808`
- SHA-256:
  `CC35C45B1BF71DD1700ADD9ED865EAE67B7549CECB246D3E7879ECF7E0B43004`

Keine PB-Studio-, Backend- oder FFmpeg-Testprozesse blieben aktiv.

## Alternativweg

Die separate Win32-Probe bestätigte denselben nativen Dialog außerhalb
des aktiven Jobs. Cycle 11 verwendet deshalb den öffentlichen GUI-Lifecycle:
Projekt während des Jobs schließen (dadurch kooperativ abbrechen), danach
über den bestätigten nativen Dialog das Zielprojekt öffnen. Dies prüft
Close/Open-Projektwechsel, Job-Abbruch und Cache-Invalidierung ohne den
bereits falsifizierten Direktdialogweg zu wiederholen.
