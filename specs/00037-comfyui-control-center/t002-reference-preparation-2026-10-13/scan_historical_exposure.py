from pathlib import Path
import subprocess,json,collections
OUT=Path(__file__).parent;ROOT=OUT.parent
rows=json.loads((ROOT/'t002-selection-2026-10-13/inventory.json').read_text(encoding='utf-8'))
lookup=collections.defaultdict(set)
for i,r in enumerate(rows):
 for pattern in (Path(r['path']).name,r['sha256'],r['sha256'][:16]):lookup[pattern].add(i)
pat=OUT/'historical-search-patterns.txt';pat.write_text('\n'.join(lookup)+'\n',encoding='utf-8')
cmd=['rg','--no-ignore','--hidden','--json','-F','-f',str(pat),'--glob','!00037-comfyui-control-center/**','--glob','!**/00037-comfyui-control-center/**','--glob','!**/.git/**','docs','specs','scripts','Tests','src','backend']
p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace');hits=collections.defaultdict(list);counts=collections.Counter()
for line in p.stdout:
 try:msg=json.loads(line)
 except ValueError:continue
 if msg.get('type')!='match':continue
 d=msg['data'];path=d['path'].get('text','');matched=set()
 for sm in d['submatches']:
  token=sm['match'].get('text','')
  for i in lookup.get(token,[]):matched.add(i)
 for i in matched:
  counts[i]+=1
  if len(hits[i])<12:hits[i].append({'evidence_path':path,'line':d['line_number'],'excerpt':d['lines'].get('text','').strip()[:700]})
err=p.stderr.read();code=p.wait()
result={'command':cmd,'exit':code,'stderr':err,'scope':'searchable repository text only; excludes Spec00037 to avoid self-evidence; no product DB, external sessions, binary archives, or user private use inspected','sources':[{'index':i,'path':r['path'],'sha256':r['sha256'],'match_lines':counts[i],'status':'historical_reference_found_not_automatically_execution_proof' if counts[i] else 'NO_TEXT_HIT_NOT_PROOF_OF_UNUSED','examples':hits[i]} for i,r in enumerate(rows)]}
(OUT/'historical-text-scan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('rg exit',code,'stderr',err[:200]);print('video name/hash hits',sum(counts[i]>0 for i,r in enumerate(rows) if r['role']=='video'),'of416')
for i,r in enumerate(rows):
 if r['role']=='video' and not counts[i] and i<220:print('candidate',i,Path(r['path']).name)
