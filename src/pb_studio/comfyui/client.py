"""Bounded read-only ComfyUI discovery, plus local socket contract primitives.

Explicit inspect() is a user-initiated diagnostic, including when settings.enabled
is false. enabled controls later automatic host integration; this module has no
background tasks, startup hooks, submit, cancel, upload or GPU operations.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import quote, urlencode
from uuid import UUID

import httpx

from .capabilities import build_snapshot
from .schemas import (ComfyConnectionSettings, DiscoverySnapshot, EndpointIdentity,
                      SocketBinding, SocketObservation)


@dataclass
class _ReadBudget:
    remaining: int


class _DiscoveryError(Exception):
    """Safe reason code only; never expose remote bodies or transport exception text."""


def _strict_json(data: str | bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError('nonfinite JSON number')
        return number
    def invalid_constant(value):
        raise ValueError('nonfinite JSON constant')
    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float)
        stack = [(value, 0)]
        count = 0
        while stack:
            item, depth = stack.pop()
            count += 1
            if depth > 64 or count > 1_000_000:
                raise ValueError('JSON structural limit exceeded')
            if isinstance(item, str):
                item.encode('utf-8')  # Reject escaped lone surrogates as well.
            elif isinstance(item, dict):
                stack.extend((key, depth + 1) for key in item)
                stack.extend((child, depth + 1) for child in item.values())
            elif isinstance(item, list):
                stack.extend((child, depth + 1) for child in item)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise _DiscoveryError('invalid_json') from exc


class ComfyClient:
    """Each result retains its request endpoint, never a mutable global last-error.

    Production transport does not trust proxy environment variables, follow
    redirects or retry. Injectable transports are only a contract-test seam.
    Network-wait deadline bounds the entire inspect, not each of N model roles.
    Total response bytes per inspect are bounded as well; JSON parsing is bounded
    structurally and by input size, not a preemptible CPU deadline.
    Transfer timeout is validated separately for later transfer consumers; no
    transfer API is implemented in this wave.
    """
    def __init__(self, settings: ComfyConnectionSettings | None = None, *,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings or ComfyConnectionSettings()
        self._http = httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(self.settings.control_timeout_seconds),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            headers={'Accept': 'application/json', 'Accept-Encoding': 'identity'},
        )

    async def __aenter__(self) -> ComfyClient:
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get_json(self, endpoint: EndpointIdentity, route: str, budget: _ReadBudget) -> Any:
        # Private allowlist prevents accidental future use as an arbitrary proxy.
        if route not in ('/system_stats', '/object_info', '/features', '/models', '/extensions') and not re.fullmatch(r'/models/[A-Za-z0-9_-]+', route):
            raise ValueError('Route outside read-only discovery scope')
        try:
            async with self._http.stream('GET', endpoint.canonical_url + route) as response:
                if 300 <= response.status_code < 400:
                    raise _DiscoveryError('redirect_rejected')
                if response.status_code != 200:
                    raise _DiscoveryError(f'http_{response.status_code}')
                if response.headers.get('content-encoding', 'identity').lower() != 'identity':
                    raise _DiscoveryError('content_encoding_rejected')
                media_type = response.headers.get('content-type', '').split(';', 1)[0].strip().lower()
                if media_type != 'application/json':
                    raise _DiscoveryError('unexpected_content_type')
                content_length = response.headers.get('content-length')
                if content_length is not None:
                    try:
                        size = int(content_length)
                    except ValueError as exc:
                        raise _DiscoveryError('invalid_content_length') from exc
                    if size < 0:
                        raise _DiscoveryError('invalid_content_length')
                    if size > self.settings.max_response_bytes:
                        raise _DiscoveryError('response_too_large')
                    if size > budget.remaining:
                        raise _DiscoveryError('response_budget_exceeded')
                data = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    if len(data) + len(chunk) > self.settings.max_response_bytes:
                        raise _DiscoveryError('response_too_large')
                    budget.remaining -= len(chunk)
                    if budget.remaining < 0:
                        raise _DiscoveryError('response_budget_exceeded')
                    data.extend(chunk)
                return _strict_json(data)
        except httpx.TimeoutException as exc:
            raise _DiscoveryError('control_timeout') from exc
        except httpx.HTTPError as exc:
            raise _DiscoveryError('transport_unavailable') from exc

    async def inspect(self, endpoint: EndpointIdentity, *, inventory: bool = True) -> DiscoverySnapshot:
        """Explicit diagnostic GETs; inventory=False touches only /system_stats.

        /object_info can start ComfyUI's internal asset scanner. Callers observing
        active jobs can choose inventory=False to avoid that server-side work.
        Cancellation propagates and does not alter any remote job.
        """
        try:
            async with asyncio.timeout(self.settings.control_timeout_seconds):
                return await self._inspect(endpoint, inventory=inventory)
        except TimeoutError:
            return DiscoverySnapshot(endpoint=endpoint, readiness='unavailable', reasons=('control_timeout',))
        except _DiscoveryError as exc:
            reason = str(exc)
            state = 'unavailable' if reason in ('control_timeout', 'transport_unavailable') or reason.startswith('http_') else 'incompatible'
            return DiscoverySnapshot(endpoint=endpoint, readiness=state, reasons=(reason,))

    async def _inspect(self, endpoint: EndpointIdentity, *, inventory: bool) -> DiscoverySnapshot:
        budget = _ReadBudget(self.settings.max_response_bytes)
        stats = await self._get_json(endpoint, '/system_stats', budget)
        if not isinstance(stats, dict) or not isinstance(stats.get('system'), dict) or not isinstance(stats.get('devices'), list):
            raise _DiscoveryError('invalid_system_stats')
        version = stats['system'].get('comfyui_version')
        if not isinstance(version, str) or not version or len(version) > 128:
            raise _DiscoveryError('invalid_system_stats')
        if not inventory:
            return build_snapshot(endpoint=endpoint, version=version, nodes=None, model_names=None,
                                  features=None, extensions=None, reasons=('inventory_not_requested',))
        nodes = await self._get_json(endpoint, '/object_info', budget)
        if not isinstance(nodes, dict) or len(nodes) > 50000:
            raise _DiscoveryError('invalid_node_inventory')
        reasons = []
        async def optional(route):
            try:
                return await self._get_json(endpoint, route, budget)
            except _DiscoveryError as exc:
                if str(exc) == 'response_budget_exceeded':
                    raise
                reasons.append(f'{route.lstrip("/")}:{exc}')
                return None
        features = await optional('/features')
        if features is not None and (not isinstance(features, dict) or len(features) > 1024):
            reasons.append('invalid_features')
            features = None
        roles = await optional('/models')
        models = None
        unavailable_roles = []
        if roles is not None:
            if not isinstance(roles, list) or len(roles) > 64 or not all(isinstance(role, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', role) for role in roles):
                reasons.append('invalid_model_roles')
            else:
                models = {}
                for role in sorted(set(roles)):
                    names = await optional('/models/' + quote(role, safe=''))
                    if names is None:
                        unavailable_roles.append(role)
                        continue
                    if not isinstance(names, list) or len(names) > 50000 or not all(isinstance(name, str) and 0 < len(name) <= 4096 for name in names):
                        reasons.append('invalid_model_names')
                        unavailable_roles.append(role)
                        continue
                    models[role] = names
        extensions = await optional('/extensions')
        if extensions is not None:
            if not isinstance(extensions, list) or len(extensions) > 10000 or not all(isinstance(item, str) and len(item) <= 4096 for item in extensions):
                reasons.append('invalid_extensions')
                extensions = None
            else:
                extensions = tuple(extensions)
        return build_snapshot(endpoint=endpoint, version=version, nodes=nodes, model_names=models,
                              features=features, extensions=extensions, reasons=tuple(reasons),
                              unavailable_model_roles=tuple(unavailable_roles))


def _canonical_uuid(value: str) -> str:
    try:
        if str(UUID(value)) != value:
            raise ValueError('Noncanonical UUID')
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('SID/prompt ID requires a canonical lowercase UUID') from exc
    return value


def websocket_url(endpoint: EndpointIdentity, client_id: str) -> str:
    """Pure mapping; opens no socket. HTTP payload uses client_id, WS uses clientId."""
    sid = _canonical_uuid(client_id)
    origin = endpoint.canonical_url.replace('https://', 'wss://', 1).replace('http://', 'ws://', 1)
    return origin + '/ws?' + urlencode({'clientId': sid})


class SocketOwnerRegistry:
    """Process-wide local owner guard for future bridge lifecycle integration.

    Hold claim across complete connect/receive/close, including awaiting actual
    local handler shutdown. No sockets are opened here. Release is NOT proof of
    remote handler cleanup; HTTP reconciliation remains mandatory after reconnect.
    """
    _lock = threading.Lock()
    _owners: set[str] = set()

    @contextmanager
    def claim(self, endpoint: EndpointIdentity, client_id: str) -> Iterator[SocketBinding]:
        sid = _canonical_uuid(client_id)
        key = endpoint.canonical_url
        with self._lock:
            if key in self._owners:
                raise RuntimeError('Endpoint already has a local socket owner')
            self._owners.add(key)
        try:
            yield SocketBinding(endpoint=endpoint, websocket_client_id=sid, post_client_id=sid)
        finally:
            with self._lock:
                self._owners.remove(key)


def decode_ws_frame(frame: str | bytes, endpoint: EndpointIdentity, connection_generation: int,
                    *, max_bytes: int = 1_048_576) -> SocketObservation:
    """Discard previews; expose only safe envelope identity, never mutate jobs.

    correlatable means syntactically eligible, NOT owned: the future receiver must
    still match endpoint, profile, and prompt ID against its durable attempt.
    """
    if type(max_bytes) is not int or not 1 <= max_bytes <= 67_108_864:
        raise ValueError('Invalid frame limit')
    fields = dict(endpoint=endpoint, connection_generation=connection_generation)
    if not isinstance(frame, (str, bytes)):
        return SocketObservation(**fields, kind='invalid')
    if len(frame) > max_bytes:
        return SocketObservation(**fields, kind='oversize_discarded')
    if isinstance(frame, bytes):
        return SocketObservation(**fields, kind='binary_discarded')
    try:
        if len(frame.encode('utf-8')) > max_bytes:
            return SocketObservation(**fields, kind='oversize_discarded')
        value = _strict_json(frame)
        if not isinstance(value, dict) or not isinstance(value.get('type'), str) or len(value['type']) > 128 or not isinstance(value.get('data'), dict):
            raise ValueError('Invalid event envelope')
        prompt_id = value['data'].get('prompt_id')
        if prompt_id is not None:
            prompt_id = _canonical_uuid(prompt_id)
        return SocketObservation(**fields, kind='json', event_type=value['type'], prompt_id=prompt_id,
                                 correlatable=prompt_id is not None)
    except (ValueError, UnicodeError, _DiscoveryError):
        return SocketObservation(**fields, kind='invalid')
