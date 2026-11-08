"""Discovery is evidence of presence, never a smoke/qualification result."""
import asyncio
import unittest

import httpx
from pydantic import ValidationError

from pb_studio.comfyui.capabilities import SOURCE_PROFILE, build_snapshot, map_remote_status
from pb_studio.comfyui.client import ComfyClient
from pb_studio.comfyui.schemas import EndpointIdentity, ModelIdentity


class CapabilityTests(unittest.TestCase):
    def snapshot(self, **changes):
        kwargs = dict(endpoint=EndpointIdentity(endpoint_id='test', canonical_url='http://127.0.0.1:8188'), version='0.39.2', nodes={'Loader': {'input': {'required': {}}, 'output': ['MODEL']}}, model_names={'checkpoints': ['same.safetensors']}, features={}, extensions=())
        kwargs.update(changes)
        return build_snapshot(**kwargs)

    def test_names_do_not_prove_identity_or_readiness(self):
        snap = self.snapshot()
        self.assertEqual(snap.models[0].identity_state, 'unknown')
        self.assertIsNone(snap.models[0].sha256)
        self.assertEqual(snap.nodes[0].package_identity_state, 'unknown')
        self.assertEqual(snap.readiness, 'discovered')
        self.assertFalse(snap.execution_ready)

    def test_hash_distinguishes_same_name_and_broken_model(self):
        first = ModelIdentity(role='checkpoints', name='same', sha256='a'*64, identity_state='verified')
        second = ModelIdentity(role='checkpoints', name='same', sha256='b'*64, identity_state='verified')
        self.assertNotEqual(first, second)
        broken = ModelIdentity(role='checkpoints', name='same', identity_state='invalid')
        self.assertFalse(broken.execution_ready)
        with self.assertRaises(ValidationError):
            ModelIdentity(role='x', name='x', identity_state='verified')

    def test_extensions_not_custom_package_inventory(self):
        snap = self.snapshot(extensions=('/extensions/example.js',))
        self.assertIn('custom_node_versions_unknown', snap.reasons)
        self.assertFalse(snap.custom_node_inventory_complete)

    def test_unknown_version_source_and_runtime_stay_unknown(self):
        snap = self.snapshot(version='99.0.0')
        self.assertEqual(snap.profile_revision, 'unqualified')
        self.assertIsNone(snap.client_prompt_id_source_supported)
        self.assertIsNone(snap.client_prompt_id_runtime_verified)
        self.assertFalse(snap.execution_ready)

    def test_known_version_does_not_prove_loaded_revision(self):
        snap = self.snapshot()
        self.assertEqual(snap.profile_revision, SOURCE_PROFILE.revision)
        self.assertTrue(snap.client_prompt_id_source_supported)
        self.assertIsNone(snap.client_prompt_id_runtime_verified)
        self.assertIsNone(snap.endpoint.server_boot_identity)
        self.assertIn('runtime_source_binding_unknown', snap.reasons)

    def test_schema_fingerprint_is_order_independent_not_version(self):
        a = self.snapshot(nodes={'L': {'input': {}, 'output': ['MODEL']}})
        b = self.snapshot(nodes={'L': {'output': ['MODEL'], 'input': {}}})
        c = self.snapshot(nodes={'L': {'input': {}, 'output': ['IMAGE']}})
        self.assertEqual(a.nodes[0].schema_sha256, b.nodes[0].schema_sha256)
        self.assertNotEqual(a.nodes[0].schema_sha256, c.nodes[0].schema_sha256)

    def test_broken_or_missing_nodes_are_explicit(self):
        empty = self.snapshot(nodes={})
        self.assertIn('nodes_missing', empty.reasons)
        bad = self.snapshot(nodes={'L': {'output': ['MODEL']}})
        self.assertEqual(bad.nodes[0].schema_state, 'invalid')
        self.assertFalse(bad.execution_ready)

    def test_role_failure_is_unavailable_not_observed_empty(self):
        snap = self.snapshot(model_names={}, unavailable_model_roles=('checkpoints',))
        self.assertEqual(snap.model_roles[0].state, 'unavailable')
        self.assertIsNone(snap.model_roles[0].names)
        self.assertNotIn('models_missing', snap.reasons)
        empty = self.snapshot(model_names={'checkpoints': []})
        self.assertEqual(empty.model_roles[0].names, ())
        self.assertEqual(empty.model_roles[0].state, 'observed')

    def test_explicit_profile_version_mismatch_blocks_discovery_use(self):
        binding = EndpointIdentity(endpoint_id='test', canonical_url='http://127.0.0.1:8188', profile_revision=SOURCE_PROFILE.revision)
        snap = self.snapshot(endpoint=binding, version='different')
        self.assertEqual(snap.readiness, 'incompatible')
        self.assertIn('profile_version_mismatch', snap.reasons)
        self.assertFalse(snap.execution_ready)

    def test_remote_status_completed_needs_raw_success(self):
        self.assertEqual(map_remote_status(SOURCE_PROFILE.revision, 'pending'), 'queued')
        self.assertEqual(map_remote_status(SOURCE_PROFILE.revision, 'completed'), 'unknown')
        self.assertEqual(map_remote_status(SOURCE_PROFILE.revision, 'completed', 'success'), 'execution_succeeded')
        self.assertEqual(map_remote_status('unqualified', 'completed', 'success'), 'unknown')
        self.assertEqual(map_remote_status(SOURCE_PROFILE.revision, 'new_state', 'success'), 'unknown')

    def test_optional_failure_keeps_explicit_partial_inventory(self):
        async def run():
            def respond(request):
                if request.url.path == '/system_stats':
                    return httpx.Response(200, json={'system': {'comfyui_version': '0.39.2'}, 'devices': []})
                if request.url.path == '/object_info':
                    return httpx.Response(200, json={})
                return httpx.Response(404)
            async with ComfyClient(transport=httpx.MockTransport(respond)) as client:
                return await client.inspect(EndpointIdentity(endpoint_id='test', canonical_url='http://127.0.0.1:8188'))
        snap = asyncio.run(run())
        self.assertIn('models:http_404', snap.reasons)
        self.assertIsNone(snap.models)
        self.assertFalse(snap.execution_ready)

    def test_bad_role_never_becomes_path_or_unbounded_scan(self):
        async def run():
            calls = []
            def respond(request):
                calls.append(request.url.path)
                if request.url.path == '/system_stats':
                    return httpx.Response(200, json={'system': {'comfyui_version': '0.39.2'}, 'devices': []})
                if request.url.path == '/object_info':
                    return httpx.Response(200, json={})
                if request.url.path == '/models':
                    return httpx.Response(200, json=['../prompt'])
                return httpx.Response(200, json={})
            async with ComfyClient(transport=httpx.MockTransport(respond)) as client:
                snap = await client.inspect(EndpointIdentity(endpoint_id='test', canonical_url='http://127.0.0.1:8188'))
                return snap, calls
        snap, calls = asyncio.run(run())
        self.assertNotIn('/prompt', calls)
        self.assertIn('invalid_model_roles', snap.reasons)

if __name__ == '__main__':
    unittest.main()
