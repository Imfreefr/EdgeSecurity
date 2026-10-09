"""Check actual infer method's class mapping without loading model weights/torch."""
import ast
import unittest
from collections import OrderedDict
from threading import Lock
from uuid import uuid4
from pathlib import Path
from types import SimpleNamespace


class TensorList:
    def __init__(self, values):
        self.values = values

    def cpu(self):
        return self

    def tolist(self):
        return self.values

    def int(self):
        return self


class Boxes(SimpleNamespace):
    def __len__(self):
        return len(self.cls.values)

    def cpu(self):
        return self

    def numpy(self):
        return self


class DetectorClassTests(unittest.TestCase):
    def test_actual_infer_preserves_ids_and_canonical_classes(self):
        tree = ast.parse(Path('backend/services/detector.py').read_text(encoding='utf-8'))
        detector = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        namespace = dict(OrderedDict=OrderedDict, Lock=Lock, uuid4=uuid4,
                         create_camera_tracker=lambda: SimpleNamespace(update=lambda *args: []))
        exec(compile(ast.Module(body=[detector], type_ignores=[]), '<detector-infer>', 'exec'), namespace)
        boxes = Boxes(id=None, cls=TensorList([0, 1, 2, 3]),
                                xyxy=TensorList([[1, 2, 3, 4]]*4), conf=TensorList([.9]*4))
        model = SimpleNamespace(predict=lambda **kwargs: [SimpleNamespace(boxes=boxes)])
        instance = object.__new__(namespace['SafetyDetector'])
        instance.__dict__.update(model=model, confidence=.4, iou=.5,
                                names={0: '.pessoa', 1: '.máquina', 2: 'operador', 3: 'objeto'},
                                _inference_lock=Lock(), _camera_trackers=OrderedDict(), _tracker_capacity=256)
        result = instance.infer(SimpleNamespace(shape=(480, 640, 3)))
        self.assertEqual([item['class_id'] for item in result], [0, 1, 2, 3])
        self.assertEqual([item['class_name'] for item in result], ['human', 'forklift', 'operator', 'objeto'])
        self.assertEqual(result[2]['label'], 'operador')

        instance.names = {0: 'pedestre', 1: 'empilhadeira', 2: 'operador', 3: 'carga'}
        result = instance.infer(SimpleNamespace(shape=(480, 640, 3)))
        self.assertEqual([item['class_name'] for item in result], ['human', 'forklift', 'operator', 'carga'])


if __name__ == '__main__':
    unittest.main()
