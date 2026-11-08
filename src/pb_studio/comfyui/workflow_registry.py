"""Caller-owned durable JSON registry. No product DB, scheduler or network access.

Dispatch authorization is a LOCAL receipt, not permission to send: future scheduler
must additionally prove admission, trust, qualification, restore fence and ownership.
"""
from contextlib import contextmanager
from dataclasses import asdict
import os
from pathlib import Path
import tempfile
import threading
import uuid
from .workflow_schemas import (WorkflowBundle,WorkflowRevisionKey,WorkflowActivationReceipt,
    DispatchAuthorization,ValidationReport,ValidationIssue,WorkflowError,RegistryConflict,canonical,strict_json,digest)

_LOCKS={}; _LOCKS_GUARD=threading.Lock()

class WorkflowRegistry:
    def __init__(self,path,inventory=None):
        self.path=Path(path).absolute(); self.inventory=inventory
        if not self.path.parent.is_dir(): raise WorkflowError('Caller must create registry directory explicitly')
        with _LOCKS_GUARD: self._mutex=_LOCKS.setdefault(str(self.path).casefold(),threading.RLock())
        self.lock_path=self.path.with_suffix(self.path.suffix+'.lock')
        # A missing store with an existing lock sidecar is NOT silently reset.
        with self._locked() as first:
            if not self.path.exists():
                if not first: raise WorkflowError('Registry missing; explicit restore required')
                self._write({'schema':1,'generation':str(uuid.uuid4()),'bundles':{},'activation':{},'requests':{},'dispatch':{}})
            self._read()

    @contextmanager
    def _locked(self):
        with self._mutex:
            first=False
            try:
                fd=os.open(self.lock_path,os.O_CREAT|os.O_EXCL|os.O_RDWR); first=True
                os.write(fd,b'0'); os.fsync(fd)
            except FileExistsError:
                fd=os.open(self.lock_path,os.O_RDWR)
            with os.fdopen(fd,'r+b') as handle:
                if os.name=='nt':
                    import msvcrt
                    handle.seek(0); msvcrt.locking(handle.fileno(),msvcrt.LK_LOCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX)
                try: yield first
                finally:
                    if os.name=='nt':
                        handle.seek(0); msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                    else: fcntl.flock(handle,fcntl.LOCK_UN)

    def _read(self):
        try:
            d=strict_json(self.path.read_text(encoding='utf-8'))
            if set(d)!={'schema','generation','bundles','activation','requests','dispatch'} or type(d['schema']) is not int or d['schema']!=1: raise ValueError()
            uuid.UUID(d['generation'])
            if not all(isinstance(d[k],dict) for k in ('bundles','activation','requests','dispatch')): raise ValueError()
            if set(d['bundles'])!=set(d['activation']): raise ValueError()
            for slot,b in d['bundles'].items():
                bundle=WorkflowBundle(b)
                if slot!=self._slot(bundle.key): raise ValueError()
                a=d['activation'][slot]
                if set(a)!={'key','enabled','activation_revision','registry_generation','activation_token'} or a['key']!=asdict(bundle.key) or type(a['enabled']) is not bool or type(a['activation_revision']) is not int or a['activation_revision']<0 or a['registry_generation']!=d['generation']: raise ValueError()
                uuid.UUID(a['activation_token'])
            def check_result(result):
                if not isinstance(result,dict): raise ValueError()
                fields=set(result)
                if fields=={'workflow_id','revision','bundle_hash'}:
                    key=WorkflowRevisionKey(**result)
                elif fields=={'key','enabled','activation_revision','registry_generation','activation_token'}:
                    key=WorkflowRevisionKey(**result['key'])
                    if type(result['enabled']) is not bool or type(result['activation_revision']) is not int or result['activation_revision']<0 or result['registry_generation']!=d['generation']:raise ValueError()
                    uuid.UUID(result['activation_token'])
                elif fields=={'key','registry_generation','authorization_id','client_request_id'}:
                    key=WorkflowRevisionKey(**result['key'])
                    uuid.UUID(result['registry_generation']);uuid.UUID(result['authorization_id']);uuid.UUID(result['client_request_id'])
                else: raise ValueError()
                if self._slot(key) not in d['bundles'] or WorkflowBundle(d['bundles'][self._slot(key)]).key!=key: raise ValueError()
            for rid,request in d['requests'].items():
                uuid.UUID(rid)
                if not isinstance(request,dict) or set(request)!={'fingerprint','result'} or not isinstance(request['fingerprint'],str) or len(request['fingerprint'])!=64 or any(c not in '0123456789abcdef' for c in request['fingerprint']): raise ValueError()
                check_result(request['result'])
            for aid,result in d['dispatch'].items():
                check_result(result)
                if result.get('authorization_id')!=aid:raise ValueError()
            return d
        except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
            raise WorkflowError('Registry corrupt or unavailable; explicit recovery required') from exc

    def _write(self,d):
        fd,name=tempfile.mkstemp(prefix=self.path.name+'.',suffix='.tmp',dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
                f.write(canonical(d)); f.flush(); os.fsync(f.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name): os.unlink(name)

    @staticmethod
    def _slot(key): return key.workflow_id+':'+str(key.revision)
    @staticmethod
    def _receipt(d): return WorkflowActivationReceipt(WorkflowRevisionKey(**d['key']),d['enabled'],d['activation_revision'],d['registry_generation'],d['activation_token'])
    @staticmethod
    def _request_id(value):
        try: return str(uuid.UUID(str(value)))
        except ValueError as exc: raise WorkflowError('client_request_id must be UUID') from exc
    def _existing(self,d,key):
        b=d['bundles'].get(self._slot(key))
        if b is None: raise WorkflowError('Unknown workflow revision')
        if WorkflowBundle(b).key!=key: raise RegistryConflict('Bundle hash mismatch')
        return b
    def _replay(self,d,rid,payload):
        old=d['requests'].get(rid)
        if old and old['fingerprint']!=digest(payload): raise RegistryConflict('Idempotency payload conflict')
        return old['result'] if old else None
    def validate(self,bundle,inventory=None):
        inventory=inventory or self.inventory; issues=[]
        if inventory is None or inventory.nodes is None:
            issues.append(ValidationIssue('inventory_unavailable','nodes','observed node inventory','unknown'))
        else:
            nodes={n.name:n for n in inventory.nodes}
            for r in bundle.manifest['node_requirements']:
                n=nodes.get(r['class_type'])
                if n is None or n.schema_state!='observed' or n.schema_sha256!=r['schema_sha256']:
                    issues.append(ValidationIssue('node_schema_mismatch','node_requirements','matching observed schema hash','missing or different'))
        observed_models={(model.role,model.name):model for model in (getattr(inventory,'models',None) or ())}
        for model in bundle.manifest['model_bundle']:
            found=observed_models.get((model['role'],model['name']))
            if found is None or found.identity_state in ('missing','invalid'):
                issues.append(ValidationIssue('model_missing','model_bundle','observed model','missing or invalid'))
            elif model['sha256'] is not None and (found.identity_state!='verified' or found.sha256!=model['sha256']):
                issues.append(ValidationIssue('model_identity_unverified','model_bundle','matching content hash','unknown or different'))
        return ValidationReport(not issues,tuple(issues),getattr(getattr(inventory,'endpoint',None),'discovery_generation',None))
    def register(self,bundle,client_request_id=None):
        if not isinstance(bundle,WorkflowBundle): raise WorkflowError('Validated WorkflowBundle required')
        report=self.validate(bundle)
        if not report.valid: raise WorkflowError('Observed node schema required for registration')
        rid=self._request_id(client_request_id or uuid.uuid4()); payload={'op':'register','bundle':bundle.to_dict()}
        with self._locked():
            d=self._read(); replay=self._replay(d,rid,payload)
            if replay: return WorkflowRevisionKey(**replay)
            key=bundle.key; slot=self._slot(key)
            if slot in d['bundles']:
                self._existing(d,key)
            else:
                revisions=[b['manifest']['revision'] for b in d['bundles'].values() if b['manifest']['workflow_id']==key.workflow_id]
                if revisions and key.revision<=max(revisions): raise RegistryConflict('Revision must increase monotonically')
                d['bundles'][slot]=bundle.to_dict()
                d['activation'][slot]=asdict(WorkflowActivationReceipt(key,False,0,d['generation'],str(uuid.uuid4())))
            result=asdict(key); d['requests'][rid]={'fingerprint':digest(payload),'result':result}; self._write(d); return key
    def get(self,key):
        with self._locked(): return WorkflowBundle(self._existing(self._read(),key))
    def activation(self,key):
        with self._locked():
            d=self._read(); self._existing(d,key); return self._receipt(d['activation'][self._slot(key)])
    def set_enabled(self,key,enabled,expected_activation_token,client_request_id):
        if type(enabled) is not bool: raise WorkflowError('enabled must be boolean')
        rid=self._request_id(client_request_id); payload={'op':'enable','key':asdict(key),'enabled':enabled,'token':expected_activation_token}
        with self._locked():
            d=self._read(); replay=self._replay(d,rid,payload)
            if replay: return self._receipt(replay)
            self._existing(d,key); old=d['activation'][self._slot(key)]
            if old['activation_token']!=expected_activation_token: raise RegistryConflict('Stale activation token')
            receipt=WorkflowActivationReceipt(key,enabled,old['activation_revision']+1,d['generation'],str(uuid.uuid4()))
            result=asdict(receipt); d['activation'][self._slot(key)]=result
            d['requests'][rid]={'fingerprint':digest(payload),'result':result}; self._write(d); return receipt
    def authorize_dispatch(self,key,expected_activation_token,client_request_id):
        rid=self._request_id(client_request_id); payload={'op':'authorize','key':asdict(key),'token':expected_activation_token}
        with self._locked():
            d=self._read(); replay=self._replay(d,rid,payload)
            if replay: return DispatchAuthorization(WorkflowRevisionKey(**replay['key']),replay['registry_generation'],replay['authorization_id'],replay['client_request_id'])
            self._existing(d,key); a=d['activation'][self._slot(key)]
            if a['activation_token']!=expected_activation_token or not a['enabled']: raise RegistryConflict('Workflow disabled or stale activation')
            receipt=DispatchAuthorization(key,d['generation'],str(uuid.uuid4()),rid); result=asdict(receipt)
            d['dispatch'][receipt.authorization_id]=result; d['requests'][rid]={'fingerprint':digest(payload),'result':result}; self._write(d); return receipt
    def rotate_generation_after_restore(self):
        """Explicit offline recovery fence; all revisions disabled, old tokens invalid.

        Caller must fence the future scheduler first. Cannot detect external rollback
        of every local file; this method is mandatory in future restore integration.
        Prior dispatch receipts remain historical; never become new send permission.
        """
        with self._locked():
            d=self._read();d['generation']=str(uuid.uuid4());d['requests']={}
            for slot,old in d['activation'].items():
                d['activation'][slot]=asdict(WorkflowActivationReceipt(WorkflowRevisionKey(**old['key']),False,old['activation_revision']+1,d['generation'],str(uuid.uuid4())))
            self._write(d)
            return d['generation']
