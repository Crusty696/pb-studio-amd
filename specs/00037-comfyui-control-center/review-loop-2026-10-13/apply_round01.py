from pathlib import Path
import json,copy
root=Path.cwd(); p=root/'specs/00037-comfyui-control-center'; a=p/'review-loop-2026-10-13'; b=a/'round-01-baseline'
plan=(b/'plan.md').read_text(encoding='utf-8'); comm=(b/'communication-contract.md').read_text(encoding='utf-8'); tasks=(b/'tasks.md').read_text(encoding='utf-8'); wp=json.loads((b/'work-packages.json').read_text(encoding='utf-8')); old=copy.deepcopy(wp)
def replace(s,x,y):
 assert x in s,x[:80]
 return s.replace(x,y)
plan=replace(plan,'| active / available_partial | needs_decision |','| active / available_partial | awaiting_import | Generierung und QC fertig; mindestens ein Pflichtoutput wartet bewusst auf Übernahme, keine sonstige laufende Pflichtarbeit; kein Fehler, kein aktiver Remoteattempt |\n| awaiting_import | active | bewusster lokaler Importintent mit client_request_id/CAS angelegt und verknüpft; kein neuer Generierungsattempt |\n| available_partial | active | bewusster Analysefortsetzungsintent durable; nur fehlende gewählte Analysearbeit, keine erneute Generierung |\n| active / available_partial | needs_decision |')
plan=replace(plan,'| submission_unknown | needs_decision |','| submission_unknown / needs_decision | rejected | exakt request-/endpointgebundenes, profilqualifiziertes autoritatives Nichtannahmereceipt oder bewiesener Nicht-Send; kein widersprechendes Accept-/Ausführungsreceipt. Fehlende Queue/History, Proxyfehler oder Timeout reichen nicht |\n| submission_unknown | needs_decision |')
plan=replace(plan,'discovered/staging/validating/validated/published | quarantined | cancelled/obsolete/noch keine Importfreigabe','discovered/staging/validating/validated/awaiting_import/published | quarantined | cancelled/obsolete')
plan=replace(plan,'| validated | published | immutable Zielname','| validated | awaiting_import | autoimport=false: valide Ausgabe dauerhaft in owned staging sichern; user_wait_reason=import_not_requested; keine Fehlerquarantäne |\n| awaiting_import | published | bewusster lokaler Importintent/CAS freigegeben; neuer Claim verknüpft ursprünglichen Job, immutable Veröffentlichung und erneut gültige QC/Hashnachweise |\n| validated | published | autoimport=true oder explizite Importfreigabe; immutable Zielname')
plan=replace(plan,'| catalog_committed | analysis_pending | normale Analyseanforderung und immutable Run angelegt |','| catalog_committed | analysis_pending | autoanalyze=true oder bewusster Analyseintent; normale Analyseanforderung und immutable Run angelegt |\n| catalog_committed | catalog_committed | autoanalyze=false: durable user_wait_reason=analysis_not_requested, LogicalJob available_partial; kein Worker, keine automatische Analyse, keine Eligibility vortäuschen |')
plan=replace(plan,'5. Catalog+Importclaim+geplante Analyse lokal unter Recovery-/Projektguard committen.','5. Catalog+Importclaim+Analysepolicy lokal unter Recovery-/Projektguard committen; Analyseauftrag nur mit Freigabe, sonst dauerhafter Wartegrund ohne Worker.')
plan=replace(plan,'→ accepted / rejected / quarantined Artifactreceipt','→ validiertes Artifactreceipt oder rejected/quarantined\n→ bei deaktiviertem Autoimport awaiting_import bis bewusste lokale Freigabe')
plan=replace(plan,'→ normaler Analyse-Run mit ausgewählten Providern','→ bei deaktivierter Autoanalyse catalog_committed/available_partial bis bewusste Analysefreigabe\n→ normaler Analyse-Run mit ausgewählten Providern')
plan=replace(plan,'| WorkflowRevisionKey | workflow_id, revision, bundle_hash; drei Felder müssen zusammenpassen |','| WorkflowRevisionKey | workflow_id, revision, bundle_hash; drei Felder müssen zusammenpassen |\n| WorkflowActivationReceipt | WorkflowRevisionKey, enabled, activation_revision, registry_generation, opaque activation_token; mutable Freigabe getrennt von Bundlecontent |\n| AnalysisContinuationRequest/Receipt | client_request_id, project_uuid, origin_job_uuid, import_receipt_uuid, expected_state_revision, gewählte Pflichtstages/Policy; receipt: analysis_intent_uuid, state/revision, verknüpfte Runs |')
plan=replace(plan,'Ausschließlich Aktivierungsflag per CAS, immutable Bundleinhalt bleibt unverändert','expected_activation_token+client_request_id; WorkflowActivationReceipt, stale409; immutable Bundleinhalt bleibt unverändert')
plan=replace(plan,'comfyui/workflow_registry.py::WorkflowRegistry.set_enabled(key: WorkflowRevisionKey, enabled: bool) -> WorkflowRevisionKey','comfyui/workflow_registry.py::WorkflowRegistry.set_enabled(key: WorkflowRevisionKey, enabled: bool, expected_activation_token: str, client_request_id: UUID) -> WorkflowActivationReceipt')
plan=replace(plan,'| POST `/artifacts/{id}/import` |','| POST `/jobs/{id}/analyze` | Idempotenter projektgebundener Analysefortsetzungsintent mit expected_state_revision/import_receipt_uuid; nur ausdrücklich gewählte Analyse, kein neuer Generierungsattempt |\n| POST `/artifacts/{id}/import` |')
plan=replace(plan,'Reuse-only-Export beweist keine Fresh-Generation-Endurance; keine erfundene Mindestquote','Reuse-only-Export beweist keine Fresh-Generation-Endurance; keine erfundene Mindestquote. G8-shared ausschließlich beaufsichtigt; G8-unattended verlangt zusätzlich qualifiziertes T016 und tatsächlichen kooperierenden Scope')
plan=replace(plan,'T045/T044 pflegen `docs/comfyui/architecture.md`','T045 liefert den verpflichtenden Developer Guide unabhängig vom Wizard; T044 ergänzt nur ausdrücklich gewählten Wizardscope. T045/T044 pflegen `docs/comfyui/architecture.md`')
contract='''# Reviewloop: verbindliche Korrekturen Runde01

Diese Regeln ergänzen Plan Q/P/S, Kommunikationsvertrag und Arbeitspakete. Ausschließlich Planabsicht; alle folgenden Produktprüfungen NOT RUN.

## L01 — Nutzerkontrolliertes Warten ist kein Fehler

Generierungserfolg, Übernahmeentscheidung und Analysebereitschaft getrennt persistieren. LogicalJob awaiting_import ist ein dauerhafter nichtterminaler Nutzerwartezustand; Activity-/Lease-/Closeprüfung behandelt ihn nicht als laufenden Worker. Artifact-/Importsagazustand awaiting_import sichert valide owned Stagingbytes samt Hash/QC/Provenance; bloß deaktivierter Autoimport erzeugt keine Quarantäne. Noch laufende Pflichtoutputs werden weiter verfolgt; Job erst parken, wenn keine sonstige Pflichtarbeit läuft.

Bewusster Import erzeugt weiterhin neuen lokalen Intent/Claim ohne neuen Generierungsattempt. Durable relation origin_job_uuid→import_intent_uuid→import_receipt_uuid bindet Original und Fortsetzung. Die nichtterminale ursprüngliche Importsaga darf unter CAS den freigegebenen Import fortführen; genau ein Artifactpublikations-/Medieneintrag. Nach Catalogcommit Originaljob available_partial, nach echten Pflichtreceipts ready; der lokale Importintent besitzt eigenen dokumentierten Abschluss. Bereits cancelled/obsolete Originaljobs bleiben terminal. Ein bewusst neu freigegebener Import aus terminaler Quarantäne erhält eine neue lokale Importsaga ab discovered mit erneuter Hash/QCprüfung des erhaltenen Artefakts; terminale alte Saga und ursprüngliche Provenance bleiben unverändert.

Autoanalyse=false belässt die Importsaga catalog_committed mit analysis_not_requested und Job available_partial. Keine automatische Analyse, kein aktiver Worker, kein GPUlease, kein Retry/Endlospolling. Explizites POST /jobs/{id}/analyze erzeugt idempotenten AnalysisContinuationRequest/Receipt; Import-/Projekt-/Revisionsbindung und noch fehlende Pflichtstages prüfen. Native-MVPanalyse hat keinen neuen Comfy-Generierungsattempt. Spätere alternative Analyseprovider besitzen ihre eigenen klar typisierten Analysejobs, niemals heimlich eine zweite Mediengenerierung.

Restart rekonstruiert Nutzerwartepolicy, Intents und Receipts ohne automatische Freigabe. Batchprojektion trennt ausführung_fertig von medien_bereit und wartet_auf_nutzer; ein geparkter Batch meldet weder unendliche aktive GPUarbeit noch Gesamtbereitschaft. Retention schützt wartende Ergebnisse bis bewusstem Abbruch/Archivierung und separat freigegebener Löschung; keine stille TTL-Löschung. Cancel/obsolete während Import/Analyse nutzt bestehende CAS-/Drainregeln; spätere Importreceipts reaktivieren keinen terminalen Originaljob. UI zeigt Übernehmen/Analysieren/Abbrechen und Ursache; Workflow-/Jobwire-Enummapping ausdrücklich ergänzen.

Endabnahme T026: alle vier Autoimport/Autoanalyse-Kombinationen, mehrere Pflichtoutputs, Restart, spätere Freigabe, verlorene Antwort/Doppelklick, Cancel im Fortsetzungsrennen. Keine ungewollte Analyse, keine doppelte Katalogzeile und kein neuer Generierungsattempt. T010/T011/T019/T021/T022/T024/T025 liefern vorher ihre isoliert prüfbaren Teilverträge.

## L02 — Reshot vor seiner vollständigen Timelineabnahme

T040 hängt zusätzlich von T030 ab. FP17-Endabnahme verwendet erst danach einen real qualifizierten Reshot-Child. Allgemeine Variantenfixtures ersetzen diesen Nachweis nicht. Keine weitere Nutzerentscheidung erforderlich; ursprünglicher Reshotzielumfang bleibt erhalten.

## L03 — Unbeaufsichtigte Longform benötigt qualifizierte Koordination

T041/Phase-Manifest unterscheidet G8-shared-supervised und G8-managed-unattended. Ersteres verwendet ausdrücklich beaufsichtigtes observed_shared mit dessen Grenzen. Verlässlich unbeaufsichtigte Freigabe verlangt bedingt T016 einschließlich vollständiger lokaler Consumerintegration, qualifiziertem tatsächlich kooperierendem Scope und Cleanup-/Lease-/Nichtkooperatorprüfungen. T016 bleibt keine erste MVPpflicht, wird aber zwingende Vorgängerfreigabe für diesen später gewählten Betriebsclaim. Runtime darf ein ungeeignetes Profil nicht allein wegen leerer Queue in unattended hochstufen.

## L04 — Pflichtdokument unabhängig vom optionalen Wizard

T045 ist Createowner von docs/comfyui/developer-guide.md. Der Guide entsteht phasenweise mit den tatsächlich gelieferten Verträgen; geplante Kapitel bleiben als geplant erkennbar. T044 konsumiert ihn nur und liefert bei gewähltem Wizard seine Ergänzungen über T045. Vollständiger Pflichtscope liefert architecture.md, installation.md, workflow-format.md, provider-system.md, troubleshooting.md und developer-guide.md ohne Wizard. Phasen-QC prüft nur bereits fällige Abschnitte, keine vorgezogene Vollständigkeit späterer Funktionen.

## L05 — Workflowinhalt und Aktivierung besitzen verschiedene Revisionen

WorkflowRevisionKey bleibt unveränderliche Contentidentität. WorkflowActivationReceipt trägt enabled, activation_revision und registry_generation sowie opaken Token. Aktuellen Receipt aus GET /workflows lesen; PATCH mit expected_activation_token/client_request_id. Gleicher Mutationintent/Payload liefert denselben Receipt, anderer Payload409. Fremder/veralteter Token409; erfolgreichen Wechsel dauerhaft speichern und erst dann publizieren. Restoregeneration verhindert Wiederverwendung alter Tokens.

Enable-off verhindert neue, noch nicht autorisierte Dispatches. Freigabeprüfung und lokale durable Dispatchautorisierung werden mit Aktivierungswechsel linearisiert; bereits mögliche Sends werden beobachtet/bei ausdrücklichem Cancel gezielt abgebrochen. Disable allein schreibt keine terminalen Receipts um. Kein Lock über Netzwerkwartezeit. T005 liefert Repository-/CASteil; T022 API; T024 vollständige UI-Endabnahme mit zwei Fenstern, Antwortverlust, Replay und Reopen.

## L06 — Autoritative spätere Nichtannahme löst Unknown

Q2 erlaubt submission_unknown/needs_decision→rejected nur mit exakt gebundenem autoritativem Nichtannahmereceipt oder nachweislichem Nicht-Send. Ein validierter später verarbeiteter Requestreceipt kann genügen; generisches Proxy400/5xx, Connectionloss und leere History/Queue nicht. Widerspruch zu vorhandener Annahme/Ausführung erzeugt Conflict, keine Retryfreigabe. Danach unveränderte Retrypolicy/Budget; neuer Attempt mit neuer Prompt-ID erst nach definitiver Entscheidung. T010 Zustandsvertrag; T012 Transportreceipt; T013 vollständige Reconciliationprüfung; T014 Retryregression.
'''
plan+='\n## X. Wiederholter Vollreview und ergänzende Zustandsverträge\n\n[Reviewloop-Korrekturen](review-loop-2026-10-13/contracts.md) L01–L06 sind verbindlicher Bestandteil. [Prüfprotokoll](review-loop-2026-10-13/protocol.md) definiert vollständige Runden und gesonderte Abschlussverifikation. Kein Nullbefund-/Abschlussclaim vor erfülltem Protokoll.\n'
comm+='\n## 13. Ergänzungen aus Vollreviewrunde01\n\nPlan Q und review-loop-2026-10-13/contracts.md L01/L05/L06 ergänzen die Wireverträge: awaiting_import und analysis_not_requested als ehrliche Nutzerwarteprojektionen; idempotente Analysefortsetzungsroute; WorkflowActivationReceipt mit eigenem Token; Unknown→rejected nur mit qualifiziertem Nichtannahmebeleg. Goldenfixtures, Job-/Batchsnapshot und tatsächlicher UIflow berücksichtigen diese Fälle zusätzlich zu W01–W32. L01-Endabnahme T026, L05 T024, L06 T013; frühere Pakete liefern eigene Teiltests, kein vorzeitiger Gesamtnachweis.\n'
byid={t['id']:t for t in wp}
byid['T040']['deps'].append('T030')
byid['T044']['create'].remove('docs/comfyui/developer-guide.md'); byid['T045']['create'].append('docs/comfyui/developer-guide.md')
byid['T044']['consume']+='; phasenweiser Developer Guide T045, Ergänzungen über dessen Pflichtowner'
byid['T041']['gates']+='; G8-shared-supervised nur beaufsichtigt; G8-managed-unattended erst nach qualifiziertem T016 für tatsächlich kooperierenden Scope'
byid['T041']['assert']+=' L03: ohne qualifiziertes T016 keine verlässlich unbeaufsichtigte Freigabe; beaufsichtigtes Shared-Profil getrennt ausweisen und fehlende Kooperation/Cleanupreceipts blockieren unattended.'
byid['T045']['assert']+=' L04: alle sechs Pflichtdokumente einschließlich Developer Guide ohne optionalen Wizard; pro Phase nur fällige Vertragsabschnitte als geliefert markieren.'
byid['T005']['produce']+='; persistiertes WorkflowActivationReceipt mit eigener activation_revision/registry_generation und idempotentem CAS'
fs=json.loads((a/'round-01-findings.json').read_text(encoding='utf-8'))
end={'L01':'T026','L02':'T040','L03':'T041','L04':'T045','L05':'T024','L06':'T013'}
for f in fs:
 for id in f['tasks']:
  t=byid[id]; t['consume']+='; Reviewloop-Vertrag '+f['id']
  t['assert']+=' '+f['id']+': '+(f['acceptance'] if id==end[f['id']] else 'eigenen Schnittstellen-/Zustandsanteil isoliert prüfen; vollständige Endabnahme '+end[f['id']]+', kein vorzeitiger Integrations-PASS.')
