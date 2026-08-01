# T412 — Render-Retry/Restart

Status: PASS
Datum: 2026-08-02
Geprüfter Produkt-SHA: `ec3a0d81f2e30f0ba639ffe6bf0c68e14936ed9a`
Anforderungen: `FR-343`, `TR-347`

## Geschlossene Fehler

- Der Startup-Resume rief `_run_render_task` ohne die verpflichtende persistierte `queue_job_id` auf. Der reale Pfad endete dadurch vor dem Rendering mit `TypeError`; der alte Test spiegelte fälschlich dieselbe Vier-Argument-Signatur. Aufruf und Test verwenden nun fünf Argumente.
- `RenderQueue.update_status` akzeptierte beliebige Übergänge und konnte abgeschlossene Historie wieder auf `running` setzen. Eine atomare Zustandsmatrix unter `BEGIN IMMEDIATE` erlaubt jetzt nur Lifecycle-konforme Übergänge; `completed`, `failed` und `cancelled` sind unveränderlich.
- Fehlende gespeicherte Audio-/Video-Hashes wurden als `None` Teil der Identität. Jetzt wird in einem Worker-Thread der SHA-256 des tatsächlichen Mediums berechnet; fehlende Katalogmedien brechen sichtbar ab.

## Vertragsbelege

| Vertrag | Beleg | Ergebnis |
|---|---|---|
| Aktive Deduplizierung | Zwei echte Windows-Spawn-Prozesse starten denselben Job gegen dieselbe SQLite-Datei gleichzeitig | eine Job-ID, eine Zeile, PASS |
| Terminaler Retry | Parametrisch für `completed`, `failed`, `cancelled` | alter Attempt unverändert; neuer Attempt mit neuer ID, PASS |
| Backend-Restart | Persistierter `running`-Job durch echten Resume-Orchestrator | `interrupted → running → completed`, PASS |
| Inhaltsidentität | Projekt-ID/-Root, Timeline, Settings, Audio- und Video-Contenthashes | vollständig, PASS |
| Gleicher Pfad/neuer Inhalt | Fehlende Kataloghashes werden aus Dateiinhalt gebildet; Bytes werden am gleichen Pfad geändert | anderer Digest, PASS |
| Persistenzwahrheit | Queue-Write erfolgt vor UI-/SSE-Erfolgsstatus | Fehler bleibt sichtbar, kein falscher Erfolg, PASS |

## Tests

- Autoritativer fokussierter Lauf: 68 Tests, 0 Failures, 0 Errors, 0 Skips in 18,339 Sekunden.
- JUnit: `T412-render-retry-receipts/T412-focused.xml`, SHA-256 `DCC9F4E6A2A84BB691E4DFE37FC49CE130AAF859B5E48B58243859195FBDEE43`.
- Konsolenlog: `T412-render-retry-receipts/T412-focused.log`, SHA-256 `ACB9CF06941EF97C323FCFFDE5EE75BB8C5A3D7DB6BF03717677CD1123BDF27E`.
- Der erste Lauf meldete 65 PASS und drei Testfehler: eine alte direkte `queued → completed`-Testannahme und zwei falsche Modulimporte. Nach Korrektur dieser Tests bestand der einzige Wiederholungslauf vollständig; die Produktänderung musste nicht nachgebessert werden.
- `receipt.json` bindet Commit, Quellhashes und Vertragsresultate; `receipt-hashes.sha256` bindet alle T412-Belege.

## Unabhängiger Review

PASS ohne Blocker: atomare Cross-Process-Deduplizierung, terminale Unveränderlichkeit, neue Retry-Attempts, korrekte Resume-Queue-ID, vollständiger Restart-Lifecycle und Contenthash-Fallback wurden gegen Code und JUnit-Beleg bestätigt.

## Begrenzung

Der physische AMF-/DirectML-Betrieb ist separat durch T411 belegt. Die Python-Gesamtsuite, Security/SCA/SBOM und endgültige Release-SHA-Bindung folgen in T413–T415.
