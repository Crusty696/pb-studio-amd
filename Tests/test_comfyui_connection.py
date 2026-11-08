"""Isolated contracts: no backend, GPU, filesystem assets or live ComfyUI."""
import asyncio
import unittest
from uuid import uuid4

import httpx
from pydantic import ValidationError

from pb_studio.comfyui.client import ComfyClient, SocketOwnerRegistry, decode_ws_frame, websocket_url
from pb_studio.comfyui.schemas import ComfyConnectionSettings, EndpointIdentity


def endpoint(port=8188, generation=0):
    return EndpointIdentity(endpoint_id=f'local-{port}', canonical_url=f'http://127.0.0.1:{port}', discovery_generation=generation)


def handler(request):
    payloads = {
        '/system_stats': {'system': {'comfyui_version': '0.39.2'}, 'devices': []},
        '/object_info': {'CheckpointLoaderSimple': {'input': {'required': {}}, 'output': ['MODEL'], 'name': 'CheckpointLoaderSimple'}},
        '/features': {'supports_preview_metadata': True},
        '/models': ['checkpoints'], '/models/checkpoints': ['model.safetensors'], '/extensions': ['/extensions/core.js'],
    }
    return httpx.Response(200, json=payloads[request.url.path])


class ConnectionTests(unittest.TestCase):
    def inspect(self, responder=handler, **kwargs):
        async def run():
            async with ComfyClient(transport=httpx.MockTransport(responder), **kwargs) as client:
                return await client.inspect(endpoint())
        return asyncio.run(run())

    def test_get_only_and_typed_immutable_snapshot(self):
        requests = []
        def respond(request):
            requests.append(request)
            return handler(request)
        snap = self.inspect(respond)
        self.assertEqual(snap.readiness, 'discovered')
        self.assertFalse(snap.execution_ready)
        self.assertEqual(snap.endpoint, endpoint())
        self.assertIsNone(snap.endpoint.server_boot_identity)
        self.assertTrue(all(r.method == 'GET' for r in requests))
        self.assertNotIn('/queue', [r.url.path for r in requests])
        with self.assertRaises(ValidationError):
            snap.readiness = 'qualified'

    def test_endpoints_and_generations_never_mixed(self):
        async def run():
            def respond(request):
                response = handler(request)
                if request.url.path == '/system_stats':
                    return httpx.Response(200, json={'system': {'comfyui_version': str(request.url.port)}, 'devices': []})
                return response
            async with ComfyClient(transport=httpx.MockTransport(respond)) as client:
                return await asyncio.gather(client.inspect(endpoint(8188, 3)), client.inspect(endpoint(8189, 4)))
        a, b = asyncio.run(run())
        self.assertEqual((a.version, b.version), ('8188', '8189'))
        self.assertNotEqual(a.endpoint, b.endpoint)
        self.assertIsNone(a.endpoint.server_boot_identity)

    def test_wrong_service_rejected(self):
        snap = self.inspect(lambda r: httpx.Response(200, json={'ok': True}))
        self.assertEqual(snap.readiness, 'incompatible')
        self.assertIn('invalid_system_stats', snap.reasons)

    def test_offline_returns_safe_reason_once(self):
        requests = []
        def fail(request):
            requests.append(request)
            raise httpx.ConnectError('SECRET path prompt', request=request)
        snap = self.inspect(fail)
        self.assertEqual(snap.readiness, 'unavailable')
        self.assertEqual(len(requests), 1)
        self.assertNotIn('SECRET', snap.model_dump_json())

    def test_total_deadline_and_event_loop_responsiveness(self):
        async def run():
            ticks = []
            async def slow(request):
                await asyncio.sleep(.025)
                return handler(request)
            async def ticker():
                await asyncio.sleep(.01)
                ticks.append(True)
            async with ComfyClient(settings=ComfyConnectionSettings(control_timeout_seconds=.04), transport=httpx.MockTransport(slow)) as client:
                snap, _ = await asyncio.gather(client.inspect(endpoint()), ticker())
                return snap, ticks
        snap, ticks = asyncio.run(run())
        self.assertTrue(ticks)
        self.assertEqual(snap.readiness, 'unavailable')
        self.assertIn('control_timeout', snap.reasons)

    def test_external_cancellation_propagates(self):
        async def run():
            async def slow(request):
                await asyncio.sleep(20)
            async with ComfyClient(transport=httpx.MockTransport(slow)) as client:
                task = asyncio.create_task(client.inspect(endpoint()))
                await asyncio.sleep(0)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        asyncio.run(run())

    def test_redirect_never_followed(self):
        requests = []
        def redirect(request):
            requests.append(request)
            return httpx.Response(302, headers={'Location': 'http://example.com/secrets'})
        snap = self.inspect(redirect)
        self.assertEqual(len(requests), 1)
        self.assertIn('redirect_rejected', snap.reasons)

    def test_oversize_and_bad_json_fail_closed(self):
        for response, reason in [
            (httpx.Response(200, content=b'x' * 129, headers={'content-type': 'application/json'}), 'response_too_large'),
            (httpx.Response(200, content=b'{', headers={'content-type': 'application/json'}), 'invalid_json'),
            (httpx.Response(200, content=b'{"system": {}, "system": {}}', headers={'content-type': 'application/json'}), 'invalid_json'),
            (httpx.Response(200, text='<html>proxy</html>'), 'unexpected_content_type'),
        ]:
            with self.subTest(reason=reason):
                snap = self.inspect(lambda r: response, settings=ComfyConnectionSettings(max_response_bytes=128))
                self.assertIn(reason, snap.reasons)

    def test_nonfinite_json_rejected(self):
        snap = self.inspect(lambda r: httpx.Response(200, content=b'{"x":NaN}', headers={'content-type': 'application/json'}))
        self.assertIn('invalid_json', snap.reasons)

    def test_numeric_overflow_surrogates_and_depth_fail_closed(self):
        for body in [b'{"x":1e400}', b'{"x":"\\ud800"}', b'[' * 80 + b'0' + b']' * 80]:
            with self.subTest(body=body[:30]):
                snap = self.inspect(lambda r: httpx.Response(200, content=body, headers={'content-type': 'application/json'}))
                self.assertEqual(snap.readiness, 'incompatible')
                self.assertIn('invalid_json', snap.reasons)

    def test_content_encoding_and_chunked_byte_limit(self):
        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'x' * 65
                yield b'x' * 65
        snap = self.inspect(lambda r: httpx.Response(200, stream=Stream(), headers={'content-type': 'application/json'}), settings=ComfyConnectionSettings(max_response_bytes=128))
        self.assertIn('response_too_large', snap.reasons)
        snap = self.inspect(lambda r: httpx.Response(200, headers={'content-type': 'application/json', 'content-encoding': 'deflate'}))
        self.assertIn('content_encoding_rejected', snap.reasons)

    def test_socket_owner_shared_across_registries_and_aliases(self):
        first, second = SocketOwnerRegistry(), SocketOwnerRegistry()
        alias = EndpointIdentity(endpoint_id='other-config', canonical_url='http://localhost:8188/', discovery_generation=99)
        with first.claim(endpoint(), str(uuid4())):
            with self.assertRaises(RuntimeError):
                with second.claim(alias, str(uuid4())):
                    pass

    def test_failure_response_does_not_retry_or_save_body(self):
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(503, text='SECRET traceback')
        snap = self.inspect(respond)
        self.assertEqual(len(calls), 1)
        self.assertEqual(snap.reasons, ('http_503',))
        self.assertNotIn('SECRET', snap.model_dump_json())

    def test_total_byte_budget_is_per_inspect_and_endpoint(self):
        calls = []
        def respond(request):
            calls.append(request.url.path)
            return handler(request)
        snap = self.inspect(respond, settings=ComfyConnectionSettings(max_response_bytes=200))
        self.assertIn('response_budget_exceeded', snap.reasons)
        self.assertLess(len(calls), 6)

    def test_probe_does_not_fetch_inventory(self):
        async def run():
            calls = []
            def respond(request):
                calls.append(request.url.path)
                return handler(request)
            async with ComfyClient(transport=httpx.MockTransport(respond)) as client:
                snap = await client.inspect(endpoint(), inventory=False)
                return snap, calls
        snap, calls = asyncio.run(run())
        self.assertEqual(calls, ['/system_stats'])
        self.assertIn('inventory_not_requested', snap.reasons)
        self.assertEqual(snap.readiness, 'discovered')

    def test_local_urls_only_and_canonicalized(self):
        self.assertEqual(ComfyConnectionSettings(endpoint_url='http://localhost:8188/').endpoint_url, 'http://127.0.0.1:8188')
        for url in ['http://example.com', 'http://127.0.0.1@evil.com', 'http://127.0.0.1/path', 'http://127.0.0.1?token=x', 'file:///x', 'http://127.1', 'http://127.0.0.1#x', 'http://127.0.0.1:0']:
            with self.subTest(url=url), self.assertRaises(ValidationError):
                ComfyConnectionSettings(endpoint_url=url)
        self.assertEqual(ComfyConnectionSettings(endpoint_url='http://[::1]:8188').to_endpoint().configured_locality, 'loopback')

    def test_settings_bounds_and_types(self):
        for changes in [{'control_timeout_seconds': float('inf')}, {'control_timeout_seconds': 0.0}, {'max_response_bytes': True}, {'transfer_timeout_seconds': 3601.0}, {'discovery_generation': -1}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                if 'discovery_generation' in changes:
                    endpoint(generation=-1)
                else:
                    ComfyConnectionSettings(**changes)

    def test_websocket_mapping_binary_and_owner(self):
        sid = str(uuid4())
        self.assertEqual(websocket_url(endpoint(), sid), f'ws://127.0.0.1:8188/ws?clientId={sid}')
        binary = decode_ws_frame(b'\x00\x01preview', endpoint(), 2)
        self.assertEqual(binary.kind, 'binary_discarded')
        self.assertIsNone(binary.prompt_id)
        event = decode_ws_frame('{"type":"executing","data":{"node":"1"}}', endpoint(), 2)
        self.assertIsNone(event.prompt_id)
        self.assertFalse(event.correlatable)
        registry = SocketOwnerRegistry()
        with registry.claim(endpoint(), sid):
            with self.assertRaises(RuntimeError):
                with registry.claim(endpoint(), sid):
                    pass
        with registry.claim(endpoint(), sid) as binding:
            self.assertEqual(binding.post_client_id, sid)
            self.assertTrue(binding.reconciliation_required)

    def test_ws_invalid_and_oversize_are_safe(self):
        for value in ['{', '[]', '{"type":"executing","data":{"prompt_id":"bad"}}']:
            self.assertEqual(decode_ws_frame(value, endpoint(), 0).kind, 'invalid')
        self.assertEqual(decode_ws_frame(b'x' * 20, endpoint(), 0, max_bytes=10).kind, 'oversize_discarded')

if __name__ == '__main__':
    unittest.main()
