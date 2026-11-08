from pathlib import Path
import json,re,hashlib,datetime
root=Path.cwd(); p=root/'specs/00037-comfyui-control-center'; a=p/'full-plan-audit-2026-10-13'
wp=json.loads((p/'work-packages.json').read_text(encoding='utf-8')); tasks=(p/'tasks.md').read_text(encoding='utf-8'); plan=(p/'plan.md').read_text(encoding='utf-8'); spec=(p/'spec.md').read_text(encoding='utf-8'); domain=(p/'domain-contracts.md').read_text(encoding='utf-8'); comm=(p/'communication-contract.md').read_text(encoding='utf-8'); fs=json.loads((a/'findings.json').read_text(encoding='utf-8'))
checks={}; errors=[]
def check(k,v):
 checks[k]=bool(v)
 if not v: errors.append(k)
byid={t['id']:t for t in wp}; check('45_unique_open_packages',len(byid)==45 and len(re.findall(r'^- \[ \] T\d{3}',tasks,re.M))==45 and not re.search(r'^- \[[xX]\]',tasks,re.M))
req=set(re.findall(r'\b(?:FR|TR|OR|RR)-\d{3}\b',spec)); check('42_requirements_preserved',len(req)==42 and req=={r for t in wp for r in t['req']})
check('40_original_findings_present',len(set(re.findall(r'^#### (F\d{2})',plan,re.M)))==40)
check('82_original_sections_preserved',len(re.findall(r'^\| \d+ \|', (p/'traceability.md').read_text(encoding='utf-8'), re.M))==82)
check('18_additional_findings_traced',len(fs)==18 and all(f['id'] in domain and f['id'] in (p/'traceability.md').read_text(encoding='utf-8') for f in fs))
order=[]; remaining=set(byid)
while remaining:
 ready=sorted(t for t in remaining if all(d in order for d in byid[t]['deps']))
 if not ready: break
 order+=ready; remaining-=set(ready)
check('dependency_graph_acyclic',not remaining)
def ancestors(t):
 out=set(); todo=list(byid[t]['deps'])
 while todo:
  n=todo.pop()
  if n not in out: out.add(n); todo+=byid[n]['deps']
 return out
creators={}
for t in wp:
 for f in t['create']: creators.setdefault(f,[]).append(t['id'])
check('unique_planned_file_creator',all(len(v)==1 for v in creators.values()))
missing=[]; future=[]; conflicts=[]
for t in wp:
 start=tasks.index('### '+t['id']+' —'); end=tasks.find('\n### ',start+4); block=tasks[start:len(tasks) if end<0 else end]
 for key in ['assert','produce','consume','risk','rollback','gates']:
  if t[key] not in block: missing.append([t['id'],key])
 for f in t['modify']+t['create']:
  if str(root/f) not in block: missing.append([t['id'],f])
 for f in t['modify']:
  if not (root/f).exists():
   owner=creators.get(f,[]); future.append(dict(task=t['id'],file=f,creator=owner))
   if not owner or owner[0] not in ancestors(t['id']): missing.append([t['id'],'missing earlier creator',f])
 idx=next((l for l in tasks.splitlines() if l.startswith('| '+t['id']+' |')), '')
 if (' | '+(', '.join(t['deps']) or 'keine')+' | ') not in idx: missing.append([t['id'],'dependency index'])
 if '**Abhängigkeiten / Gates:** '+(', '.join(t['deps']) or 'keine')+'.' not in block: missing.append([t['id'],'dependency block'])
check('task_metadata_index_blocks_and_file_ownership_match',not missing)
for t in wp:
 if t.get('parallel'):
  for other in wp:
   if other['id']==t['id'] or other['id'] in ancestors(t['id']) or t['id'] in ancestors(other['id']): continue
   overlap=set(t['modify']+t['create'])&set(other['modify']+other['create'])
   if overlap: conflicts.append([t['id'],other['id'],sorted(overlap)])
check('parallel_marked_tasks_no_unordered_write_overlap',not conflicts)
inventory=json.loads((root/'docs/comfyui-plan-review-2026-10-12/source-inventory.json').read_text(encoding='utf-8')); changed=[]
for item in inventory:
 f=root/item['path']; h=hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
 if h!=item['sha256']: changed.append(item['path'])