for before,after in zip(old,wp):
 start=tasks.index('### '+before['id']+' —'); endpos=tasks.find('\n### ',start+4); endpos=len(tasks) if endpos<0 else endpos; block=tasks[start:endpos]
 for k in ['assert','produce','consume','risk','rollback','gates']:
  if before[k]!=after[k]: block=replace(block,before[k],after[k])
 if before['deps']!=after['deps']:
  block=replace(block,'**Abhängigkeiten / Gates:** '+', '.join(before['deps'])+'.','**Abhängigkeiten / Gates:** '+', '.join(after['deps'])+'.')
  tasks=tasks.replace('| '+before['id']+' | '+before['phase']+' | '+', '.join(before['deps'])+' |','| '+after['id']+' | '+after['phase']+' | '+', '.join(after['deps'])+' |')
  start=tasks.index('### '+before['id']+' —'); endpos=tasks.find('\n### ',start+4); endpos=len(tasks) if endpos<0 else endpos
 if before['create']!=after['create']:
  head='**Neue Dateien (geplant):**\n'; s=block.index(head)+len(head); e=block.index('\n**Interfaces:**',s)
  block=block[:s]+''.join('- `'+str(root/f)+'`\n' for f in after['create'])+block[e:]
 tasks=tasks[:start]+block+tasks[endpos:]
trace=(b/'traceability.md').read_text(encoding='utf-8')+'\n## Vollreviewrunde01\n\n| Befund | Pakete | Status |\n|---|---|---|\n'+''.join('| '+f['id']+' '+f['title']+' | '+', '.join(f['tasks'])+' | Plan korrigiert; Gegenprüfung offen; Produktabnahme NOT RUN |\n' for f in fs)
for name,data in [('plan.md',plan),('communication-contract.md',comm),('tasks.md',tasks),('work-packages.json',json.dumps(wp,ensure_ascii=False,indent=2)+'\n'),('traceability.md',trace),('review-loop-2026-10-13/contracts.md',contract)]:
 (p/name).write_text(data,encoding='utf-8'); assert (p/name).read_text(encoding='utf-8')==data
for f in fs: f['status']='plan corrected; next full review pending'
(a/'round-01-findings.json').write_text(json.dumps(fs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('R1 six corrections applied to planning artifacts only')
