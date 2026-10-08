"""Small generated fixtures test safety only; not training imagery."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from apply_duplicate_redraw import apply_review


class DuplicateRedrawTests(unittest.TestCase):
    def prepare(self, root):
        records, members = [], []
        for identity, split in [('a', 'train'), ('b', 'val')]:
            path = root/(identity+'.png')
            Image.new('RGB', (16, 12), '#112233').save(path)
            records.append(dict(id=identity, platform_name='fixture', path=path.name,
                width=16, height=12, split=split, boxes=[[0, .5, .5, .1, .1]],
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), status='pending'))
            members.append(dict(id=identity, name='fixture', split=split))
        manifest, inventory, decisions = root/'input.ndjson', root/'inventory.json', root/'decisions.json'
        manifest.write_text(''.join(json.dumps(r)+'\n' for r in records), encoding='utf-8')
        inventory.write_text(json.dumps(dict(identical_pixel_groups=[dict(members=members)])), encoding='utf-8')
        decisions.write_text(json.dumps(dict(reference_size=[16,12], date='fixture', group='fixture',
            frames=dict(fixture=dict(boxes=[[0,1,1,8,10]], coverage_complete=True, note='fixture')))), encoding='utf-8')
        return manifest, inventory, decisions

    def test_preserves_labels_and_requires_overlay_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.prepare(root)
            before = args[0].read_bytes(), (root/'a.png').read_bytes(), (root/'b.png').read_bytes()
            report = apply_review(*args, root/'out')
            rows = [json.loads(s) for s in (root/'out/manifest.ndjson').read_text().splitlines()]
            self.assertEqual(report['duplicate_occurrences_excluded'], 1)
            self.assertEqual(rows[0]['boxes'], [[0, .5, .5, .1, .1]])
            self.assertEqual(rows[1]['duplicate_of'], 'a')
            self.assertTrue(all(not r['approved_for_training'] for r in rows))
            self.assertFalse(rows[0]['annotation_review_complete'])
            self.assertEqual(before, (args[0].read_bytes(), (root/'a.png').read_bytes(), (root/'b.png').read_bytes()))
            with self.assertRaises(ValueError):
                apply_review(*args, root/'out')

    def test_changed_pixels_rejected_even_with_updated_byte_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.prepare(root)
            Image.new('RGB', (16, 12), '#ffffff').save(root/'b.png')
            rows = [json.loads(s) for s in args[0].read_text().splitlines()]
            rows[1]['sha256'] = hashlib.sha256((root/'b.png').read_bytes()).hexdigest()
            args[0].write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'pixels differ'):
                apply_review(*args, root/'out')
            self.assertFalse((root/'out').exists())

    def test_out_of_frame_box_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.prepare(root)
            decision = json.loads(args[2].read_text())
            decision['frames']['fixture']['boxes'][0][-1] = 13
            args[2].write_text(json.dumps(decision), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Invalid manually'):
                apply_review(*args, root/'out')
            self.assertFalse((root/'out').exists())


if __name__ == '__main__':
    unittest.main()
