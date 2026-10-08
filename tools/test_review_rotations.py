import unittest
import hashlib
import json
import tempfile
from pathlib import Path
from PIL import Image
from correct_review_rotations import rotate_box, correct


class RotationTests(unittest.TestCase):
    def test_counterclockwise_coordinates(self):
        self.assertEqual(rotate_box([0, .75, .25, .2, .4]), [0, .25, .25, .4, .2])

    def test_four_rotations_restore_box(self):
        box = [1, .6, .3, .2, .4]
        result = box
        for _ in range(4):
            result = rotate_box(result)
        for actual, expected in zip(result, box):
            self.assertAlmostEqual(actual, expected)

    def test_invalid_box_rejected(self):
        for box in ([0, .9, .5, .4, .2], [4, .5, .5, .2, .2], [0, float('nan'), .5, .2, .2]):
            with self.assertRaises(ValueError):
                rotate_box(box)

    def test_deferred_labels_preserved_not_approved_or_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root/'source.png'
            Image.new('RGB', (8, 6), 'blue').save(image)
            boxes = [[2, .5, 0, .2, .3]]
            row = dict(id='fixture', path=str(image), width=8, height=6, boxes=boxes,
                       sha256=hashlib.sha256(image.read_bytes()).hexdigest(), pixel_sha256='fixture',
                       status='pending_individual_visual_review')
            manifest = root/'manifest.ndjson'
            manifest.write_text(json.dumps(row)+'\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                correct(manifest, root/'strict', ['fixture'])
            self.assertFalse((root/'strict').exists())
            correct(manifest, root/'review', ['fixture'], defer_invalid_boxes=True)
            result = json.loads((root/'review/manifest.ndjson').read_text(encoding='utf-8'))
            self.assertEqual(result['geometry_source']['boxes'], boxes)
            self.assertEqual(result['boxes'], [])
            self.assertTrue(result['annotation_redraw_required'])
            self.assertFalse(result['confirmed_negative'])
            self.assertFalse(result['annotation_review_complete'])
            self.assertFalse(result['approved_for_training'])
            self.assertEqual((result['width'], result['height']), (6, 8))
            self.assertTrue(image.exists())
