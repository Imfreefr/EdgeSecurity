import json
import tempfile
import unittest
from pathlib import Path
from save_dataset_checkpoint import save


class CheckpointTests(unittest.TestCase):
    def test_atomic_pointer_and_lock_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root/'manifest.ndjson'
            manifest.write_text(json.dumps(dict(id='a', platform_name='frame', status='pending_individual_visual_review'))+'\n', encoding='utf-8')
            target = root/'resume.json'
            self.assertEqual(save(manifest, target)['first_pending'], 'frame')
            previous = target.read_bytes()
            lock = root/'resume.json.lock'
            lock.write_text('other writer')
            with self.assertRaises(FileExistsError):
                save(manifest, target)
            self.assertEqual(target.read_bytes(), previous)
            self.assertTrue(lock.exists())
