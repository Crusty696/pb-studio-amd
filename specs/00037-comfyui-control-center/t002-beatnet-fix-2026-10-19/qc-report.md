# T002 BeatNet-Kompatibilitaetsfix — 19.10.2026

## Ergebnis und Scope

Bestaetigter NumPy-1.26/madmom-0.16.1-DBN-Abbruch behoben und mit echten A01–A03-Ausschnitten ueber beide Python-Aufrufer geprueft. Scope T046/T047 unter T002. T002 insgesamt, musikalische Taktqualitaet und WPF-Gesamtabnahme bleiben offen.

## Umsetzung

- src/pb_studio/audio/beatnet_compat.py: lokaler versions- und typgebundener Adapter an der jeweiligen DBN-Instanz. Selektiert skalare Log-Scores statt heterogener Pfad-/Score-Arrays. Upstream-Schwelle, Korrektur, Zeitversatz, Metrumkandidaten und Gleichstandsregel bleiben erhalten; BSD-Attribution enthalten.
- beat_detector.py: nur vollstaendig angepasste Instanz speichern; PF unveraendert, DBN auch im Online-Modus beruecksichtigt.
- analyzer.py: zweiter direkter Aufrufer nutzt denselben Adapter, gemeinsamen optionalen Import und explizit CPU.
- Tests/test_beatnet_compat.py: 20 neue Regressionen. Installiertes Original wirft im Test weiterhin den reproduzierten Fehler, angepasste Instanz besteht; globale NumPy-Funktion und fremde Decoderinstanz bleiben unveraendert.

Keine Aenderung installierter Bibliotheken, keine Installation, kein globales NumPy-Patching. Keine Anpassung der Beat-This- oder musikalischen Taktlogik.

## Pruefungen nach Stromausfall

Nutzer meldete Stromausfall; LastBootUpTime live 19.10.2026 18:54:22. Vorheriger Testdurchgang nicht als vollstaendig gewertet: A01-Receipt vorhanden, A02/A03 fehlten. Produktcode blieb erhalten. Geschuetzte Dateihashes kontrolliert, weder Backend gestartet noch Recovery zurueckgesetzt. Alle folgenden Hauptnachweise wurden nach dem Neustart frisch ausgefuehrt.

54/54 Tests bestanden, Exit 0, 23,98 s: neue 20 plus 34 angrenzende Tests fuer AudioAnalyzer, Beatfortschritt/-staerke, Importhygiene, Downbeatausrichtung und Engine-Weitergabe. 15 Warnungen aus bestehenden Deprecations und simulierten fehlenden Testaudiodateien. Keine ganze Repository-Testsuite behauptet.

Unabhaengiger Audio-Reviewer: kein blockierender Befund; 16 exakte Decoder-Referenzvergleiche mit echten HMMs, Korrektur an/aus, Schwellen 0/0,4, Laengen 1/2/40/80. Dieser Review erfolgte vor dem Stromausfall; der unveraenderte Code wurde danach erneut kompiliert und getestet. Vier geaenderte Python-Dateien kompilieren, git diff --check sauber.

## Echte Testmedien

Je Originalsekunden 60–90: neue private Float-WAV-Fixtures via vorhandenem FFmpeg, Originale nur gelesen. Je Quelle frischer Prozess; AudioAnalyzer zuerst importiert und analyze_file ausgefuehrt, danach zweimal BeatDetector offline/DBN mit jeweils frischer Instanz. Ersatzpfade mit Fehler-Tripwire gesperrt und Aufrufzahl explizit geprueft. Neun echte CPU-Analysen insgesamt. Keine GPU erforderlich.

| Quelle | BeatDetector Beats | Downbeats | AudioAnalyzer Beats | Ersatzpfadaufrufe | frische Wiederholung identisch |
|---|---:|---:|---:|---:|---|
| A01 | 70 | 35 | 70 | 0 | ja |
| A02 | 70 | 35 | 68 | 0 | ja |
| A03 | 68 | 34 | 68 | 0 | ja |

Die beiden Aufrufer verwenden unterschiedliche Audio-Vorverarbeitung (AudioAnalyzer konvertiert); ihre Anzahlen sind keine zugesicherte numerische Paritaet. Nachweis hier: beide echten BeatNet-Pfade liefern gueltige Ergebnisse ohne den Kompatibilitaetsabbruch und ohne Librosa-Ausweichpfad. Hohe Downbeat-Anzahlen bleiben keine bestaetigte musikalische Wahrheit.

## Separater offener Befund: wiederverwendete Instanz

Der erste Medienversuch nutzte dieselbe BeatDetector-Instanz zweimal. A01 lief ohne Fehler/Fallback, aber drei Beatzeiten (davon zwei Downbeats) verschoben sich bis 20 ms; die strenge Gleichheitsassertion scheiterte. Beleg unveraendert erhalten: same-instance-A01-observation.json. Dies wurde nicht nachtraeglich als bestanden umetikettiert.

Unabhaengige Ursachenprobe: BeatNet/model.py:31–32 initialisiert hidden/cell einmal, :44 schreibt sie fort; BeatNet.py:139–144 und :196–211 setzen sie bei Dateianalyse nicht zurueck. Modell.eval() setzt solche Tensoren nicht zurueck. Gleiche synthetische Features erzeugen ohne DBN-Adapter beim zweiten Aufruf andere Logits (max 0.008167276); Ruecksetzen nur dieser Zustaende stellt erstes Ergebnis exakt wieder her. LOG_SPECT allein bleibt bei identischem Input bitgleich. Genauer A01-Aktivierungs-/Resetvergleich nicht ausgefuehrt. Dies ist ein separat dokumentierter bestehender Zustandsmechanismus, hier nicht repariert. Frische Instanzen in der abschliessenden Kompatibilitaetspruefung verdecken diesen offenen Befund nicht.

## Schutz und Laufzeitstand

Alle drei vollstaendigen Original-SHA-256 vor/nach identisch. Recovery-Marker, config.json, produktive Datenbank/WAL/SHM sowie installierte BeatNet.py und madmom/downbeats.py vor/nach und am Abschluss unveraendert gehasht. Fixtures vor/nach gleich. APPDATA/LOCALAPPDATA/Projekt- und Temp-Pfade der Medienprozesse isoliert; Pytest ebenfalls isoliert. Keine bestehenden Auftraege gesteuert, keine Generierung oder Migration.

Aktualisierte Python-Quellen wurden in frischen Prozessen tatsaechlich geladen und ausgefuehrt. Kein C#-/EXE-Build noetig, keine UI-/Launcherdateien geaendert. Produkt-Backend/GUI bewusst nicht neu gestartet; eine laufende App wurde nicht auf neue Module umgeladen. Daher kein sichtbarer WPF-End-to-End-Nachweis.

## Belege

real-media-verification.json und A01/A02/A03-result.json; pytest-results.xml; independent-review.json; same-instance-A01-observation.json. Ausgefuehrter Harness privat: scratch/t002-beatnet-post-power-20261019-185747/verify_fixed.py. WAVs bleiben ignoriert lokal, nicht Bestandteil dieses Berichts. Keine Medien veroeffentlicht.

Kompatibilitaetsfix abgenommen; T002-Gesamtqualitaet, bestehende Zustandswiederverwendung und fachliche Takteinsbewertung offen.
