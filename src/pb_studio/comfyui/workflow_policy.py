"""Offline local-only policy contracts. No sandbox, network, audit or execution.

A manifest is untrusted. Optional evidence is accepted only through an explicitly
injected trusted verifier, supplied by future audit/qualification code, never by
workflow metadata. Even an accepted policy is not G1 and never execution_ready.
"""
from __future__ import annotations
import ipaddress
import re
from typing import Callable, Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field
from .schemas import EndpointIdentity
from .workflow_schemas import WorkflowBundle, ValidationReport, ValidationIssue, digest

_SHA = r"^[a-f0-9]{64}$"
_SECRET_KEY = re.compile(r"^(?:.*[_-])?(?:api[_-]?key|access[_-]?token|authorization|password|passwd|secret|credential|private[_-]?key|client[_-]?secret|token|capability)$",re.I)
_TEXT_SECRET = re.compile(r"(?:authorization|api[_ -]?key|access[_ -]?token|password|secret|credential|capability)[\"']?\s*[:=]\s*\S+|\bbearer\s+\S+", re.I)
_URL = re.compile(r"https?://[^\s\"'<>]+",re.I)

class PolicyEvidence(BaseModel):
    model_config=ConfigDict(frozen=True,extra="forbid",strict=True)
    mode: Literal["audited_frozen","enforced"]
    audit_receipt_sha256: str = Field(pattern=_SHA)
    scope_sha256: str = Field(pattern=_SHA)
    runtime_sha256: str = Field(pattern=_SHA)
    mutators_frozen: bool = False
    pre_enqueue_after_mutations: bool = False
    egress_enforced: bool = False

def policy_scope_digest(bundle: WorkflowBundle, endpoint: EndpointIdentity) -> str:
    return digest({"bundle_hash":bundle.key.bundle_hash,"endpoint":endpoint.model_dump(mode="json")})

def _local_host(host):
    if host=="localhost":return True
    try:return ipaddress.ip_address(host).is_loopback
    except (ValueError,TypeError):return False

def check_workflow_policy(bundle: WorkflowBundle, endpoint: EndpointIdentity, *,
                          evidence: PolicyEvidence | None = None,
                          evidence_verifier: Callable[[PolicyEvidence], bool] | None = None,
                          observed_runtime_sha256: str | None = None,
                          effective_prompt: dict | None = None) -> ValidationReport:
    """Pure checks. None verifier/effective identity means unqualified, not success."""
    issues=[]
    def issue(code,path="manifest",expected="verified local-only contract",observed="unverified"):
        issues.append(ValidationIssue(code,path,expected,observed))
    manifest=bundle.manifest
    network=manifest.get("network_policy")
    if manifest.get("execution_location")!="local":issue("execution_location_unknown")
    if not isinstance(network,dict):
        issue("invalid_network_policy");network={}
    if set(network)-{"mode","allowed_hosts","redirects_allowed","external_calls"}:issue("untrusted_policy_fields")
    mode=network.get("mode")
    if mode not in ("declared_only","audited_frozen","enforced"):issue("unknown_assurance_mode")
    if network.get("redirects_allowed") is not False:issue("redirects_not_prohibited")
    if network.get("external_calls") is not False:issue("external_calls_not_prohibited")
    hosts=network.get("allowed_hosts")
    if not isinstance(hosts,list) or not all(isinstance(h,str) and _local_host(h) for h in hosts):issue("external_host_allowed")
    def canonical_host(host):
        if host=="localhost":return "127.0.0.1"
        try:return ipaddress.ip_address(host).compressed
        except (ValueError,TypeError):return None
    allowed={canonical_host(h) for h in hosts if isinstance(h,str)} if isinstance(hosts,list) else set()
    stack=[(manifest,0),(bundle.api_prompt,0)];count=0
    while stack:
        value,depth=stack.pop();count+=1
        if count>100000 or depth>48:
            issue("policy_structure_limit");break
        if isinstance(value,dict):
            for key,child in value.items():
                if isinstance(key,str) and _SECRET_KEY.fullmatch(key):issue("secret_material",observed="redacted")
                stack.append((child,depth+1))
        elif isinstance(value,(list,tuple)):
            stack.extend((child,depth+1) for child in value)
        elif isinstance(value,str):
            if _TEXT_SECRET.search(value):issue("secret_material",observed="redacted")
            for match in _URL.finditer(value):
                try:
                    url=urlsplit(match.group(0));host=url.hostname
                    if url.username is not None or url.password is not None:issue("url_credentials",observed="redacted")
                    if not _local_host(host):issue("external_url")
                    elif canonical_host(host) not in allowed:issue("local_url_not_allowed")
                    if url.query or url.fragment:issue("unqualified_url_parameters")
                except ValueError:issue("invalid_url")
    binding="unqualified"
    if mode=="declared_only":issue("permission_execution_identity_unverified")
    elif mode in ("audited_frozen","enforced"):
        verified=False
        if isinstance(evidence,PolicyEvidence) and evidence_verifier is not None:
            try:verified=evidence_verifier(evidence) is True
            except Exception:verified=False
        if not verified:
            issue("audit_evidence_unverified")
        else:
            if evidence.mode!=mode or evidence.scope_sha256!=policy_scope_digest(bundle,endpoint):issue("profile_scope_changed")
            if observed_runtime_sha256 is None:issue("runtime_identity_unknown")
            elif observed_runtime_sha256!=evidence.runtime_sha256:issue("runtime_identity_changed")
            if effective_prompt is None:issue("effective_identity_unknown")
            else:
                try:
                    if digest(effective_prompt)!=digest(bundle.api_prompt):issue("effective_graph_changed")
                except (ValueError,TypeError,RecursionError,UnicodeError):issue("invalid_effective_graph")
            if mode=="audited_frozen" and not evidence.mutators_frozen:issue("mutators_not_frozen")
            if mode=="enforced" and not (evidence.pre_enqueue_after_mutations and evidence.egress_enforced):issue("enforcement_unverified")
            if not issues:binding=mode
    # Do not echo remote/input values or caller-provided exception messages.
    unique=tuple(dict.fromkeys(issues))
    return ValidationReport(valid=not unique,issues=unique,discovery_generation=endpoint.discovery_generation,
                            profile_binding=binding,execution_ready=False)
