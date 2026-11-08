"""Offline policy and actual extracted SSE emitter contracts; no backend startup."""
import ast
import asyncio
import logging
from pathlib import Path
from typing import Any
import pytest
from pb_studio.comfyui.log_redaction import redact_log_value

@pytest.mark.parametrize("value", [
    {"nested": [{"api_key": "SECRET1"}, {"Authorization": "Bearer SECRET2"}]},
    '{"password":"SECRET3"}',
    "request https://user:SECRET4@localhost:8188/path",
    "redirect https://example.test/path?access_token=SECRET5",
    "bad JSON {password: SECRET6",
    "Authorization: Bearer SECRET7",
])
def test_secret_values_never_leave_redactor(value):
    result = str(redact_log_value(value))
    assert "SECRET" not in result

def test_ordinary_log_preserved():
    assert redact_log_value("Job complete: 2 outputs") == "Job complete: 2 outputs"

def test_bounds_and_cycles_fail_closed():
    cycle = {}; cycle["cycle"] = cycle
    assert "TRUNCATED" in str(redact_log_value(cycle))
    assert "TRUNCATED" in str(redact_log_value("x"*100000))

def emitter_namespace():
    tree = ast.parse(Path("backend/dependencies.py").read_text(encoding="utf-8"))
    nodes = [x for x in tree.body if isinstance(x, (ast.ClassDef, ast.AsyncFunctionDef)) and x.name in ("publish_log", "SSELogHandler")]
    calls=[]
    async def publish(event, data): calls.append((event,data))
    def publish_sync(event, data): calls.append((event,data))
    namespace={"logging":logging,"Any":Any,"publish_event":publish,"publish_event_threadsafe":publish_sync,"redact_log_value":redact_log_value}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),"backend/dependencies.py","exec"),namespace)
    return namespace,calls

def test_actual_publish_log_redacts_before_publish():
    ns,calls=emitter_namespace()
    asyncio.run(ns["publish_log"]("password=SECRET",detail="api_key=SECRET2",source="token=SECRET3"))
    assert len(calls)==1
    assert "SECRET" not in str(calls)

def test_actual_logging_handler_redacts_without_mutating_record():
    ns,calls=emitter_namespace()
    record=logging.LogRecord("worker",logging.INFO,"x",1,"Authorization: Bearer %s",("SECRET",),None)
    ns["SSELogHandler"]().emit(record)
    assert len(calls)==1
    assert "SECRET" not in str(calls)
    assert record.args==("SECRET",)


from types import SimpleNamespace
from pb_studio.comfyui.schemas import EndpointIdentity
from pb_studio.comfyui.workflow_policy import check_workflow_policy, PolicyEvidence, policy_scope_digest
from pb_studio.comfyui.workflow_schemas import digest

def policy_bundle(**changes):
    manifest={"execution_location":"local","server_profile":"pinned-runtime", "network_policy":{"mode":"declared_only","allowed_hosts":[],"redirects_allowed":False,"external_calls":False}}
    manifest.update(changes)
    graph={"1":{"class_type":"LocalNode","inputs":{"seed":1}}}
    return SimpleNamespace(manifest=manifest,api_prompt=graph,key=SimpleNamespace(bundle_hash=digest({"manifest":manifest,"api_prompt":graph})))

def ep(): return EndpointIdentity(endpoint_id="local",canonical_url="http://127.0.0.1:8188")

def test_declaration_never_qualifies():
    report=check_workflow_policy(policy_bundle(),ep())
    assert not report.valid and not report.execution_ready
    assert "permission_execution_identity_unverified" in [i.code for i in report.issues]

def test_untrusted_manifest_cannot_self_attest():
    b=policy_bundle(network_policy={"mode":"enforced","allowed_hosts":[],"redirects_allowed":False,"external_calls":False,"verified":True})
    assert not check_workflow_policy(b,ep()).valid

def test_external_url_nested_secrets_and_redirect_rejected():
    b=policy_bundle(extra={"nested":[{"api_key":"SECRET"},"https://external.test/upload"]})
    r=check_workflow_policy(b,ep())
    assert not r.valid
    assert "SECRET" not in repr(r)
    codes=[i.code for i in r.issues]
    assert "secret_material" in codes and "external_url" in codes

