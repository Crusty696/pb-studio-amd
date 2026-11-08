# ComfyUI Discovery — Fehlerdiagnose

- Offline/Timeout: Diagnose als fehlender oder unvollständiger Snapshot behandeln. Keine automatischen Neustarts oder Jobwiederholungen.
- Falscher Dienst/ungültige Antwort: nicht bereit melden; URL/Profil prüfen. Keine Antworttexte mit Zugangsdaten loggen.
- unbekannte Version/Modellidentität: Discovery kann sichtbar sein, aber keine Workflowqualifikation daraus ableiten.
- laufende ComfyUI-Arbeit: keine Queueänderung; ausführliche Inventarabfrage kann Assetscan auslösen. Minimalprobe nur system_stats.
- RUNTIME_DIRTY in PB: keine Markerentfernung durch Bridge; vor späterem produktivem Start separaten Recoveryzustand prüfen.

Welle A bietet noch keine WPF-Bedienoberfläche. Ein Source-/Vertragstest ist keine GUI-/GPU-/Medienabnahme. Qualifikation echter Arbeitsabläufe folgt T007 und späteren Gates.

## Welle B

Staler activation_token: aktuellen Receipt lesen und Nutzerintention erneut bewerten; nicht blind überschreiben. Registry fehlt trotz Lockdatei oder Ledger korrupt: fail-closed; kein automatischer Reset. Restore erst unter künftigem Recoveryvertrag. permission_execution_identity_unverified bedeutet fehlende Qualifikation, keinen Verbindungsfehler. effective_graph_changed sperrt auch legitime Parameteränderungen, solange deren spätere Ausführungsidentität nicht gebunden ist. Unbekanntes Schema/Outputadapter nicht durch Abschalten der Validierung umgehen.
