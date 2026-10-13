from pathlib import Path
import json,copy,re
root=Path.cwd(); p=root/'specs/00037-comfyui-control-center'; a=p/'full-plan-audit-2026-10-13'; b=a/'baseline'
rows=json.loads((a/'findings.json').read_text(encoding='utf-8'))
for f in rows:
 f['sources']=[s.replace('src/pb_studio/services/brain_service.py','src/pb_studio/brain/brain_service.py') for s in f['sources']]
(a/'findings.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
plan=(b/'plan.md').read_text(encoding='utf-8'); tasks=(b/'tasks.md').read_text(encoding='utf-8'); wp=json.loads((b/'work-packages.json').read_text(encoding='utf-8')); old=copy.deepcopy(wp)
def repl(s,x,y):
 assert x in s,x[:100]
 return s.replace(x,y)
plan=repl(plan,'status: completed | failed | unavailable | not_requested | interrupted','status: completed | partial | failed | unavailable | not_requested | interrupted')
plan=repl(plan,'dauerhafte UUID additiv mappen. Bestehende project_id/root/epoch sind kein belegter UUIDvertrag','bestehende kanonische Katalog-UUID aus stable_project_uuid wiederverwenden; Root/Katalogbindung ergänzen. Flüchtige Epoch bleibt ausschließlich Commitkontext; keine zweite UUIDvergabe')
plan=repl(plan,'| ProviderJobEvent | event_id, job/attempt IDs, ProjectIdentity, state_revision, phase, progress_known/value?, error_code; redacted |','| ProviderJobEvent | schema_version, event_uuid, store_generation_uuid, job_change_seq, project_uuid, entity_kind, entity_uuid, entity_revision; job_uuid/attempt_uuid?/state_revision bei Jobs. Invalidierung gemäß communication-contract.md §8, kein Legacy-Progressdelta |')
plan=repl(plan,'Nicht im Katalog definierte Typnamen sind vor Umsetzung ein Planfehler.','Der Katalog umfasst auch die ausdrücklich referenzierten Kommunikations-DTOs unten. Nicht dort definierte Typnamen sind vor Umsetzung ein Planfehler. Python-interne job_id/attempt_id sind nur ausdrücklich gemappte Aliasse für job_uuid/attempt_uuid am neuen Wirevertrag; keine zweite Identität.')
plan=repl(plan,'| CoverageDecision | sufficient/insufficient/unknown, candidate IDs, required/observed data, calibrated profile, reasons, plan revision |','| CoverageDecision | sufficient/insufficient/unknown, candidate IDs, required/observed data, calibrated profile, reasons, plan revision, TimelineBinding und AnchorSnapshot; valide leere Library vom unknown unterscheiden |')
plan=repl(plan,'| AssetPlan | plan_uuid/revision, requirement slots/ranges/handles, style/character/seedpolicy, dependency DAG, budget, reuse mappings |','| AssetPlan | plan_uuid/revision, stabile Slot-IDs/ranges/handles, TimelineBinding, AnchorSnapshot, style/character/seedpolicy, dependency DAG, budget, reuse mappings einschließlich DerivationTimeMap |')
plan=repl(plan,'expected_config_revision; Endpointwechsel next_job','ConfigToken (Backendinstanz, Revision, Snapshotdigest), atomarer Patch-/Reload-/Persistenzvertrag; Endpointwechsel next_job')
# Remove outdated event representation in prose using exact located sentence fragment.
plan=plan.replace('SSE zeigt Deltas mit job_id, attempt_id, project_uuid, state_revision, phase','SSE invalidiert Jobs/Batches mit ProviderJobEvent gemäß communication-contract.md §8; Snapshot/Changefeed liefert den bestätigten Zustand')
plan=plan.replace('SSE zeigt Deltas mit `job_id`, `attempt_id`, `project_uuid`, `state_revision`, `phase`','SSE invalidiert Jobs/Batches mit ProviderJobEvent gemäß communication-contract.md §8; Snapshot/Changefeed liefert den bestätigten Zustand')
# DTO index: exact structures are normative in referenced sections, avoid duplicate wire definitions.
extra='''
| ApiOutcome, ErrorEnvelope, JobReceipt, PendingProviderIntent | Kommunikationsvertrag §2–3; requestbezogene Outcomes, persistierte Intentidentität und bestätigtes Jobreceipt |
| JobSnapshotPage, JobChangePage | Kommunikationsvertrag §8; gebundene Snapshot-/Changefeedcursor, Generation, Job-/Batchprojektionen |
| CloseReceipt | Kommunikationsvertrag §10; vorbereiteter dauerhafter Closezustand und eigener Freezeowner |
| ConfigToken, ConfigSnapshotReceipt | domain-contracts.md FP15; instanz-/digestgebundene CAS-Identität und bestätigter effektiver Snapshot |
| ActiveAnalysisSnapshot, FieldOwnershipMap | domain-contracts.md FP02; konsistente Capability-/Run-/Feldzuordnung |
| TimelineBinding, AnchorSnapshot | domain-contracts.md FP03–FP04; timeline_uuid/revision, stabile Slots und aufgelöste Ankerbindung |
| DerivationTimeMap | domain-contracts.md FP17; Parent-/Childhash, rationale Bereiche, origin/handles und Mappingrevision |
| ColorProfileReceipt | domain-contracts.md FP13; Stream-/Farb-/Bittiefenprofil und qualifizierte Transformation |
| BenchmarkIsolationReceipt | domain-contracts.md FP16; Evaluationsscope, eingefrorene Gewichte/Projektorgeneration/Lernpolicy |
'''
needle='\nDer Katalog umfasst auch'
plan=plan.replace(needle,extra+needle)
# All restored prepared states need fence before legal dispatch.
lines=plan.splitlines()
for i,l in enumerate(lines):
 if l.startswith('| prepared | dispatching |'):
  lines[i]=l.rstrip().removesuffix('|').rstrip()+'; Restorefence geprüft und Dispatch explizit freigegeben gemäß FP08, recovered prepared ist kein Nicht-Send-Beweis |'
plan='\n'.join(lines)+'\n'
plan+='''
## W. Fachliche Gesamtgegenprüfung2026-10-13

[domain-contracts.md](domain-contracts.md) konkretisiert verbindlich die verbleibenden Übergänge: Analyseconsumer/Brain, Timeline/Anker/Derivatzeit, Recovery, lokale GPU-Consumer, Farbqualifikation, Settings und Benchmarkisolation. [Befunde](full-plan-audit-2026-10-13/findings.json) binden jede Korrektur an Quellen und ursprüngliche Planstellen. [Prüfbericht](full-plan-audit-2026-10-13/report.md) trennt Dokumentnachweis von künftiger Produktabnahme. Die Verträge präzisieren bestehende Requirements; Cloud bleibt außerhalb PB, O03-Messwerte und konkrete O04-Freigaben bleiben offen.

Quellkorrektur: Dauerhafte Katalog-Projekt-UUID existiert bereits (database_core.py stable_project_uuid; project_repository.py; project_router.py; recovery_adapters.py). T010/T011 verwenden sie wieder. Neu ist ihre vollständige Bindung an Jobs und lokale Commitkontexte. Vor Umsetzung einzelne Sourcehashes erneut prüfen.

Alle Fachabnahmen FP01–FP18 sind zukünftig und phasenbezogen zuzuordnen; kein jetziger Runtime-PASS. Phasengates verlangen die Fälle der betroffenen Pflichtpakete, nicht vorzeitig alle späteren Features. Gemeinsame Dateibesitzer werden sequenziell umgesetzt, unabhängig von nomineller Phasennummer; disjunkte Read-only-Prüfung bedeutet keine parallele Schreibfreigabe.
'''
plan=plan.replace('| active / available_partial | needs_decision |', '| pending / waiting_for_provider / waiting_for_resources / retry_wait | needs_decision | Restorefence: verlorene Send-/Cancelhistorie nicht ausschließbar; kein künstlicher Dispatch, bestehende Identitäten bewahren |\n| active / available_partial | needs_decision |')
plan=plan.replace('| prepared | cancelled |', '| prepared | submission_unknown | Restore/Rücksprung: Nicht-Send unbewiesen; bestehende Promptidentität abgleichen, kein Netzwerk-POST |\n| prepared | cancelled |')
plan=plan.replace('`needs_decision` ist nichtterminal, aber blockierend.', '`needs_decision` ist nichtterminal, aber blockierend. Restorebetroffene Jobs ohne erhaltenen Attempt/Importclaim bleiben needs_decision; fehlende jüngere Records nicht erfinden. Autoritative rekonstruierte Originalreceipts dürfen unter CAS den bestehenden Intent/Attempt wiederherstellen und anschließend die vorhandene needs_decision→active-Kante nutzen; kein neuer Remoteversand. Nicht aufklärbar bleibt blockiert; bewusstes Neurechnen nur als neuer Intent gemäß Q2.')
# New normative document with falsifiable scope per finding.
content='''# Ergänzende fachliche Integrationsverträge

Stand2026-10-13. Bestandteil des Masterplans, ausschließlich [ABSICHT]. Quellenbelege und vor Änderung gesicherte Planstellen stehen in full-plan-audit-2026-10-13/findings.json. Folgende Abnahmen sind geplant, nicht ausgeführt. Bereits bestätigte Entscheidungen werden nicht erneut geöffnet. Konkrete Zahlenprofile, Medienfreigaben, DDL und öffentliche API-Freigaben bleiben offen.

Die stärkste tragfähige Architektur bleibt: unabhängiges ComfyUI, PB als Eigentümer von Jobs/Medien/Timeline, revisionsgebundene Resultate, begrenzte Ausführung und nachweisgebundene Qualifikation. Die folgenden Verträge schließen konkrete Übergangslücken dieser Architektur.

'''
endowner={'FP01':'T031','FP02':'T031','FP03':'T040','FP04':'T040','FP05':'T040','FP06':'T031','FP07':'T031','FP08':'T021','FP09':'T011','FP10':'T016','FP11':'T016','FP12':'T015','FP13':'T026','FP14':'T025','FP15':'T023','FP16':'T038','FP17':'T040','FP18':'T020'}
for f in rows:
 content+=f"## {f['id']} — {f['title']}\n\n{f['correction']}\n\n**Verantwortliche Pakete:** {', '.join(f['tasks'])}.\n\n**Endabnahme:** {endowner[f['id']]} im gewählten Scope. Vorgänger liefern und testen nur ihre eigenen Schnittstellen/Teilfälle; Nachfolger konsumieren den Nachweis und prüfen Regressionen. T016-Fälle gelten ausschließlich für managed, T015 prüft zuvor lokale Admission/observed_shared.\n\n**Verbindliche spätere Gegenprüfung:** {f['acceptance']}\n\n"
content+='''## Ergänzende Festlegungen für Umsetzung und Abnahme

- FP01/FP02: FieldOwnershipMap muss vor Implementierung jedes bestehende Audiofeld einschließlich tempo_curve/subtrack_segments einem Producer und Consumer zuordnen. Gemischte Snapshots prüfen konkrete Abhängigkeiten; inkompatible Kombinationen bleiben unqualified. Ein atomar aktivierter Snapshot ersetzt keine unabhängigen unveränderlichen Runs. Kurven dürfen bei fehlender Coverage nicht durch erfundene Nullwerte vollständige Messung vortäuschen.
- FP03/FP04: Zeitlinenschreiber umfassen Generator, manuelle Edits, Autosave, Reload, Import und Clear. Ankeränderung benötigt eine zur Timeline/Assetplanbindung vergleichbare stabile Revision oder geprüften Snapshotdigest. Kein DB-Lock über Netzwerk-/GPU-Warten. Konflikt hält erzeugtes Asset auffindbar, blockiert aber automatische Slotübernahme.
- FP08: Restoreepoch muss vor Freigabe von Scheduler/HTTPmutationen dauerhaft bekannt sein. Bei nicht nachweisbarer Herkunft einer zurückkopierten DB fail closed; bloß identische UUID/gesunde SQLiteintegrität ist kein Frischebeweis. Bewusst neue Jobs nach Restore benötigen neuen Intent und bestätigten Recoveryumfang. Alte unbekannte Outcomes bleiben getrennt sichtbar; kein Freischalten der gesamten alten Outbox durch einen neuen Auftrag.
- FP10/FP11: Consumer-Matrix nennt konkreten Eintritt, Leaseowner, Lockreihenfolge, Timeout-/Cancelcleanup und Endreceipt. observed_shared bleibt Beobachtung ohne Garantie gegenüber fremden Prozessen; lokale Admission allein macht managed nicht kooperativ. Unbekannter Physikzustand wird nicht durch Lease-TTL oder numerische Nullbuchhaltung geheilt.
- FP13: Eingabemetadaten allein beweisen keine korrekte Farbreproduktion. Profile definieren akzeptierte Metadaten/fehlende Angaben, explizite Transformation und Abnahmeausgabe. Keine stille HDR→SDR-Umetikettierung; Original unverändert. Tatsächliche lokale FFmpegfilter/AMFfähigkeit vor Profilfreigabe prüfen. Die rationale FPS-Kette ProductionViewModel→ApiClient→RenderRequest→FFmpeg ebenfalls abnehmen: Dezimal23.976 ist nicht stillschweigend gleich24000/1001. Gapi bleibt offen.
- FP14: communication-contract.md ist normativer Owner des neuen Wireformats; Plan P indiziert dessen Typen. Konkrete JSONschemas/OpenAPI und Goldenfixtures vor Gapi erstellen, unauflösbare Widersprüche blockieren Implementierung. Bestehende Legacyevents behalten ihren separaten Vertrag.
- FP15: Externe Configänderungen sind konkurrierende Schreiber. Genau ein erfolgreicher Commit veröffentlicht den neuen effektiven Snapshot; fehlgeschlagene Persistenz erzeugt keine vorgetäuschte Wirksamkeit. PinnedAttempt enthält den vollständigen für Ausführung benötigten Snapshot/Fingerprint, nicht nur einen flüchtigen Revisionszähler.
- FP16: Evaluationsspeicher gehört zum Benchmarkbereich, kein zweiter Medienkatalog. Gefrorene Brainstände dürfen Vergleichsleser nicht aus laufendem globalem Singleton beziehen. Native-/Provider-Rohqualität und lernabhängige Directorqualität getrennt ausweisen; ein Vergleich ohne Brainabhängigkeit benötigt keinen erfundenen Trainingslauf.
- FP17: Allgemeiner ClipStart bleibt Child-lokale Sourceposition. Mapping wird vor Timelinecommit aufgelöst und in Provenance erhalten; Seekhelper soll keine Parentbeziehung erraten. Bei nichtlinearer Transformation nur tatsächlich qualifiziertes Mapping anwenden.

Öffentliche Grundlagen, gegen die die Planableitung geprüft wurde: [Python3.11 Future.cancel](https://docs.python.org/3.11/library/concurrent.futures.html#concurrent.futures.Future.cancel) unterscheidet wartende und bereits laufende Arbeit; [SQLite Backup API](https://sqlite.org/backup.html) beschreibt einen Datenbanksnapshot, keine atomare Rücksetzung eines externen Ausführungsprozesses; [FFmpeg colorspace](https://ffmpeg.org/ffmpeg-filters.html#colorspace) trennt Farbparameter und Transformation. Diese Dokumentation ersetzt weder den lokalen Buildnachweis noch die qualifizierte Medienabnahme.
'''
# append future acceptance to relevant packages; update markdown copies from old canonical data.
mods={
'T009':['src/pb_studio/brain/post_processor.py','src/pb_studio/brain/loader_cache.py','src/pb_studio/brain/cross_modal_projector.py'],
'T015':['backend/routers/pacing_router.py','backend/routers/render_router.py'],
'T021':['backend/recovery_bootstrap.py'],
'T026':['src/pb_studio/rendering/render_service.py','src/pb_studio/rendering/preview_renderer.py','PBStudio.UI/ViewModels/ProductionViewModel.cs','PBStudio.UI/Services/ApiClient.cs','PBStudio.UI/Services/IApiClient.cs','backend/schemas/render_schemas.py'],
'T030':['src/pb_studio/jobs/derivations.py'],
'T031':['src/pb_studio/services/pacing_service.py','src/pb_studio/pacing/advanced_pacing_engine.py','src/pb_studio/brain/post_processor.py','src/pb_studio/brain/loader_cache.py','src/pb_studio/brain/cross_modal_projector.py'],
'T038':['src/pb_studio/brain/brain_service.py','src/pb_studio/brain/feedback_logger.py','src/pb_studio/brain/projector_trainer.py','backend/routers/brain_router.py'],
'T040':['backend/routers/pacing_router.py','backend/routers/project_router.py','backend/schemas/pacing_schemas.py','backend/app_state.py','PBStudio.UI/ViewModels/TimelineViewModel.cs','PBStudio.UI/ViewModels/VideoLibraryViewModel.cs','PBStudio.UI/Services/ApiClient.cs','PBStudio.UI/Services/IApiClient.cs']}
for t in wp:
 fs=[f for f in rows if t['id'] in f['tasks']]
 if fs:
  t['assert']+=' Gesamtgegenprüfung: '+' '.join((f['id']+': '+f['acceptance']) if t['id']==endowner[f['id']] else (f['id']+': eigenen Anteil gemäß Fachvertrag isoliert prüfen; vollständige Endabnahme '+endowner[f['id']]+' (nur gewählter Scope), danach Nachweis konsumieren/regressionsprüfen; keine zukünftige Integration als bestanden melden.') for f in fs)
  t['consume']+='; verbindliche Fachverträge '+', '.join(f['id'] for f in fs)+' in domain-contracts.md'
 for path in mods.get(t['id'],[]):
  if path not in t['modify']: t['modify'].append(path)
 if t['id'] in ['T026','T040']:
  t['gates']+='; Gapi vor öffentlicher Vertragsänderung, Gmigration vor persistierter Timeline-/Mappingerweiterung'
 if t['id']=='T009':
  t['assert']+=' P2 konkret: Repository, immutable Runs, Snapshot-/FieldOwnershipMap-Vertrag und Cachekern mit bestehenden Native-Cacheconsumern; gemischte Capabilityprojektion erst T031.'
 if t['id']=='T019':
  t['assert']+=' FP18-Teilnachweis hier nur gültiger Importclaim und Mediaidentität; Native-Run/ADD folgt T020.'
 if t['id']=='T020':
  t['create']+=['src/pb_studio/providers/native_embedding_adapter.py']
  t['produce']+='; schmaler Native-SigLIP-Adapter produziert und persistiert den validierten AnalysisRun vor ADD'
 if t['id']=='T040':
  t['create']+=['Tests/test_comfyui_derivative_timeline_ranges.py','PBStudio.UI.Tests/ComfyTimelineRevisionTests.cs']
 if t['id']=='T031':
  t['assert']=t['assert'].replace('aktiver Nativecache unverändert','ohne explizite Aktivierung aktiver Nativecache unverändert')
# use per-task blocks to avoid replacing unrelated prose.
for before,after in zip(old,wp):
 start=tasks.index('### '+before['id']+' —'); end=tasks.find('\n### ',start+4); end=len(tasks) if end<0 else end
 block=tasks[start:end]
 for key in ['assert','produce','consume','risk','rollback','gates']:
  if before[key]!=after[key]:
   assert before[key] in block,(before['id'],key)
   block=block.replace(before[key],after[key])
 if before['modify']!=after['modify']:
  head='**Betroffene Dateien (Modify):**\n'; tail='\n**Neue Dateien (geplant):**'
  s=block.index(head)+len(head); e=block.index(tail,s)
  block=block[:s]+''.join('- `'+str(root/path)+'` — '+('vorhanden' if (root/path).exists() else 'geplant; durch Vorgänger erstellt')+'\n' for path in after['modify'])+block[e:]
 if before['create']!=after['create']:
  head='**Neue Dateien (geplant):**\n'; s=block.index(head)+len(head); e=block.index('\n**Interfaces:**',s)
  block=block[:s]+''.join('- `'+str(root/path)+'`\n' for path in after['create'])+block[e:]
 tasks=tasks[:start]+block+tasks[end:]
tasks=tasks.replace('Vollständige Rückverfolgbarkeit: [traceability.md](traceability.md).','Vollständige Rückverfolgbarkeit: [traceability.md](traceability.md). Fachliche Gesamtgegenprüfung: [domain-contracts.md](domain-contracts.md).')
comm=(b/'communication-contract.md').read_text(encoding='utf-8')
comm=repl(comm,'store_generation_uuid ändert sich bei inkonsistentem Restore/Neuaufbau','store_generation_uuid ändert sich bei jedem tatsächlichen Restore/Rücksprung oder Neuaufbau einschließlich konsistenter automatischer Crashrecovery')
comm=comm.replace('## 4. PB → Comfy:', 'Restorefence FP08 gilt zusätzlich für zurückgespielte Backend-pending/prepared/Outboxrecords und verlorene jüngere Cancelintents. Restoreepoch außerhalb zurückgespielter Domainrecords persistieren; vor Dispatch autoritativ abgleichen, andernfalls needs_decision. Kein Startupscan und keine gesunde Datenbank beweisen Nicht-Send.\n\n## 4. PB → Comfy:')
comm=comm.replace('| W07 | Backendrestart/Uhr zurück/Restore/Journalauslauf | Generation/reset/snapshot, kein alter Cursorclaim |','| W07 | Backendrestart/Uhr zurück/Restore/Journalauslauf; Snapshot vor Send und späterer Restore | Generation/reset/snapshot; Restorefence, kein alter Cursorclaim und null erneute Remote-POSTs aus rückgesetzter Outbox |')
trace=(b/'traceability.md').read_text(encoding='utf-8')+'\n## Fachliche Gesamtgegenprüfung2026-10-13\n\nAlle folgenden Korrekturen präzisieren bestehende Requirements; Produktabnahmen NOT RUN. Quellen/ursprüngliche Planzeilen: [Befundregister](full-plan-audit-2026-10-13/findings.json).\n\n| Befund | Arbeitspakete | Requirements | Vertrag |\n|---|---|---|---|\n'
byid={t['id']:t for t in wp}
for f in rows:
 req=sorted({r for t in f['tasks'] for r in byid[t]['req']})
 trace+=f"| {f['id']} | {', '.join(f['tasks'])} | {', '.join(req)} | {f['title']} |\n"
for name,data in [('plan.md',plan),('tasks.md',tasks),('communication-contract.md',comm),('domain-contracts.md',content),('traceability.md',trace),('work-packages.json',json.dumps(wp,ensure_ascii=False,indent=2)+'\n')]:
 (p/name).write_text(data,encoding='utf-8'); assert (p/name).read_text(encoding='utf-8')==data
print('6 planning documents revised,',len(rows),'contracts; no product files edited')
