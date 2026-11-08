"""Immutable contracts for the read-only ComfyUI bridge.

Timeout defaults are operational safeguards, not measured acceptance thresholds.
None represents unavailable/unknown evidence; empty tuples represent observed emptiness.
"""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', strict=True)


def canonical_local_url(value: str) -> str:
    if not isinstance(value, str) or value != value.strip() or any(ord(c) < 33 for c in value):
        raise ValueError('Endpoint URL must be an explicit local HTTP(S) origin')
    try:
        url = urlsplit(value)
        port = url.port
        host = url.hostname
    except ValueError as exc:
        raise ValueError('Invalid endpoint origin') from exc
    if url.scheme not in ('http', 'https') or not host or url.username is not None or url.password is not None:
        raise ValueError('Endpoint must be an unauthenticated local HTTP(S) origin')
    if url.path not in ('', '/') or url.query or url.fragment or '?' in value or '#' in value:
        raise ValueError('Endpoint paths, queries and fragments are not supported')
    if host == 'localhost':
        host = '127.0.0.1'  # Avoid DNS/proxy resolution of the local alias.
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError('Only explicit loopback addresses are allowed') from exc
    if not address.is_loopback or '%' in host:
        raise ValueError('Only loopback endpoints are allowed in this wave')
    if port is not None and not 1 <= port <= 65535:
        raise ValueError('Invalid endpoint port')
    host = f'[{address.compressed}]' if address.version == 6 else address.compressed
    default_port = 80 if url.scheme == 'http' else 443
    return f'{url.scheme}://{host}' + (f':{port}' if port is not None and port != default_port else '')


class EndpointIdentity(FrozenModel):
    endpoint_id: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.-]+$')
    canonical_url: str
    configured_locality: Literal['loopback'] = 'loopback'
    profile_revision: str = Field(default='unqualified', min_length=1, max_length=128)
    discovery_generation: int = Field(default=0, ge=0, le=9223372036854775807)
    # Version, URL and connection generation are deliberately not boot receipts.
    server_identity: None = None
    session_identity: None = None
    server_boot_identity: None = None

    _local_url = field_validator('canonical_url')(canonical_local_url)


class ComfyConnectionSettings(FrozenModel):
    enabled: bool = False
    endpoint_id: str = Field(default='local-comfyui', min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.-]+$')
    endpoint_url: str = 'http://127.0.0.1:8188'
    configured_locality: Literal['loopback'] = 'loopback'
    profile_revision: str = Field(default='unqualified', min_length=1, max_length=128)
    control_timeout_seconds: float = Field(default=10.0, gt=0, le=300, allow_inf_nan=False)
    transfer_timeout_seconds: float = Field(default=120.0, gt=0, le=3600, allow_inf_nan=False)
    max_response_bytes: int = Field(default=8_388_608, gt=0, le=67_108_864)

    _local_url = field_validator('endpoint_url')(canonical_local_url)

    def to_endpoint(self, discovery_generation: int = 0) -> EndpointIdentity:
        return EndpointIdentity(endpoint_id=self.endpoint_id, canonical_url=self.endpoint_url,
                                configured_locality=self.configured_locality,
                                profile_revision=self.profile_revision,
                                discovery_generation=discovery_generation)


class NodeIdentity(FrozenModel):
    name: str
    schema_sha256: str | None
    schema_state: Literal['observed', 'invalid']
    package_identity_state: Literal['unknown'] = 'unknown'


class ModelIdentity(FrozenModel):
    role: str
    name: str
    identity_state: Literal['unknown', 'verified', 'invalid', 'missing'] = 'unknown'
    sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    execution_ready: Literal[False] = False

    @model_validator(mode='after')
    def require_identity_evidence(self) -> ModelIdentity:
        if self.identity_state == 'verified' and self.sha256 is None:
            raise ValueError('A verified model identity requires an explicit hash')
        if self.identity_state != 'verified' and self.sha256 is not None:
            raise ValueError('A hash must carry a verified identity state')
        return self


class ModelRoleInventory(FrozenModel):
    role: str
    names: tuple[str, ...] | None
    state: Literal['observed', 'unavailable']


class FeatureObservation(FrozenModel):
    name: str
    value_json: str


class DiscoverySnapshot(FrozenModel):
    endpoint: EndpointIdentity
    version: str | None = None
    profile_revision: str = 'unqualified'
    profile_source_sha256: str | None = None
    profile_binding: Literal['source_candidate', 'unqualified'] = 'unqualified'
    nodes: tuple[NodeIdentity, ...] | None = None
    models: tuple[ModelIdentity, ...] | None = None
    model_roles: tuple[ModelRoleInventory, ...] | None = None
    features: tuple[FeatureObservation, ...] | None = None
    extensions: tuple[str, ...] | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    readiness: Literal['discovered', 'unavailable', 'incompatible']
    reasons: tuple[str, ...] = ()
    execution_ready: Literal[False] = False
    custom_node_inventory_complete: Literal[False] = False
    client_prompt_id_source_supported: bool | None = None
    client_prompt_id_runtime_verified: None = None


class SourceProfile(FrozenModel):
    revision: str
    version: str
    source_commit: str
    server_sha256: str
    client_prompt_id_supported: bool


class SocketBinding(FrozenModel):
    endpoint: EndpointIdentity
    websocket_client_id: str
    post_client_id: str
    reconciliation_required: Literal[True] = True


class SocketObservation(FrozenModel):
    endpoint: EndpointIdentity
    connection_generation: int = Field(ge=0, le=9223372036854775807)
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    kind: Literal['json', 'invalid', 'binary_discarded', 'oversize_discarded']
    event_type: str | None = None
    prompt_id: str | None = None
    correlatable: bool = False
