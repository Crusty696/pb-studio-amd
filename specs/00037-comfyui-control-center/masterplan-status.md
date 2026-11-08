# Masterplan — abgehakter Stand 2026-10-20

**6 von 45 Hauptpaketen abgeschlossen. 39 nicht abgeschlossen.** Dazu 11 abgeschlossene Teilaufgaben T046-T056 innerhalb von T002. Kein Aufwand-Prozentsatz; keine fertige PB-ComfyUI-Produktintegration.

Status aus vorhandenen Belegen abgeglichen, keine erneuten Modell-/Medientests. Technische Umsetzung und fachliche Qualität werden getrennt bewertet. Die bereits vorhandenen Haken bleiben erhalten; die bisher veraltete Kopfübersicht ist korrigiert.

## Gesamter Umbauplan

Bibliotheks-/Vertragsumfang T001/T003-T006: [Welle A](wave-a/qc-report.md), [Welle B](wave-b/qc-report.md). Abhängigkeiten und konkrete Abnahmen unverändert in [tasks.md](tasks.md); Architektur in [plan.md](plan.md).

| Paket | Status | Arbeit |
|---|---|---|
| T001 | [X] Erledigt | Policy, Source-Drift und offene Gates festhalten |
| T002 | [ ] Teilweise | Golden Set, Native-Baseline und Qualityprofile |
| T003 | [X] Erledigt | Lesende Endpointbindung und Offlinefähigkeit |
| T004 | [X] Erledigt | Capability-, Node- und Modellidentitäten |
| T005 | [X] Erledigt | Workflowregistry, Revisionen und typed Mapping |
| T006 | [X] Erledigt | Local-only, Trust, Egress und Redaction |
| T007 | [ ] Offen | Früher lokaler Hardware- und Medien-Smoke |
| T008 | [X] Erledigt | Isolierte Result-, Zeit- und Embeddingvalidatoren; Produktintegration spaeter |
| T009 | [ ] Offen | Immutable Analyse-Runs und Cacheidentität |
| T010 | [ ] Offen | Persistente Projektidentität und drei Automaten |
| T011 | [ ] Offen | Additiver Store, UUIDmapping und Migrationsvertrag |
| T012 | [ ] Offen | Scheduler, Submitoutbox und bounded Dispatch |
| T013 | [ ] Offen | Remote-Beobachtung und Reconciliation |
| T014 | [ ] Offen | Own-Cancel, Pause, Retry und Priorität |
| T015 | [ ] Offen | Shared Admission, Budget und Ressourcenprofil |
| T016 | [ ] Optional offen | Optionaler kooperativer Managed-GPU-Gate |
| T017 | [ ] Offen | Sicherer Input-/Outputtransport |
| T018 | [ ] Offen | Technische QC und rationale Medienzeit |
| T019 | [ ] Offen | Canonical Import, Provenance und Ownership |
| T020 | [ ] Offen | Durable ADD-Vektorsaga im Native-SigLIP-Raum |
| T021 | [ ] Offen | Recoveryinventar, Remoteactivity und Shutdown |
| T022 | [ ] Offen | PB REST-, Snapshot- und SSE-Jobverträge |
| T023 | [ ] Offen | WPF Verbindung, Settings und Installationshilfe |
| T024 | [ ] Offen | WPF Workflowlibrary und manuelle Generation |
| T025 | [ ] Offen | WPF Jobs, Queue-Reorder und Herkunftsfilter |
| T026 | [ ] Offen | Integrierten lokalen Generation-MVP abnehmen |
| T027 | [ ] Offen | Varianten, Regenerate und weitere Inputfamilien |
| T028 | [ ] Offen | Upscale als qualifiziertes Derivat |
| T029 | [ ] Offen | Interpolation und rationales FPS-Derivat |
| T030 | [ ] Offen | Begrenzter Reshot und Kontinuitätsprüfung |
| T031 | [ ] Offen | Native Stageadapter und Consumerdurchleitung |
| T032 | [ ] Offen | Alternative Beat-/Downbeat-/Timingprovider |
| T033 | [ ] Offen | Stems und Drumtriggerprovider |
| T034 | [ ] Offen | Energie, Struktur, Harmonie und Longmixprovider |
| T035 | [ ] Offen | Alternative Caption-/Inhalts-/Moodprovider |
| T036 | [ ] Offen | Szenen, Motion, Technik und Qualityprovider |
| T037 | [ ] Optional offen | Optionale alternative und segmentweise Embeddingräume |
| T038 | [ ] Offen | Vergleichsmodus und Kohortenqualifikation |
| T039 | [ ] Offen | Qualifiziertes AUTO und sichtbares Degrade |
| T040 | [ ] Offen | Director Coverage, Asset-DAG und Timelinebindung |
| T041 | [ ] Offen | Bounded Longform-Automation und Gesamtvideo |
| T042 | [ ] Optional offen | Optionales Generatorfeedback und Lernen |
| T043 | [ ] Offen | Retention, Ownership, Archivierung und sichere GC |
| T044 | [ ] Optional offen | Optionaler Setupwizard und Entwicklerhilfe |
| T045 | [ ] Teilweise | Phasenweise Regression, QC und Liefernachweis |

## T002 — erledigte Teilaufgaben

