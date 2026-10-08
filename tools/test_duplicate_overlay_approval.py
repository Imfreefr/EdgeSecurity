"""Visual approval cannot silently accept changed review artifacts."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from apply_duplicate_redraw import apply_review
from approve_duplicate_overlays import approve
import test_duplicate_redraw


class DuplicateApprovalTests(unittest.TestCase):
    def prepare(self, root):
        inputs = test_duplicate_redraw.DuplicateRedrawTests().prepare(root)
        proposal = root/'proposal'
        apply_review(*inputs, proposal)
        manifest = proposal/'manifest.ndjson'
        approval = root/'approval.json'
        approval.write_text(json.dumps(dict(date='fixture',
            manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            approved_overlays=dict(fixture=hashlib.sha256((proposal/'fixture-redraw.png').read_bytes()).hexdigest()))), encoding='utf-8')
        return manifest, approval

    def test_applies_annotation_only_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = self.prepare(root)
            before = inputs[0].read_bytes()
            report = approve(*inputs, root/'approved')
            rows = [json.loads(line) for line in (root/'approved/manifest.ndjson').read_text().splitlines()]
            self.assertEqual(report['approved_annotation_reviews'], 1)
            self.assertTrue(rows[0]['annotation_review_complete'])
            self.assertIn('original_boxes', rows[0])
            self.assertFalse(rows[0]['approved_for_training'])
            self.assertEqual(rows[1]['status'], 'excluded_exact_duplicate')
            self.assertEqual(before, inputs[0].read_bytes())

    def test_manifest_overlay_and_source_mutations_rejected(self):
        for target in ('manifest.ndjson', 'fixture-redraw.png', 'source'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest, approval = self.prepare(root)
                path = root/'a.png' if target == 'source' else manifest.parent/target
                path.write_bytes(path.read_bytes()+b'changed')
                with self.assertRaises(ValueError):
                    approve(manifest, approval, root/'approved')
                self.assertFalse((root/'approved').exists())


if __name__ == '__main__':
    unittest.main()