check('254_inventoried_sources_unchanged',len(inventory)==254 and not changed)
extra_sources=json.loads((p/'communication-audit-2026-10-13/source-hashes.json').read_text(encoding='utf-8'))['source_files']
check('additional_communication_sources_unchanged',all(Path(x['path']).exists() and hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()==x['sha256'] for x in extra_sources))
original=Path(r'E:\AI\.codex\attachments\c4e53c9a-40ff-48bd-8665-be05f6cd0fcc\Eingefügter Text.txt')
check('original_attachment_unchanged',hashlib.sha256(original.read_bytes()).hexdigest()=='4a1f436e6b1825f79623c93ab2d33918e1d6a69f8b66455ef99be776c7a7e6d6')
baseline=json.loads((a/'baseline-manifest.json').read_text(encoding='utf-8')); check('baseline_snapshots_immutable',all(hashlib.sha256((a/'baseline'/f['path']).read_bytes()).hexdigest()==f['sha256'] for f in baseline['files']))
check('spec_under_10KiB',len((p/'spec.md').read_bytes())<=10240)
check('no_completion_markers',not(p/'.completed').exists() and not(p/'.qc-passed').exists())
check('restore_transition_edges_present','| prepared | submission_unknown | Restore' in plan and '| pending / waiting_for_provider / waiting_for_resources / retry_wait | needs_decision | Restore' in plan)
check('restore_generation_consistent_and_automatic','jedem tatsächlichen Restore/Rücksprung' in comm and 'automatischer Crashrecovery' in comm)
check('canonical_existing_project_uuid','bestehende kanonische Katalog-UUID' in plan and 'kein belegter UUIDvertrag' not in plan)
check('partial_stage_status','status: completed | partial | failed' in plan)
check('event_catalog_matches_communication','| ProviderJobEvent | schema_version, event_uuid, store_generation_uuid, job_change_seq' in plan and 'entity_kind' in comm)
check('no_future_full_acceptance_in_T009', 'alle Brain/Pacingconsumer liefern B' not in byid['T009']['assert'] and 'vollständige Endabnahme T031' in byid['T009']['assert'])
check('no_T019_acceptance_cycle','Reale Native-Erzeugung→persistierter Run→ADDreceipt→ready' not in byid['T019']['assert'] and 'Importclaim und Mediaidentität' in byid['T019']['assert'])
check('T020_owns_native_run_producer','src/pb_studio/providers/native_embedding_adapter.py' in byid['T020']['create'] and 'persistiert' in byid['T020']['produce'] and 'T031' not in ancestors('T026'))
check('cloud_gates_removed',not re.search(r'\b(?:O05|Gcloud)\b',plan+tasks+spec+comm+domain))
links=[]
for n in ['plan.md','tasks.md','traceability.md','domain-contracts.md','communication-contract.md','full-plan-audit-2026-10-13/report.md']:
 text=(p/n).read_text(encoding='utf-8'); check('balanced_fences_'+n,text.count('```')%2==0)
 for target in re.findall(r'\]\(([^)]+)\)',text):
  if target.startswith(('http','C:','E:','#')): continue
  dest=(p/n).parent/target.split('#')[0]
  if target.endswith('verification.json'): continue
  if not dest.exists(): links.append([n,target])
check('local_document_links_resolve',not links)
sourcehashes=[]; invalidrefs=[]
for f in fs:
 for ref in f['sources']:
  path,lines=ref.rsplit(':',1); file=root/path
  if not file.exists(): invalidrefs.append(ref); continue
  nums=[int(x) for x in re.findall(r'\d+',lines)]
  if max(nums)>len(file.read_text(encoding='utf-8-sig').splitlines()): invalidrefs.append(ref)
  sourcehashes.append(dict(path=path,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
check('cited_files_and_line_bounds_exist',not invalidrefs)
result=dict(verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),proof_level='Executed planning-document assertions and source hashes only; no product tests, apps, GPU, GUI, migrations or media execution',checks=checks,passed=sum(checks.values()),failed=errors,packages=45,requirements=42,findings=18,source_hashes_checked=len(inventory),source_hash_changes=changed,metadata_errors=missing,unresolved_links=links,invalid_source_refs=invalidrefs,parallel_conflicts=conflicts,future_modify_paths_with_creator=future,topological_order=order,product_acceptance='NOT RUN',implementation='NOT AUTHORIZED')
(a/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(a/'cited-source-hashes.json').write_text(json.dumps(sourcehashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'checks':len(checks),'passed':sum(checks.values()),'failed':errors,'metadata_errors':missing,'invalid_refs':invalidrefs,'broken_links':links},ensure_ascii=False))
if errors: raise SystemExit(1)