- [X] Sechs Videos und drei Audioquellen ausgewählt; Nutzerbewertungen gespeichert.
- [X] T046/T047: BeatNet-Kompatibilität korrigiert und mit A01-A03 geprüft.
- [X] T048/T049: Wiederverwendete BeatNet-Instanzen isoliert und Reihenfolgen geprüft.
- [X] T050: Belegstand und neues KI-Hirn synchronisiert.
- [X] T051: Begrenzte Audio-Spektral-/Strukturprüfung durchgeführt.
- [X] T052: CPU-Szenenerkennung der sechs Clips durchgeführt.
- [X] T053: Referenzbilder durch Bildinhaltsanalyse geprüft; Qualitätsfehler dokumentiert.
- [X] T054: Belegte Prompt-/Tagfilterfehler korrigiert.
- [X] T055: V02/V03, Bildtransport und mehrere Zeitpunkte untersucht. **Erkennungsfehler nicht vollständig behoben.**
- [X] T056: SigLIP-Vorverarbeitung und Schutz vor vermischten Vektorversionen repariert.

Belege und genaue Grenzen: [current-status.md](current-status.md), [T055/T056-Bericht](t055-vision-2026-10-19/report.md). Letzter Reparaturabschluss: 186 gezielte Tests und getrennte echte Modellprüfungen; keine erneute Durchführung bei dieser Planpflege.

## T002 — noch offen

- [ ] Musikalisch richtige Beat-/Taktanfangsreferenzen, insbesondere A01/A03.
- [ ] Fachliche Abnahme der Bildinhalte; V02 bleibt fehlerhaft, V03 am mittleren Einzelbild ebenfalls. Ein späterer V03-Zeitpunkt erkennt den Wasserfall.
- [ ] Inhaltliche SigLIP-Qualifikation; Textencoder fehlt. Wiederholbare Vektoren sind kein Qualitätsnachweis.
- [ ] Verbleibende relevante Nativepfade: Tonart, Stems, Volltrack/Langdatei sowie Ressourcen- und Qualitätsgrenzen.
- [ ] Unabhängiger Holdout; vorhandene Medien bleiben Regression.
- [ ] Sichtbare vollständige Produkt-/API-/GUI-Abnahme.

## Weitere Reihenfolge und Grenzen

**Aktuelle Nutzerentscheidung:** ComfyUI-Lauf T007 ueberspringen und mit unabhaengigem T008 fortfahren. T007/G1 bleiben offen; spaetere G1-abhaengige Pakete erhalten daraus keine Freigabe.

T008: isolierter Vertrag mit Testgegenfaellen abgeschlossen; [Test- und Grenzbericht](t008-contracts-2026-10-19/report.md). Vollstaendige FP07-Consumerabnahme bleibt T031; G1 bleibt offen.

T010: reine Q1/Q2/Q3-Vertragsfixtures begonnen; [Teilbericht](t010-contracts-2026-10-20/report.md). Keine produktive Transition/Persistenz; Paket offen.

Letzte Livepruefung: externer Server nach Neustart wieder erreichbar; **1 fremder Auftrag laeuft, 0 warten**. T007-Pilot pausiert vor Submit; keine Fremdqueue veraendert.

**Aktueller Nutzeroverride 2026-10-19:** T002 ueberspringen, mit T007 fortfahren. T002 bleibt offen. T007-Livevorpruefung begonnen: ComfyUI 0.41.2 auf Port8190 kurz erreichbar, danach Verbindung verweigert; fremder Filmtest im Stop-/Laufuebergang. Pilot noch nicht ausgefuehrt. [Befund und naechste Schritte](t007-preflight-2026-10-19/report.md). Die nachfolgende urspruengliche Reihenfolge ist insoweit uebersteuert.

1. T002-Restumfang vor der nächsten Messung begrenzen: konkrete offene Frage, notwendiger Nachweis und Abbruchkriterium festlegen. Bereits belegte Teilaufgaben nicht erneut aufrollen.
2. T007 bleibt nach T002/T005/T006 eingeordnet. Ein echter Generierungspilot benötigt seine separate konkrete Freigabe; aktueller Auftrag erlaubt keine Generierung.
3. Danach Abhängigkeiten aus tasks.md einhalten: Vertrags-/Job-/Transport-/Importintegration, anschließend WPF und MVP-Abnahme. T008 hängt bereits nur von T005 ab; der Plan verlangt keine künstliche Serialisierung unabhängiger Pakete.
4. Spätere Erweiterungen, alternative Analyseanbieter, Automatik und optionale Pakete bleiben offen. Weder alle T002-Tests vor jedem Paket wiederholen noch offene Gates still überspringen.

## Arbeitsregel gegen Wiederholungsschleifen

- Vor jedem Lauf: neue Frage und erwarteten Entscheidungsnutzen benennen; vorhandene Belege zuerst verwenden.
- Erfolgreiche Prüfungen nur bei betroffenen Änderungen, neuen Fehlern oder einem konkret offenen Risiko wiederholen.
- Nach einer Reparatur: gezielte Regression plus erforderliche betroffene Verbraucher; keine laufend vergrößerten Testserien ohne Begründung.
- Modellgrenzen als offen ausweisen. Keine wiederholten Promptvarianten ohne neue Hypothese; keine Qualitätsfreigabe aus Testanzahl ableiten.

Originale und laufende Aufträge schützen. Keine Generierung, Installation oder Migration aus dieser Statuspflege ableiten. Cloud gehört nicht zum PB-Umbau. Neues KI-Hirn ersetzt Obsidian.
