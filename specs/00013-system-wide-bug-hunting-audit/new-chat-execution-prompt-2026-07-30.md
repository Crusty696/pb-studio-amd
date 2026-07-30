# Prompt für das neue Chatfenster

Arbeite den folgenden bereits vollständig freigegebenen Reparaturplan autonom bis zum Ende ab:

`C:\Users\david\Documents\Pb_studio_AMD_version\specs\00013-system-wide-bug-hunting-audit\approved-repair-plan-2026-07-30.md`

Arbeitsverzeichnis:

`C:\Users\david\Documents\Pb_studio_AMD_version`

Lies vor jeder Aktion vollständig:

1. `C:\Users\david\Documents\Pb_studio_AMD_version\AGENTS.md`
2. `C:\Users\david\Documents\Pb_studio_AMD_version\CLAUDE.md`
3. den oben genannten freigegebenen Reparaturplan
4. `specs\00013-system-wide-bug-hunting-audit\tasks.md`
5. `specs\00013-system-wide-bug-hunting-audit\repair-progress.md`

## Auftrag

- Starte bei T340 und arbeite ohne Unterbrechung bis einschließlich T369.
- Ziel ist nicht nur geänderter Sourcecode. Ziel ist eine gebaute, gestartete, live verifizierte und für meinen nächsten realen App-Test bereite PB-Studio-Version.
- Plane nicht neu und frage nicht erneut nach Freigabe.
- Führe keine Plan-Diskussion. Beginne mit Boot-Prüfung, Git-/Evidence-Inventar und T340.
- Zeige unmittelbar danach die initiale Fortschrittsliste T340–T369.

## Vollständige Autonomiefreigabe

Ich genehmige alle im Plan beschriebenen Aktionen ausdrücklich und im Voraus. Ich will keine Bestätigungen für Befehle, Dateiänderungen, Downloads, Builds, Tests, Starts, Stopps, Backups, Restore-Proben, Commits oder normale Pushes geben.

Innerhalb dieses Plans darfst und sollst du autonom:

- alle erforderlichen PB-Studio-Dateien lesen, erstellen und ändern;
- `.completed` und `.qc-passed` in T340 invalidieren und erst an den definierten Gates neu erzeugen;
- öffentliche DTOs und Verträge einschließlich `IApiClient.cs` planmäßig ändern;
- `src\pb_studio\audio\separator.py` ausschließlich für die zentrale DirectML-Adapterbindung aus T345 ändern;
- lokale LM-Studio- und LibreHardwareMonitor-Konfigurationen vor Änderungen sichern, hashen, ändern und restore-proben;
- die festgelegte offizielle LibreHardwareMonitor-Version herunterladen;
- PB Studio, Backend, LM Studio, Ollama und Hilfsprozesse starten und stoppen;
- Administratorrechte und nicht-interaktive Befehle nutzen;
- Diagnosen, Builds, Tests, GUI-Smokes, Hardwaremessungen und vollständige FFmpeg-Exporte ausführen;
- zonenweise committen, Secret-Scan und Remote-Diff durchführen, normal pushen und Remote-SHAs verifizieren;
- sichere technische Alternativen selbstständig wählen, solange sie Plan und Architekturvertrag nicht verändern.

Fordere dafür keine Zwischenfreigabe und keine Befehlsbestätigung an. Arbeite weiter, solange kein echter, im Plan definierter Blocker besteht.

Diese Freigabe erlaubt weiterhin nicht:

- neue Dependencies, Paket- oder Lockfile-Änderungen;
- Produktionsdatenmigrationen;
- Force-Push oder automatisches Rebase;
- Reverts oder Bereinigung fremder Änderungen;
- Verletzung der AMD-/DirectML-IRON-RULES;
- simulierte Erfolge oder Erfolgsaussagen ohne gespeicherten Beleg.

Bei Remote-Divergenz, unvermeidbarer Dependency-Erweiterung, nicht bestätigter Root Cause, inkompatiblem offiziellen LHM-Bundle oder einem nicht umgehbaren interaktiven UAC-Blocker: Status `BLOCKED`, exakte Evidenz und bereits versuchte sichere Alternativen melden. Nicht endlos wiederholen.

## Verbindliche Arbeitsregeln

