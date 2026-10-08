"""Exercise actual detector methods with explicit fake predictions and trackers."""
import ast
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from uuid import uuid4
import unittest
from test_detector_classes import Boxes, TensorList


def detector_fixture():
    tree = ast.parse(Path('backend/services/detector.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SafetyDetector')
    created = []

    class Tracker:
        def __init__(self):
            self.calls = 0
            created.append(self)

        def update(self, boxes, frame):
            self.calls += 1
            return [[1, 2, 3, 4, index+1, .9, cls, index] for index, cls in enumerate(boxes.cls.values)]

    namespace = dict(OrderedDict=OrderedDict, Lock=Lock, uuid4=uuid4, create_camera_tracker=Tracker)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual-detector>', 'exec'), namespace)
    instance = object.__new__(namespace['SafetyDetector'])
    boxes = Boxes(cls=TensorList([0, 1, 2, 3]), xyxy=TensorList([[1, 2, 3, 4]]*4), conf=TensorList([.9]*4))
    instance.__dict__.update(model=SimpleNamespace(predict=lambda **kwargs: [SimpleNamespace(boxes=boxes)]),
                            confidence=.4, iou=.5, names={0:'pessoa',1:'empilhadeira',2:'operador',3:'objeto'},
                            _inference_lock=Lock(), _camera_trackers=OrderedDict(), _tracker_capacity=256)
    return instance, created


class CameraTrackingTests(unittest.TestCase):
    def test_interleaved_cameras_and_tenants_have_separate_state(self):
        detector, created = detector_fixture()
        frame = SimpleNamespace(shape=(480, 640, 3))
        a = detector.infer(frame, 'one', 'company-a')
        b = detector.infer(frame, 'two', 'company-a')
        c = detector.infer(frame, 'one', 'company-b')
        again = detector.infer(frame, 'one', 'company-a')
        self.assertEqual(len(created), 3)
        self.assertEqual([t.calls for t in created], [2, 1, 1])
        self.assertEqual(a[0]['track_key'], again[0]['track_key'])
        self.assertNotEqual(a[0]['track_key'], b[0]['track_key'])
        self.assertNotEqual(a[0]['track_key'], c[0]['track_key'])
        self.assertEqual([d['class_id'] for d in a], [0, 1, 2, 3])

    def test_shape_change_and_removal_create_new_identity_epoch(self):
        detector, created = detector_fixture()
        frame = SimpleNamespace(shape=(480, 640, 3))
        first = detector.infer(frame, 'one')[0]['track_key']
        second = detector.infer(SimpleNamespace(shape=(640, 480, 3)), 'one')[0]['track_key']
        self.assertNotEqual(first, second)
        detector.release_camera('one')
        third = detector.infer(frame, 'one')[0]['track_key']
        self.assertNotEqual(second, third)

    def test_thirty_concurrent_calls_share_model_but_not_trackers(self):
        detector, created = detector_fixture()
        model = detector.model
        frame = SimpleNamespace(shape=(480, 640, 3))
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda camera: detector.infer(frame, str(camera)), range(30)))
        self.assertIs(detector.model, model)
        self.assertEqual(len(created), 30)
        self.assertEqual(len({result[0]['track_key'] for result in results}), 30)
        self.assertEqual({r[0]['camera_id'] for r in results}, {str(i) for i in range(30)})

    def test_tracker_storage_is_bounded(self):
        detector, created = detector_fixture()
        detector._tracker_capacity = 2
        frame = SimpleNamespace(shape=(480, 640, 3))
        for camera in ['one', 'two', 'three']:
            detector.infer(frame, camera)
        self.assertEqual(len(detector._camera_trackers), 2)
        self.assertNotIn((None, 'one'), detector._camera_trackers)
        with self.assertRaises(ValueError):
            detector.infer(frame, '')


if __name__ == '__main__':
    unittest.main()
