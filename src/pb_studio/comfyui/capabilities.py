"""Discovery interpretation, without guessing execution capabilities from names."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .schemas import (DiscoverySnapshot, EndpointIdentity, FeatureObservation,
                      ModelIdentity, ModelRoleInventory, NodeIdentity, SourceProfile)

# Reviewed local source, 2026-10-13. This is NOT attestation of a running server.
SOURCE_PROFILE = SourceProfile(
    revision='comfy-0.39.2-3c1b7a17-readonly-v1', version='0.39.2',
    source_commit='3c1b7a17fdf239d35ce98cc777756f572d089795',
    server_sha256='7dc4ca3bd801a64da1fe7c2d1af81da61999f6b96dd96637d456e0562e8ce40b',
    client_prompt_id_supported=True,
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def build_snapshot(*, endpoint: EndpointIdentity, version: str,
                   nodes: dict[str, Any] | None, model_names: dict[str, list[str]] | None,
                   features: dict[str, Any] | None, extensions: tuple[str, ...] | None,
                   reasons: tuple[str, ...] = (),
                   unavailable_model_roles: tuple[str, ...] = ()) -> DiscoverySnapshot:
    """Build presence evidence only; later gates own static/smoke/qualified states."""
    problems = list(reasons)
    profile = SOURCE_PROFILE if version == SOURCE_PROFILE.version else None
    if endpoint.profile_revision not in ('unqualified', SOURCE_PROFILE.revision) or (
        endpoint.profile_revision == SOURCE_PROFILE.revision and profile is None
    ):
        return DiscoverySnapshot(endpoint=endpoint, version=version, readiness='incompatible',
                                 reasons=tuple(problems + ['profile_version_mismatch']))
    if profile is None:
        problems.append('api_profile_unknown')
    problems.extend(('runtime_source_binding_unknown', 'server_boot_identity_unknown',
                     'custom_node_versions_unknown', 'model_content_identity_unknown',
                     'workflow_not_qualified'))
    node_results = None
    if nodes is not None:
        result = []
        for name, schema in sorted(nodes.items()):
            valid = (isinstance(schema, dict) and isinstance(schema.get('input'), dict)
                     and isinstance(schema.get('output'), list)
                     and all(isinstance(item, str) for item in schema['output']))
            digest = hashlib.sha256(canonical_json(schema).encode('utf-8')).hexdigest() if valid else None
            result.append(NodeIdentity(name=name, schema_sha256=digest, schema_state='observed' if valid else 'invalid'))
            if not valid:
                problems.append('node_schema_invalid')
        node_results = tuple(result)
        if not result:
            problems.append('nodes_missing')
    models = None if model_names is None else tuple(
        ModelIdentity(role=role, name=name) for role, names in sorted(model_names.items()) for name in sorted(set(names))
    )
    if models == () and not unavailable_model_roles:
        problems.append('models_missing')
    return DiscoverySnapshot(
        endpoint=endpoint, version=version, profile_revision=profile.revision if profile else 'unqualified',
        profile_source_sha256=profile.server_sha256 if profile else None,
        profile_binding='source_candidate' if profile else 'unqualified',
        nodes=node_results, models=models,
        model_roles=None if model_names is None else tuple(
            [ModelRoleInventory(role=role, names=tuple(sorted(set(names))), state='observed')
             for role, names in sorted(model_names.items())]
            + [ModelRoleInventory(role=role, names=None, state='unavailable')
               for role in sorted(set(unavailable_model_roles))]),
        features=None if features is None else tuple(FeatureObservation(name=name, value_json=canonical_json(value)) for name, value in sorted(features.items())),
        extensions=extensions, readiness='discovered', reasons=tuple(dict.fromkeys(problems)),
        client_prompt_id_source_supported=profile.client_prompt_id_supported if profile else None,
    )


def map_remote_status(profile_revision: str, normalized_status: str,
                      raw_status: str | None = None) -> str:
    """Decode profile semantics only. Caller must separately prove prompt ownership.

    No receipt, history or job is fetched by this helper. Unknown normalizer values
    and 'completed' without an explicit raw success must never imply success.
    """
    if profile_revision != SOURCE_PROFILE.revision:
        return 'unknown'
    if normalized_status == 'pending' and raw_status is None:
        return 'queued'
    if normalized_status == 'in_progress' and raw_status is None:
        return 'running'
    if normalized_status == 'completed' and raw_status == 'success':
        return 'execution_succeeded'
    if normalized_status == 'failed' and raw_status == 'error':
        return 'execution_failed'
    return 'unknown'