- `caveman` und `pb-master` müssen während jedes Tasks sowie bei jedem Subagenten aktiv sein.
- Nutze zusätzlich exakt die im Plan zur jeweiligen Zone passenden Fachskills.
- Vor jeder Implementierung Root Cause, vollständigen Datenfluss, Caller, Seiteneffekte und Architekturvertrag verifizieren.
- Status ausschließlich als `CONFIRMED`, `OPEN`, `DECIDED` oder `BLOCKED` führen.
- Keine Funktions-, Regression-, Hardware-, GUI- oder E2E-Tests vor T361.
- Vor T361 nur Diagnostik, Syntax/XML, Truncation-Schutz sowie statische Vertrags- und Referenzprüfungen.
- T342–T343 sind zwingendes Root-Cause- und Vertragsgate.
- Parallel nur in nachweislich disjunkten Code-Zonen arbeiten.
- Shared Files, öffentliche Verträge, `backend/app_state.py`, `backend/main.py`, Config Manager und Model Registry ausschließlich sequenziell bearbeiten.
- Bestehende Änderungen vollständig erhalten. Keine Reverts und keine Bereinigung fremder Änderungen.
- Keine neue Dependency oder Lockfile-Änderung.
- Keine Produktionsdatenmigration.
- Pflege `tasks.md` als verbindliche Completion-Quelle.
- Erweitere `repair-progress.md` für T340–T369 mit Status, Start, ETA, Ist-Zeit, Owner, Zone, Evidenz und Commit.
- Melde jeden Taskstart, Abschluss und Blocker. Bei Langläufern spätestens alle 30 Minuten.
- Überwache FFmpeg-Langläufer mindestens alle 15 Minuten anhand PID, Logwachstum, Outputgröße und `out_time`.
- Halte die Anti-Loop-Regeln des Plans strikt ein.
- `.completed` erst nach T360.
- `.qc-passed` ausschließlich bei 100 Prozent PASS aller End-QC-Gates.
- Das Referenzvideo und jeder neue Testexport müssen über die gesamte Dauer von `6335,027` Sekunden geprüft werden.
- H.264 und HEVC müssen jeweils den vollständigen Full-Length-Test bestehen.
- Aktualisiere abschließend Skripte, Konfigurationen, DTOs, OpenAPI-Artefakte, Tests, ADRs, CHANGELOG, CLAUDE-Projektstatus und PB-Studio-Bereich des Brain-Vaults.
- Committe zonenweise.
- Führe Secret-Scan und Remote-Diff durch.
- Pushe PB Studio sowie ausschließlich PB-Studio-Pfade des Brain-Repositories.
- Kein Force-Push und kein automatisches Rebase.
- Bei Remote-Divergenz gemäß D07 `BLOCKED`.
- Verifiziere nach jedem Push die Remote-SHAs.
- Behaupte niemals Erfolg ohne gespeicherten Testbeleg.

## Ausgangsevidenz

Manuelles App-Testlog:

`C:\Users\david\Documents\Pb_studio_AMD_version\logs\manual_app_test_20260730_020333.log`

Erwarteter SHA-256:

`086DCC6F3F7B03872AD72B90148B260E9584FACF3556E01AF2797DC193181D52`

Zu Beginn muss T340 dieses derzeit ignorierte Log in die versionierte Evidence-Struktur kopieren und Original sowie Kopie erneut hashen.

Bereits bestätigte Kernbefunde:

- DirectML-Index 0 ist die AMD-iGPU.
- DirectML-Index 1 und LUID `0x00000000_0x0001185b` gehören zur RX 7800 XT mit 16 GB VRAM.
- PB-Studio-Inference lief auf der iGPU, während das VRAM-Budget Werte der RX 7800 XT verwendete.
- LibreHardwareMonitor ist wegen fehlendem Vertrauensmanifest deaktiviert.
- LM Studio besitzt lokale Modelle, liefert bei deaktiviertem JIT aber null Modelle über `/v1/models`.
- Ollama wurde real verwendet; LM Studio nicht.
- Das C#-DTO `SceneInfo` verlangt fälschlich `double Confidence`, obwohl Backend und OpenAPI `null` erlauben.

Beginne jetzt autonom mit T340 und arbeite bis T369 weiter, bis die App nach vollständigem QC wieder für meinen realen Test bereit ist.
