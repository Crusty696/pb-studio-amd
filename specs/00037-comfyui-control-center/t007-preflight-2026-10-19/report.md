# T007: Live-Vorpruefung

## Auftrag und Gate

Nutzer: „ueberspringe das und mach mit T007 weiter“. T002 fuer die Arbeitsreihenfolge ausdruecklich uebersprungen; weder T002 noch G1 dadurch bestanden. Tonartprobe nicht gestartet. T005/T006-Nachweise gelesen; deren Bibliotheksumfang ist keine reale Ausfuehrungsqualifikation.

## Live beobachtet

- Ports 8188, 8000, 8001 antworteten nicht auf system_stats.
- Port 8190 lieferte system_stats: ComfyUI 0.41.2, Python 3.13.12, torch 2.12.0+rocm7.14.0; RX 7800 XT, VRAM gesamt 17163091968 Byte, frei 4853460480 Byte; RAM frei 3084853248 Byte. Momentaufnahme, kein Peak-/Admissionnachweis. ROCm gehoert zur separat laufenden externen ComfyUI-Runtime.
- Serverargumente banden D:/AI/ComfyUI/Runtime/Desktop/ComfyUI/main.py und Filmtestverzeichnisse unter E:/03_Video_&_Medien/DJ_GOETTIN_H3_LTX_60MIN_AGENTENPAKET_2026-10-15/H3/H3_AB_REVISION_20261019. Vorhandener Server gehoert nicht diesem Pilot.
- Queue zum ersten Abruf 0 laufend / 0 wartend. Kurz danach object_info: Verbindung verweigert. Vorheriger Serverprozess 19260 nicht mehr vorhanden. Keine vollstaendige aktuelle Node-/Modellbindung moeglich.
- Fremdes ab_state.json: stop_requested_finish_current; erster A-Auftrag completed, B-Auftrag weiterhin running. STOP_TEST vorhanden. Pythonprozesse 18732/1272 vorhanden. Diese widerspruechlichen Momentaufnahmen beweisen weder laufende GPUarbeit noch einen sauber abgeschlossenen Filmtest.

## Technische Vorbedingungen

Abschliessende erneute Livepruefung: server_restart.log meldet Neustart auf8190; system_stats wieder erreichbar (0.41.2), Queue jetzt **1 laufend / 0 wartend**, RAM frei28673691648Byte. Fremdes ab_state bleibt stop_requested_finish_current mit einem running-Eintrag. Aktueller Blocker ist damit belegte fremde Queuearbeit nach Neustart, nicht dauerhafte Nichterreichbarkeit. Kein eigener Pilot zusaetzlich gestartet.

workflow_policy.validate_local_policy liefert weiterhin execution_ready=False. Welle B dokumentiert unbekannte reale Auditidentitaet und nicht unterstuetzte Enum-/dynamische Nodeschemata. Ein konkreter Pilotgraph muss gegen aktuelle Discovery gebunden und auditiert werden; keine Test-Verifier-Freigabe und kein direkter Submit als Umgehung.

## Ergebnis und Fortsetzung

T007 begonnen, Vorpruefung blockiert durch wechselnde fremde Runtime. Kein POST, kein Submit, Interrupt, Free, Neustart, Download oder Modellladen; keine Produktdateien, Konfigurationen, Originale oder fremden Auftraege geaendert. Kein Output, keine Peakmessung, kein G1-Receipt, keine Completion-/QCmarker. Kein Build erforderlich: ausschliesslich Dokumentation.

Nach stabilem Runtimezustand: Queue, Prozessbaum und Filmprotokoll gemeinsam pruefen; aktuelle Node-/Modell-/Sourceidentitaeten erfassen; vorhandenen kleinen lokalen Graphen und eigenen Ausgabeunterordner mit endlichem Ressourcen-/Laufbudget binden; erforderliche Vertragsluecken gezielt pruefen und schliessen. Erst danach konkreten Generierungspilot gemaess T007-Gate ausfuehren. Keine automatische Wiederholung oder Hintergrundueberwachung eingerichtet.
