"""Isolated contract fixtures, not generated media or qualification evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import subprocess
import sys
import unittest
import uuid
from pb_studio.comfyui.workflow_schemas import WorkflowBundle, WorkflowError, RegistryConflict, digest
from pb_studio.comfyui.workflow_registry import WorkflowRegistry
from pb_studio.comfyui.workflow_parameters import resolve_parameters
from pb_studio.comfyui.result_parser import parse_outputs, validate_file_reference
from pb_studio.comfyui.capabilities import build_snapshot, canonical_json
from pb_studio.comfyui.schemas import EndpointIdentity


def fixture():
    raw={'input':{'required':{'text':['STRING'],'seed':['INT'],'width':['INT'],'height':['INT'],'frames':['INT']}},'output':['IMAGE']}
    prompt={'1':{'class_type':'ContractFixture','inputs':{'text':'fixture','seed':1,'width':64,'height':64,'frames':9}}}
    m={'manifest_schema':1,'workflow_id':'fixture','revision':1,'api_prompt_sha256':digest(prompt),'capabilities':['fixture.v1'],'result_adapter':'comfy.files.v1','execution_location':'local','provenance':'isolated unittest fixture, never qualified','reproducibility_level':'traceable','server_profile':None,'resource_profile':None,'quality_profile':None,'model_bundle':[],
       'network_policy':{'mode':'declared_only','allowed_hosts':[],'redirects_allowed':False,'external_calls':False},
       'node_requirements':[{'class_type':'ContractFixture','schema_sha256':hashlib.sha256(canonical_json(raw).encode()).hexdigest(),'inputs':{'text':'STRING','seed':'INT','width':'INT','height':'INT','frames':'INT'},'outputs':['IMAGE'],'package_identity':None,'raw_schema':raw}],
       'parameter_bindings':[{'semantic_name':'prompt','node_id':'1','input_name':'text','type':'STRING'},{'semantic_name':'seed','node_id':'1','input_name':'seed','type':'INT','min':0,'max':4294967295,'random':True},{'semantic_name':'width','node_id':'1','input_name':'width','type':'INT','min':8,'max':1024,'multiple':8},{'semantic_name':'height','node_id':'1','input_name':'height','type':'INT','min':8,'max':1024,'multiple':8},{'semantic_name':'frames','node_id':'1','input_name':'frames','type':'INT','min':1,'max':129}],
       'shape_constraints':{'width':'width','height':'height','frames':'frames','max_pixels':1048576,'max_pixel_frames':10485760,'frame_multiple':8,'frame_offset':1},
       'output_bindings':[{'slot_id':'main','ordinal':0,'node_id':'1','field':'images','family':'image','required':True}]}
    return {'manifest':m,'api_prompt':prompt}


def inventory(data):
    return build_snapshot(endpoint=EndpointIdentity(endpoint_id='fixture',canonical_url='http://127.0.0.1:8188'),version='fixture',nodes={r['class_type']:r['raw_schema'] for r in data['manifest']['node_requirements']},model_names={},features={},extensions=())


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.data=fixture(); self.bundle=WorkflowBundle(self.data)
    def test_immutable_nested(self):
        self.data['api_prompt']['1']['inputs']['seed']=100
        returned=self.bundle.api_prompt;returned['1']['inputs']['seed']=200
        self.assertEqual(self.bundle.api_prompt['1']['inputs']['seed'],1)
    def test_ui_rejected(self):
        self.data['api_prompt']={'nodes':[]};self.data['manifest']['api_prompt_sha256']=digest(self.data['api_prompt'])
        with self.assertRaises(WorkflowError):WorkflowBundle(self.data)
    def test_hash_rejected(self):
        self.data['api_prompt']['1']['inputs']['seed']=2
        with self.assertRaises(WorkflowError):WorkflowBundle(self.data)
    def test_unknown_adapter(self):
        self.data['manifest']['result_adapter']='evil.module:execute'
        with self.assertRaises(WorkflowError):WorkflowBundle(self.data)
    def test_slot_invalid(self):
        self.data['manifest']['parameter_bindings'][0]['node_id']='unknown'
        with self.assertRaises(WorkflowError):WorkflowBundle(self.data)
    def test_forged_schema(self):
        self.data['manifest']['node_requirements'][0]['raw_schema']['output']=['INT']
        with self.assertRaises(WorkflowError):WorkflowBundle(self.data)
    def test_links_bad_index_type_cycle(self):
        for link in (['missing',0],['1',9],['1',0],['1',True]):
            with self.subTest(link=link):
                d=fixture();d['api_prompt']['1']['inputs']['seed']=link;d['manifest']['api_prompt_sha256']=digest(d['api_prompt'])
                with self.assertRaises(WorkflowError):WorkflowBundle(d)
    def test_resolve_only_slot(self):
        r=resolve_parameters(self.bundle,{'prompt':'new'})
        self.assertEqual(r.api_prompt['1']['inputs']['text'],'new');self.assertEqual(self.bundle.api_prompt['1']['inputs']['text'],'fixture')
    def test_random_persisted(self):
        r=resolve_parameters(self.bundle,{'seed':'random'});self.assertIs(type(r.values['seed']),int);self.assertEqual(r.values['seed'],r.api_prompt['1']['inputs']['seed'])
    def test_parameter_rejections(self):
        for values in ({'seed':True},{'seed':-1},{'width':65},{'frames':8},{'unknown':1},{'width':1024,'height':1024,'frames':129}):
            with self.subTest(values=values),self.assertRaises(WorkflowError):resolve_parameters(self.bundle,values)
    def test_output_success_ownership(self):
        r=self.remote();self.assertEqual(parse_outputs(self.bundle,r)[0].filename,'actual.png')
        for mutation in ({'status':{'completed':True}}, {'expected_prompt_id':'other'},{'outputs':{}}):
            with self.subTest(mutation=mutation),self.assertRaises(WorkflowError):parse_outputs(self.bundle,{**r,**mutation})
    def remote(self):
        attempt=str(uuid.uuid4());prompt=str(uuid.uuid4());endpoint=EndpointIdentity(endpoint_id='fixture',canonical_url='http://127.0.0.1:8188')
        return dict(attempt_uuid=attempt,expected_attempt_uuid=attempt,endpoint=endpoint,expected_endpoint=endpoint,prompt_id=prompt,expected_prompt_id=prompt,expected_workflow_key=self.bundle.key,status={'status_str':'success','completed':True},outputs={'1':{'images':[{'filename':'actual.png','subfolder':'owned','type':'output'}]}})

    def test_output_full_endpoint_and_attempt_binding(self):
        r=self.remote()
        for mutation in ({'expected_endpoint':r['endpoint'].model_copy(update={'discovery_generation':1})},{'expected_attempt_uuid':str(uuid.uuid4())},{'expected_workflow_key':None}):
            with self.subTest(mutation=mutation),self.assertRaises(WorkflowError):parse_outputs(self.bundle,{**r,**mutation})
    def test_unsafe_paths(self):
        for name in ('../a','C:a','a\\b','%2e%2e','a.','a\x00','/root'):
            with self.subTest(name=name),self.assertRaises(WorkflowError):validate_file_reference({'filename':name,'subfolder':'','type':'input'})
    def test_reserved_windows_paths_rejected(self):
        for name in ('CON.png','nul','LPT1.mp4','COM9.wav'):
            with self.subTest(name=name),self.assertRaises(WorkflowError):validate_file_reference({'filename':name,'subfolder':'','type':'input'})
    def test_upload_actual_reference(self):
        self.assertEqual(validate_file_reference({'filename':'server-renamed.png','subfolder':'input-sub','type':'input'}),('server-renamed.png','input-sub','input'))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'registry.json';self.data=fixture();self.bundle=WorkflowBundle(self.data);self.inv=inventory(self.data)
        self.registry=WorkflowRegistry(self.path,self.inv);self.key=self.registry.register(self.bundle)
    def tearDown(self):self.tmp.cleanup()
    def enable(self):return self.registry.set_enabled(self.key,True,self.registry.activation(self.key).activation_token,str(uuid.uuid4()))
    def test_durable_reopen(self):
        a=self.enable();other=WorkflowRegistry(self.path,self.inv);self.assertEqual(other.activation(self.key),a);self.assertEqual(other.get(self.key).key,self.key)
    def test_disabled_dispatch(self):
        with self.assertRaises(RegistryConflict):self.registry.authorize_dispatch(self.key,self.registry.activation(self.key).activation_token,str(uuid.uuid4()))
    def test_cas_replay_and_conflict(self):
        token=self.registry.activation(self.key).activation_token;rid=str(uuid.uuid4());a=self.registry.set_enabled(self.key,True,token,rid)
        self.assertEqual(a,self.registry.set_enabled(self.key,True,token,rid))
        with self.assertRaises(RegistryConflict):self.registry.set_enabled(self.key,False,token,rid)
        with self.assertRaises(RegistryConflict):self.registry.set_enabled(self.key,False,token,str(uuid.uuid4()))
    def test_disable_retains_pinned_receipt(self):
        a=self.enable();rid=str(uuid.uuid4());receipt=self.registry.authorize_dispatch(self.key,a.activation_token,rid)
        self.registry.set_enabled(self.key,False,a.activation_token,str(uuid.uuid4()))
        self.assertEqual(receipt,self.registry.authorize_dispatch(self.key,a.activation_token,rid))
        with self.assertRaises(RegistryConflict):self.registry.authorize_dispatch(self.key,a.activation_token,str(uuid.uuid4()))
    def test_concurrent_cas_one_winner(self):
        token=self.registry.activation(self.key).activation_token;results=[]
        def run():
            try:results.append(self.registry.set_enabled(self.key,True,token,str(uuid.uuid4())))
            except RegistryConflict:results.append('conflict')
        threads=[threading.Thread(target=run) for _ in range(4)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(results.count('conflict'),3)
    def test_crossprocess_cas_one_winner(self):
        token=self.registry.activation(self.key).activation_token
        code="""import sys,uuid
