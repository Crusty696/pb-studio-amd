from pathlib import Path
import json,hashlib,re,datetime
p=Path('specs/00037-comfyui-control-center'); a=p/'review-loop-2026-10-13'
# Run complete existing planning checker fresh, preserve its historic outputs.
code=(p/'full-plan-audit-2026-10-13/verify_documents.py').read_text(encoding='utf-8-sig')
code=code.replace("(a/'verification.json').write_text","(p/'review-loop-2026-10-13/final-structural.json').write_text").replace("(a/'cited-source-hashes.json').write_text","(p/'review-loop-2026-10-13/final-source-hashes.json').write_text")
exec(compile(code,'current_complete_structural_checks','exec'))
p=Path('specs/00037-comfyui-control-center'); a=p/'review-loop-2026-10-13'; m4=json.loads((a/'round-04-input.json').read_text()); m5=json.loads((a/'round-05-input.json').read_text()); st=json.loads((a/'status.json').read_text()); plan=(p/'plan.md').read_text(encoding='utf-8'); w=json.loads((p/'work-packages.json').read_text(encoding='utf-8')); by={t['id']:t for t in w}; trace=(p/'traceability.md').read_text(encoding='utf-8'); c=(a/'contracts.md').read_text(encoding='utf-8')
checks={
'R4_R5_identical_normative_inputs':m4['files']==m5['files'],
'current_normative_files_match_final_round':all(hashlib.sha256((p/r['file']).read_bytes()).hexdigest()==r['sha256'] for r in m5['files']),
'final_two_rounds_complete_clean':all(x.get('complete') and x.get('verdict')=='CLEAN' for x in st['rounds'][-2:]),
'24_plan_chapters_exact':re.findall(r'^## ([A-X])\. ',plan,re.M)==list('ABCDEFGHIJKLMNOPQRSTUVWX'),
'82_original_ids_exact':set(map(int,re.findall(r'^\| (\d+) \|',trace,re.M)))==set(range(82)),
'7_loop_contracts_present':all('## L%02d'%i in c for i in range(1,8)),
'L01_normal_wait_not_quarantine':'| validated | awaiting_import |' in plan and 'cancelled/obsolete/noch keine Importfreigabe' not in plan,
'L01_manual_analysis_route':'POST `/jobs/{id}/analyze`' in plan,
'L02_real_reshot_precedes_adoption':'T030' in by['T040']['deps'],
'L03_unattended_requires_managed':'G8-managed-unattended erst nach qualifiziertem T016' in by['T041']['gates'],
'L04_developer_guide_mandatory':'docs/comfyui/developer-guide.md' in by['T045']['create'] and 'docs/comfyui/developer-guide.md' not in by['T044']['create'],
'L05_activation_own_CAS':'expected_activation_token: str, client_request_id: UUID) -> WorkflowActivationReceipt' in plan,
'L06_qualified_unknown_rejection':'| submission_unknown / needs_decision | rejected |' in plan and 'Fehlende Queue/History, Proxyfehler oder Timeout reichen nicht' in plan,
'L07_native_identity_discriminated':'execution_kind: native | comfy' in plan and 'bei native null' in plan,
'L07_origin_not_execution':'origin_generation_attempt_uuid bleibt ausschließlich Medienherkunft' in plan,
'L07_native_DSP_not_fake_model':'Native-DSP ohne Modell ausdrücklich not_applicable' in plan,
'implementation_not_marked_complete':not(p/'.completed').exists() and not(p/'.qc-passed').exists(),
}
result={'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kind':'executed document/hash checks only; semantic coverage separately peer reviewed','checks':checks,'passed':sum(checks.values()),'failed':[k for k,v in checks.items() if not v],'structural_checks':json.loads((a/'final-structural.json').read_text())['passed'],'normative_files':m5['files'],'skill_verdict':'separate independent review required'}
(a/'final-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'loop_checks':len(checks),'passed':sum(checks.values()),'failed':result['failed']},ensure_ascii=False))
if result['failed']: raise SystemExit(1)
