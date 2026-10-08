"""Exercise the actual WebSocket handler with explicit fake inference inputs."""
import ast
import asyncio
import base64
import unittest
from pathlib import Path
from types import SimpleNamespace
from backend.services.camera_results import CameraResults


class WebSocketCameraResultTests(unittest.TestCase):
    def test_actual_handler_records_classes_under_authorized_camera(self):
        tree = ast.parse(Path('backend/app.py').read_text(encoding='utf-8-sig'))
        endpoint = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                        and node.name == 'websocket_detection')
        endpoint.decorator_list = []
        store = CameraResults()

        class Disconnect(Exception):
            pass

        class DB:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, sql, params):
                row = {'status': 'ativo'} if 'SELECT status' in sql else {'company_id': 'tenant'}
                return SimpleNamespace(fetchone=lambda: row)

        class Socket:
            headers = {'origin': 'https://example.test'}

            def __init__(self, camera):
                self.messages = iter([
                    {'type': 'auth', 'token': 'test-token', 'camera_id': camera},
                    {'camera_id': camera, 'image': base64.b64encode(b'test-frame').decode()},
                ])
                self.sent = []
                self.closed = None

            async def accept(self):
                pass

            async def close(self, code):
                self.closed = code

            async def receive_json(self):
                try:
                    return next(self.messages)
                except StopIteration:
                    raise Disconnect()

            async def send_json(self, data):
                self.sent.append(data)

        detections = [{'class_id': cls, 'track_id': 1, 'bbox': [1, 2, 3, 4]}
                      for cls in range(4)]
        namespace = dict(asyncio=asyncio, WebSocket=Socket, WebSocketDisconnect=Disconnect,
                         HTTPException=ValueError, CORS_ORIGINS=['https://example.test'],
                         require_permission=lambda *args: {'id': 'user', 'cargo': 'administrador', 'company_id': 'tenant'},
                         conn=DB, Path=Path, base64=base64, camera_results=store,
                         cv2=SimpleNamespace(IMREAD_COLOR=1, imdecode=lambda *args: SimpleNamespace(shape=(480, 640, 3))),
                         get_detector=lambda: SimpleNamespace(model_path='fake.pt', names={i: str(i) for i in range(4)}, infer=lambda frame, **kwargs: detections),
                         assess_risk=lambda *args, **kwargs: {'level': 'safe'},
                         create_ai_alert=lambda *args: None)
        exec(compile(ast.Module(body=[endpoint], type_ignores=[]), '<actual-websocket>', 'exec'), namespace)

        async def run():
            for camera in ['camera-a', 'camera-b']:
                socket = Socket(camera)
                await namespace['websocket_detection'](socket)
                self.assertIsNone(socket.closed)
                self.assertEqual(socket.sent[-1]['type'], 'result', socket.sent)
                self.assertEqual(socket.sent[-1]['camera_id'], camera)
                self.assertEqual(socket.sent[-1]['counts'], {'people': 1, 'forklifts': 1, 'operators': 1, 'objects': 1})
                self.assertEqual(store.latest('tenant', camera)['camera_id'], camera)
                self.assertIsNone(store.latest('other-tenant', camera))
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
