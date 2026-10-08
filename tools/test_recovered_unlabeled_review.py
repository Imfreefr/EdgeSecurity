"""Recovered IDs must match individual decisions; fixtures never enter dataset."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from curate_collision_originals import recovered_unlabeled_review


class RecoveredUnlabeledTests(unittest.TestCase):
    def prepare(self, root):
        image = root/'fixture.bin'
        image.write_bytes(b'software-test-fixture-only')
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        rows = [{'id': str(i), 'platform_name': f'fixture-{i}', 'boxes': [],
                 'path': image.name, 'sha256': digest} for i in range(14)]
        manifest = root/'input.ndjson'
        manifest.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
        decision = {'images': {row['platform_name']: 'fixture reason' for row in rows},
                    'reason': 'Excluded fixture', 'decision': 'excluded_viewpoint',
                    'group': 'fixture-group', 'date': 'test', 'method': 'fixture'}
        decisions = root/'decisions.json'
        decisions.write_text(json.dumps(decision), encoding='utf-8')
        return manifest, decisions, image

    def test_preserves_originals_and_never_marks_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, decisions, image = self.prepare(root)
            before = manifest.read_bytes(), image.read_bytes()
            output = root/'review'
            recovered_unlabeled_review(manifest, decisions, output)
            rows = [json.loads(line) for line in (output/'manifest.ndjson').read_text().splitlines()]
            self.assertEqual(len(rows), 14)
            self.assertTrue(all(not row['confirmed_negative'] and not row['approved_for_training'] for row in rows))
            self.assertEqual(before, (manifest.read_bytes(), image.read_bytes()))
            with self.assertRaises(ValueError):
                recovered_unlabeled_review(manifest, decisions, output)

    def test_changed_bytes_stop_before_output_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, decisions, image = self.prepare(root)
            image.write_bytes(b'changed-fixture')
            with self.assertRaises(ValueError):
                recovered_unlabeled_review(manifest, decisions, root/'review')
            self.assertFalse((root/'review').exists())


if __name__ == '__main__':
    unittest.main()
