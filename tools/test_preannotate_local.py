"""Synthetic fixtures test integrity/resume gates; never dataset approval."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from preannotate_local import run, normalized_boxes, validate_names, overlap_flags


class PreannotationTests(unittest.TestCase):
    def test_resume_preserves_source_and_never_approves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image, model, manifest = root/'source.png', root/'model.pt', root/'manifest.ndjson'
            Image.new('RGB', (32, 32)).save(image)
            model.write_bytes(b'fixture model')
            row = dict(id='fixture', platform_name='fixture', path=str(image), width=32, height=32,
                       sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                       status='pending_individual_visual_review')
            manifest.write_text(json.dumps(row)+'\n', encoding='utf8')
            original = manifest.read_bytes()
            calls = []

            def predict(path):
                calls.append(path)
                return [[0, .999, 2, 2, 20, 20], [1, .9, -1, 0, 32, 32]]

            report = run(manifest, model, root/'batch', predictor=predict)
            self.assertEqual(report['invalid_detections'], 1)
            self.assertEqual(report['approved'], 0)
            first_statistics = (root/'batch/statistics.json').read_bytes()
            self.assertEqual(run(manifest, model, root/'batch', predictor=predict)['cached'], 1)
            self.assertEqual((root/'batch/statistics.json').read_bytes(), first_statistics)
            self.assertEqual(len(calls), 1)
            self.assertEqual(manifest.read_bytes(), original)
            artifact = json.loads((root/'batch/fixture.json').read_text(encoding='utf8'))
            self.assertFalse(artifact['visually_reviewed'])
            self.assertFalse(artifact['coverage_complete'])
            Path(artifact['overlay']).write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                run(manifest, model, root/'batch', predictor=predict)
            self.assertFalse((root/'batch/.lock').exists())

    def test_classes_geometry_and_batch_limits(self):
        validate_names({0: '.pessoa', 1: '.máquina', 2: 'operador', 3: 'objeto'})
        with self.assertRaises(ValueError):
            validate_names({0: 'person', 1: 'car', 2: 'operator', 3: 'object'})
        boxes, issues = normalized_boxes([[2, .8, 0, 0, 10, 10], [0, float('nan'), 0, 0, 10, 10]], 10, 10)
        self.assertEqual(boxes[0]['yolo'], [2, .5, .5, 1., 1.])
        self.assertEqual(len(issues), 1)
        duplicate, _ = normalized_boxes([[0, .9, 0, 0, 10, 10], [0, .8, 0, 0, 10, 10]], 10, 10)
        self.assertEqual(overlap_flags(duplicate)[0]['reason'], 'duplicate box')
        duplicate[1]['class_id'] = 2
        self.assertEqual(overlap_flags(duplicate)[0]['reason'], 'conflicting person classes')
        with self.assertRaises(ValueError):
            run('missing', 'missing', 'missing', limit=51)


if __name__ == '__main__':
    unittest.main()