def audited():
    b=policy_bundle(network_policy={"mode":"audited_frozen","allowed_hosts":[],"redirects_allowed":False,"external_calls":False})
    e=PolicyEvidence(mode="audited_frozen",audit_receipt_sha256="a"*64,scope_sha256=policy_scope_digest(b,ep()),runtime_sha256="b"*64,mutators_frozen=True)
    return b,e

def test_evidence_requires_trusted_verifier_and_matching_runtime():
    b,e=audited()
    assert not check_workflow_policy(b,ep(),evidence=e,observed_runtime_sha256="b"*64,effective_prompt=b.api_prompt).valid
    r=check_workflow_policy(b,ep(),evidence=e,evidence_verifier=lambda _:True,observed_runtime_sha256="b"*64,effective_prompt=b.api_prompt)
    assert r.valid and not r.execution_ready
    assert r.profile_binding=="audited_frozen"

def test_callback_graph_or_runtime_change_invalidates_evidence():
    b,e=audited()
    altered={"1":{"class_type":"RemoteNode","inputs":{"seed":2}}}
    for runtime,graph in [("b"*64,altered),("c"*64,b.api_prompt)]:
        r=check_workflow_policy(b,ep(),evidence=e,evidence_verifier=lambda _:True,observed_runtime_sha256=runtime,effective_prompt=graph)
        assert not r.valid

def test_missing_effective_identity_unknown():
    b,e=audited()
    r=check_workflow_policy(b,ep(),evidence=e,evidence_verifier=lambda _:True,observed_runtime_sha256="b"*64)
    assert not r.valid
    assert "effective_identity_unknown" in [i.code for i in r.issues]


def test_secret_bearing_dictionary_key_is_removed():
    assert "SECRET" not in str(redact_log_value({"https://user:SECRET@localhost": "normal"}))
    assert "SECRET" not in str(redact_log_value({"api_key=SECRET": "normal"}))

def test_escaped_credential_key_redacted():
    assert "VALUE123" not in str(redact_log_value(r'{"api\u005fkey":"VALUE123"}'))

def test_sensitive_key_budget_is_bounded():
    result=redact_log_value({"api_key_"+str(i):"value" for i in range(1000)})
    assert len(result)<=513


@pytest.mark.parametrize("text,code",[("Authorization: Bearer VALUE123","secret_material"),("http://127.0.0.2:9000/upload","local_url_not_allowed")])
def test_policy_scans_plain_credentials_and_honors_empty_host_allowlist(text,code):
    b,e=audited(); b.api_prompt["1"]["inputs"]["text"]=text
    r=check_workflow_policy(b,ep(),evidence=e,evidence_verifier=lambda _:True,observed_runtime_sha256="b"*64,effective_prompt=b.api_prompt)
    assert not r.valid
    assert code in [i.code for i in r.issues]
    assert "VALUE123" not in repr(r)

def test_enforced_requires_pre_enqueue_and_egress_proof():
    b=policy_bundle(network_policy={"mode":"enforced","allowed_hosts":[],"redirects_allowed":False,"external_calls":False})
    e=PolicyEvidence(mode="enforced",audit_receipt_sha256="a"*64,scope_sha256=policy_scope_digest(b,ep()),runtime_sha256="b"*64)
    r=check_workflow_policy(b,ep(),evidence=e,evidence_verifier=lambda _:True,observed_runtime_sha256="b"*64,effective_prompt=b.api_prompt)
    assert not r.valid and not r.execution_ready


def test_real_bundle_registry_policy_boundary(tmp_path):
    # Load only this pure test fixture, without importing global conftest/backend.
    import runpy
    from pb_studio.comfyui.workflow_schemas import WorkflowBundle
    from pb_studio.comfyui.workflow_registry import WorkflowRegistry
    fixture = runpy.run_path("Tests/test_comfyui_workflow_bundle.py")
    data = fixture["fixture"]()
    bundle = WorkflowBundle(data)
    registry = WorkflowRegistry(tmp_path / "registry.json", fixture["inventory"](data))
    key = registry.register(bundle)
    report = check_workflow_policy(registry.get(key), ep())
    assert not report.valid and not report.execution_ready
    assert report.profile_binding == "unqualified"
    assert "permission_execution_identity_unverified" in {i.code for i in report.issues}
