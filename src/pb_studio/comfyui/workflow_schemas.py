"""Immutable, JSON-only workflow contracts. No workflow executes in this module."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
import re

class WorkflowError(ValueError):
    """Invalid or unsupported local workflow contract."""

class RegistryConflict(WorkflowError):
    """Stale activation, revision collision or changed idempotency payload."""


def canonical(value):
    def check(x,depth=0):
        if depth>64: raise WorkflowError('JSON nesting limit exceeded')
        if isinstance(x,str):
            try: x.encode('utf-8')
            except UnicodeError as exc: raise WorkflowError('Invalid Unicode') from exc
        elif isinstance(x,dict):
            for k,v in x.items():
                if not isinstance(k,str): raise WorkflowError('JSON object keys must be strings')
                check(k,depth+1);check(v,depth+1)
        elif isinstance(x,list):
            for v in x:check(v,depth+1)
        elif x is not None and type(x) not in (int,float,bool): raise WorkflowError('JSON values required')
    check(value)
    try:
        text=json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if len(text.encode('utf-8'))>8_388_608: raise WorkflowError('Workflow contract too large')
        return text
    except (TypeError, ValueError) as exc:
        raise WorkflowError('Contract must contain finite JSON values') from exc


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise WorkflowError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(WorkflowError('Non-finite JSON')))


@dataclass(frozen=True)
class WorkflowRevisionKey:
    workflow_id: str
    revision: int
    bundle_hash: str


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    expected: str
    observed: str


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    issues: tuple[ValidationIssue, ...] = ()
    discovery_generation: int | None = None
    profile_binding: str = "unqualified"
    execution_ready: bool = False


@dataclass(frozen=True)
class WorkflowActivationReceipt:
    key: WorkflowRevisionKey
    enabled: bool
    activation_revision: int
    registry_generation: str
    activation_token: str


@dataclass(frozen=True)
class DispatchAuthorization:
    key: WorkflowRevisionKey
    registry_generation: str
    authorization_id: str
    client_request_id: str


@dataclass(frozen=True, init=False)
class WorkflowBundle:
    """Canonical JSON backing prevents mutation through nested dictionaries."""
    _json: str

    def __init__(self, data):
        object.__setattr__(self, '_json', canonical(data))
        validate_structure(self)

    @classmethod
    def from_dict(cls, data):
        return cls(data)

    def to_dict(self):
        return strict_json(self._json)

    @property
    def manifest(self):
        return self.to_dict()['manifest']

    @property
    def api_prompt(self):
        return self.to_dict()['api_prompt']

    @property
    def key(self):
        m = self.manifest
        return WorkflowRevisionKey(m['workflow_id'], m['revision'], hashlib.sha256(self._json.encode('utf-8')).hexdigest())


def _require(condition, message):
    if not condition:
        raise WorkflowError(message)


def validate_structure(bundle):
    d = bundle.to_dict()
    _require(isinstance(d, dict) and set(d) <= {'manifest','api_prompt','ui_graph','test_fixture','parameter_normalization'}, 'Unknown bundle field')
    m, graph = d.get('manifest'), d.get('api_prompt')
    _require(isinstance(m, dict) and isinstance(graph, dict) and graph, 'Manifest and API prompt required')
    required = {'manifest_schema','workflow_id','revision','api_prompt_sha256','capabilities','result_adapter','execution_location','node_requirements','parameter_bindings','output_bindings','network_policy','model_bundle','server_profile','resource_profile','quality_profile','reproducibility_level','provenance'}
    _require(required <= set(m), 'Missing manifest fields')
    _require(set(m) <= required | {'shape_constraints'}, 'Unknown manifest field')
    _require(type(m['manifest_schema']) is int and m['manifest_schema']==1, 'Unsupported manifest schema')
    _require(isinstance(m['workflow_id'],str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',m['workflow_id']), 'Invalid workflow ID')
    _require(type(m['revision']) is int and m['revision']>0, 'Invalid revision')
    _require(m['api_prompt_sha256']==digest(graph), 'API prompt hash mismatch')
    _require(m['result_adapter']=='comfy.files.v1', 'unsupported_output_contract')
    _require(m['execution_location'] in ('local','unknown'), 'Invalid execution location')
    _require(m['reproducibility_level']=='traceable', 'Measured reproducibility levels require future qualification')
    _require(isinstance(m['provenance'],str) and m['provenance'].strip(), 'Workflow provenance required')
    _require(isinstance(m['capabilities'],list) and m['capabilities'] and all(isinstance(x,str) and x for x in m['capabilities']), 'Capabilities required')
    for field in ('model_bundle','node_requirements','parameter_bindings','output_bindings'):
        _require(isinstance(m[field],list), 'Manifest list required: '+field)
    for field in ('server_profile','resource_profile','quality_profile'):
        _require(m[field] is None or isinstance(m[field],str) and bool(m[field].strip()), 'Invalid profile')
    model_slots=set()
    for model in m['model_bundle']:
        _require(isinstance(model,dict) and set(model)=={'role','name','sha256'},'Invalid model requirement')
        _require(all(isinstance(model[k],str) and model[k] for k in ('role','name')),'Model role/name required')
        _require((model['role'],model['name']) not in model_slots,'Duplicate model requirement')
        model_slots.add((model['role'],model['name']))
        _require(model['sha256'] is None or isinstance(model['sha256'],str) and re.fullmatch('[a-f0-9]{64}',model['sha256']),'Invalid model content hash')
    requirements = {}
    for r in m['node_requirements']:
        _require(isinstance(r,dict) and set(r)=={'class_type','schema_sha256','inputs','outputs','package_identity','raw_schema'}, 'Node schema fields invalid')
        _require(isinstance(r['class_type'],str) and r['class_type'] and r['class_type'] not in requirements, 'Duplicate/invalid node requirement')
        _require(isinstance(r['schema_sha256'],str) and re.fullmatch('[a-f0-9]{64}',r['schema_sha256']), 'Node schema hash required')
        _require(isinstance(r['inputs'],dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in r['inputs'].items()) and isinstance(r['outputs'],list) and all(isinstance(x,str) for x in r['outputs']), 'Invalid static node schema')
        _require(r['package_identity'] is None or isinstance(r['package_identity'],str), 'Invalid package identity')
        raw=r['raw_schema']
        _require(isinstance(raw,dict) and isinstance(raw.get('input'),dict) and isinstance(raw.get('output'),list), 'Raw node schema required')
        raw_hash=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',', ':'),ensure_ascii=True,allow_nan=False).encode('utf-8')).hexdigest()
        _require(raw_hash==r['schema_sha256'], 'Raw node schema hash mismatch')
        _require(set(raw['input']) <= {'required','optional','hidden'}, 'Dynamic input groups unsupported')
        declared={}
        for group in ('required','optional'):
            fields=raw['input'].get(group,{})
            _require(isinstance(fields,dict),'Invalid raw input schema')
            for name,contract in fields.items():
                _require(isinstance(contract,list) and contract and isinstance(contract[0],str), 'Dynamic/enum schema needs qualified adapter')
                _require(name not in declared,'Duplicate raw input slot')
                declared[name]=contract[0]
        _require(declared==r['inputs'] and raw['output']==r['outputs'],'Declared slots diverge from bound raw schema')
        requirements[r['class_type']]=r
    edges={k:[] for k in graph}
    for node_id,node in graph.items():
        _require(isinstance(node_id,str) and node_id and isinstance(node,dict) and set(node)<= {'class_type','inputs','_meta'} and {'class_type','inputs'}<=set(node), 'UI graph or malformed API node')
        _require(node['class_type'] in requirements, 'Undeclared node class')
        schema=requirements[node['class_type']]
        _require(isinstance(node['inputs'],dict) and set(schema['raw_schema']['input'].get('required',{}))<=set(node['inputs'])<=set(schema['inputs']), 'Missing/unknown input slot')
        for name,value in node['inputs'].items():
            typ=schema['inputs'][name]
            if isinstance(value,list):
                _require(len(value)==2 and isinstance(value[0],str) and type(value[1]) is int, 'Unsupported literal list or malformed graph link')
                source,index=value
                _require(source in graph and index>=0 and isinstance(graph[source],dict) and graph[source].get('class_type') in requirements, 'Invalid graph reference')
                outputs=requirements[graph[source]['class_type']]['outputs']
                _require(index<len(outputs) and outputs[index]==typ, 'Output index/type mismatch')
                edges[node_id].append(source)
            else:
                validate_literal(value,typ,raw_input_contract(schema,name))
    visited=set(); active=set()
    def visit(n,depth=0):
        _require(depth<=64,'Graph dependency depth unsupported')
        _require(n not in active,'Graph cycle unsupported')
        if n in visited: return
        active.add(n)
        for source in edges[n]: visit(source,depth+1)
        active.remove(n); visited.add(n)
    for n in graph: visit(n)
    seen=set(); targets=set()
    for b in m['parameter_bindings']:
        _require(isinstance(b,dict) and {'semantic_name','node_id','input_name','type'}<=set(b) and set(b)<= {'semantic_name','node_id','input_name','type','min','max','multiple','default','choices','random'}, 'Invalid parameter binding')
        name=b['semantic_name']; target=(b['node_id'],b['input_name'])
        _require(isinstance(name,str) and name and name not in seen and target not in targets, 'Duplicate parameter binding')
        _require(b['type'] in ('INT','FLOAT','STRING','BOOLEAN'),'Unsupported parameter type')
        for constraint in ('min','max'):
            if constraint in b: _require(type(b[constraint]) in (int,float) and math.isfinite(b[constraint]) and b['type'] in ('INT','FLOAT'),'Invalid numeric bound')
        if 'min' in b and 'max' in b: _require(b['min']<=b['max'],'Inverted parameter bounds')
        if 'multiple' in b: _require(type(b['multiple']) is int and b['multiple']>0 and b['type']=='INT','Invalid integer multiple')
        if 'random' in b: _require(type(b['random']) is bool and b['type']=='INT','Invalid random policy')
        if 'choices' in b: _require(isinstance(b['choices'],list) and b['choices'] and all(matches_type(v,b['type']) for v in b['choices']),'Invalid choices')
        if 'default' in b: _require(matches_type(b['default'],b['type']) or b['default']=='random' and b.get('random') is True,'Invalid default')
        seen.add(name); targets.add(target)
        _require(b['node_id'] in graph and b['input_name'] in graph[b['node_id']]['inputs'], 'Parameter slot missing')
        _require(not isinstance(graph[b['node_id']]['inputs'][b['input_name']],list), 'Cannot replace graph link')
        _require(b['type']==requirements[graph[b['node_id']]['class_type']]['inputs'][b['input_name']], 'Parameter type mismatch')
    slots=set()
    _require(bool(m['output_bindings']), 'Output contract required')
    for b in m['output_bindings']:
        _require(isinstance(b,dict) and set(b)=={'slot_id','ordinal','node_id','field','family','required'}, 'Invalid output binding')
        _require(isinstance(b['slot_id'],str) and b['slot_id'] and type(b['ordinal']) is int and b['ordinal']>=0 and type(b['required']) is bool, 'Invalid output slot')
        _require(b['node_id'] in graph and b['field'] in ('images','audio','gifs','videos') and b['family'] in ('image','audio','video'), 'Unsupported output binding')
        _require({'images':'image','audio':'audio','gifs':'video','videos':'video'}[b['field']]==b['family'],'Output family mismatch')
        _require((b['slot_id'],b['ordinal']) not in slots,'Duplicate output slot')
        slots.add((b['slot_id'],b['ordinal']))


def matches_type(value, typ):
    if typ=='INT': return type(value) is int
    if typ=='FLOAT': return type(value) in (int,float) and math.isfinite(value)
    if typ=='STRING': return isinstance(value,str)
    if typ=='BOOLEAN': return type(value) is bool
    return False


def raw_input_contract(schema,name):
    for group in ('required','optional'):
        contract=schema['raw_schema']['input'].get(group,{}).get(name)
        if contract is not None:return contract
    raise WorkflowError('Input slot absent from raw schema')


def validate_literal(value,typ,contract):
    _require(matches_type(value,typ),'Literal input type mismatch')
    options=contract[1] if len(contract)>1 else {}
    _require(isinstance(options,dict),'Invalid raw input options')
    for field in ('min','max','step'):
        if field in options:
            bound=options[field]
            _require(typ in ('INT','FLOAT') and type(bound) in (int,float) and math.isfinite(bound),'Invalid raw numeric constraint')
            if field=='min':_require(value>=bound,'Raw input minimum violated')
            if field=='max':_require(value<=bound,'Raw input maximum violated')
            if field=='step':
                _require(bound>0,'Invalid raw step')
                from fractions import Fraction
                _require((Fraction(str(value))-Fraction(str(options.get('min',0))))%Fraction(str(bound))==0,'Raw input step violated')
    if 'choices' in options:_require(isinstance(options['choices'],list) and value in options['choices'],'Raw input choices violated')
