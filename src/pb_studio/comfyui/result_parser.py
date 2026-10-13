"""Pure parsing of correlated remote evidence; no download/import/readiness claim."""
from dataclasses import dataclass
import re
import uuid
from .schemas import EndpointIdentity
from .workflow_schemas import WorkflowError

@dataclass(frozen=True)
class OutputReference:
    attempt_uuid: str
    endpoint: EndpointIdentity
    prompt_id: str
    slot_id: str
    ordinal: int
    filename: str
    subfolder: str
    type: str
    family: str


def validate_file_reference(value):
    if not isinstance(value,dict) or not {'filename','subfolder','type'}<=set(value): raise WorkflowError('Actual file receipt required')
    name,folder,kind=(value[x] for x in ('filename','subfolder','type'))
    if not isinstance(name,str) or not name or not isinstance(folder,str) or kind not in ('input','output','temp'): raise WorkflowError('Invalid file receipt')
    for text in (name,folder):
        if any(ord(c)<32 for c in text) or '\\' in text or ':' in text or '%' in text or text.startswith('/') or any(p in ('.','..') or p.endswith((' ','.')) for p in text.split('/') if p): raise WorkflowError('Unsafe file reference')
    reserved={'CON','PRN','AUX','NUL'} | {f'{prefix}{i}' for prefix in ('COM','LPT') for i in range(1,10)}
    if any(part.split('.')[0].upper() in reserved or any(c in part for c in '<>"|?*') for text in (name,folder) for part in text.split('/')): raise WorkflowError('Unsafe Windows file reference')
    if '/' in name or '//' in folder: raise WorkflowError('Unsafe file reference')
    return name,folder,kind


def parse_outputs(bundle, remote):
    """Parse with caller-injected durable expected_* context, NEVER remote assertions.

    endpoint/attempt_uuid are observer-bound provenance, not response JSON fields.
    expected_* values must come from persisted submission context. This pure helper
    cannot authenticate a caller; future transport owns building this envelope.
    """
    if not isinstance(remote,dict): raise WorkflowError('Remote evidence required')
    required=('attempt_uuid','expected_attempt_uuid','endpoint','expected_endpoint','prompt_id','expected_prompt_id','expected_workflow_key','status','outputs')
    if any(k not in remote for k in required): raise WorkflowError('Missing output ownership')
    for field in ('attempt_uuid','expected_attempt_uuid','prompt_id','expected_prompt_id'):
        try:
            if not isinstance(remote[field],str) or str(uuid.UUID(remote[field]))!=remote[field]: raise ValueError()
        except ValueError as exc: raise WorkflowError('Canonical UUID ownership required') from exc
    if not isinstance(remote['endpoint'],EndpointIdentity) or not isinstance(remote['expected_endpoint'],EndpointIdentity): raise WorkflowError('Typed endpoint binding required')
    if remote['endpoint']!=remote['expected_endpoint'] or remote['prompt_id']!=remote['expected_prompt_id'] or remote['attempt_uuid']!=remote['expected_attempt_uuid'] or remote['expected_workflow_key']!=bundle.key: raise WorkflowError('Output ownership mismatch')
    status=remote['status']
    if not isinstance(status,dict) or status.get('status_str')!='success' or status.get('completed') is not True: raise WorkflowError('result_evidence_pending')
    if bundle.manifest['result_adapter']!='comfy.files.v1': raise WorkflowError('unsupported_output_contract')
    outputs=remote['outputs']
    if not isinstance(outputs,dict): raise WorkflowError('unsupported_output_contract')
    result=[]
    for b in bundle.manifest['output_bindings']:
        node=outputs.get(b['node_id'],{}); entries=node.get(b['field']) if isinstance(node,dict) else None
        if not isinstance(entries,list) or b['ordinal']>=len(entries):
            if b['required']: raise WorkflowError('Missing required output')
            continue
        name,folder,kind=validate_file_reference(entries[b['ordinal']])
        if kind!='output': raise WorkflowError('Canonical output must use output storage')
        result.append(OutputReference(remote['attempt_uuid'],remote['endpoint'],remote['prompt_id'],b['slot_id'],b['ordinal'],name,folder,kind,b['family']))
    return result