from pb_studio.comfyui.workflow_registry import WorkflowRegistry
from pb_studio.comfyui.workflow_schemas import WorkflowRevisionKey,RegistryConflict
r=WorkflowRegistry(sys.argv[1]);k=WorkflowRevisionKey('fixture',1,sys.argv[3])
try:
 r.set_enabled(k,True,sys.argv[2],str(uuid.uuid4()));print('winner')
except RegistryConflict:print('conflict')
"""
        processes=[subprocess.Popen([sys.executable,'-c',code,str(self.path),token,self.key.bundle_hash],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        output=[]
        for process in processes:
            out,err=process.communicate(timeout=20);self.assertEqual(process.returncode,0,err);output.append(out.strip())
        self.assertEqual(sorted(output),['conflict','winner'])
    def test_revision_collision(self):
        self.data['manifest']['provenance']='different';other=WorkflowBundle(self.data)
        with self.assertRaises(RegistryConflict):self.registry.register(other)
    def test_corruption_failclosed(self):
        self.path.write_text('{}')
        with self.assertRaises(WorkflowError):WorkflowRegistry(self.path,self.inv)
        self.assertEqual(self.path.read_text(),'{}')
    def test_missing_store_no_reset(self):
        self.path.unlink()
        with self.assertRaises(WorkflowError):WorkflowRegistry(self.path,self.inv)
    def test_model_missing_and_hash_mismatch(self):
        d=fixture();d['manifest']['model_bundle']=[{'role':'checkpoint','name':'missing.safetensors','sha256':None}]
        with self.assertRaises(WorkflowError):self.registry.register(WorkflowBundle(d))
        inv=build_snapshot(endpoint=self.inv.endpoint,version='fixture',nodes={'ContractFixture':d['manifest']['node_requirements'][0]['raw_schema']},model_names={'checkpoint':['missing.safetensors']},features={},extensions=())
        r=WorkflowRegistry(Path(self.tmp.name)/'models.json',inv)
        self.assertFalse(r.validate(WorkflowBundle(d)).execution_ready)
        d['manifest']['model_bundle'][0]['sha256']='a'*64
        with self.assertRaises(WorkflowError):r.register(WorkflowBundle(d))
    def test_corrupt_replay_result_rejected(self):
        rid=str(uuid.uuid4());self.registry.register(self.bundle,rid)
        d=json.loads(self.path.read_text());d['requests'][rid]['result']={'enabled':True};self.path.write_text(json.dumps(d))
        with self.assertRaises(WorkflowError):self.registry.register(self.bundle,rid)
    def test_restore_rotates_tokens(self):
        a=self.enable();generation=self.registry.rotate_generation_after_restore()
        current=self.registry.activation(self.key)
        self.assertNotEqual(generation,a.registry_generation);self.assertFalse(current.enabled)
        with self.assertRaises(RegistryConflict):self.registry.authorize_dispatch(self.key,a.activation_token,str(uuid.uuid4()))
    def test_valid_optional_omitted(self):
        d=fixture();r=d['manifest']['node_requirements'][0]
        r['raw_schema']['input']['optional']={'optional':['STRING']};r['inputs']['optional']='STRING'
        r['schema_sha256']=hashlib.sha256(canonical_json(r['raw_schema']).encode()).hexdigest()
        self.assertTrue(WorkflowBundle(d))
    def test_raw_constraints_cannot_be_widened(self):
        d=fixture();r=d['manifest']['node_requirements'][0];r['raw_schema']['input']['required']['width']=['INT',{'min':8,'max':64,'step':8}]
        r['schema_sha256']=hashlib.sha256(canonical_json(r['raw_schema']).encode()).hexdigest()
        b=WorkflowBundle(d)
        with self.assertRaises(WorkflowError):resolve_parameters(b,{'width':128})
        d['api_prompt']['1']['inputs']['width']=128;d['manifest']['api_prompt_sha256']=digest(d['api_prompt'])
        with self.assertRaises(WorkflowError):WorkflowBundle(d)
    def test_output_family_mismatch(self):
        d=fixture();d['manifest']['output_bindings'][0]['family']='video'
        with self.assertRaises(WorkflowError):WorkflowBundle(d)
    def test_constraint_schema_invalid(self):
        d=fixture();d['manifest']['parameter_bindings'][1]['min']='wrong'
        with self.assertRaises(WorkflowError):WorkflowBundle(d)
    def test_unicode_schema_identity(self):
        d=fixture();r=d['manifest']['node_requirements'][0];r['raw_schema']['description']='ÄÖÜ'
        r['schema_sha256']=hashlib.sha256(canonical_json(r['raw_schema']).encode()).hexdigest()
        registry=WorkflowRegistry(Path(self.tmp.name)/'unicode.json',inventory(d));self.assertEqual(registry.register(WorkflowBundle(d)).workflow_id,'fixture')
    def test_inventory_hash_required(self):
        with self.assertRaises(WorkflowError):WorkflowRegistry(Path(self.tmp.name)/'other.json').register(self.bundle)

if __name__=='__main__':unittest.main()
