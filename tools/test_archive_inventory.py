import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image
from inventory_forklift_archive import inventory


class ArchiveInventoryTests(unittest.TestCase):
    def test_pixels_duplicates_invalid_and_no_extraction(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = io.BytesIO()
            Image.new('RGB', (4, 3), 'red').save(data, format='PNG')
            package = root / 'source.zip'
            with zipfile.ZipFile(package, 'w') as archive:
                archive.writestr('train/a.png', data.getvalue())
                archive.writestr('val/b.png', data.getvalue())
                archive.writestr('../../unsafe.py', 'raise RuntimeError()')
                archive.writestr('broken.jpg', b'invalid')
            output = root / 'inventory.ndjson'
            stats = inventory(package, output)
            self.assertEqual(stats['images'], 3)
            self.assertEqual(stats['invalid'], 1)
            self.assertEqual(stats['duplicate_occurrences'], 1)
            self.assertEqual(stats['approved_images'], 0)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertTrue(all(not row['approved_for_training'] for row in rows))
            self.assertEqual(set(p.name for p in root.iterdir()), {'source.zip', 'inventory.ndjson'})
            with self.assertRaises(ValueError):
                inventory(package, output)


if __name__ == '__main__':
    unittest.main()
