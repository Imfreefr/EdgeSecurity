import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from verify_cctv_package import verify_remote_pixels


class RemotePixelsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.buffer = io.BytesIO()
        Image.new('RGB', (12, 8), 'red').save(self.root/'frame.png')
        with ZipFile(self.buffer, 'w') as archive:
            archive.write(self.root/'frame.png', 'images/test/frame.png')
        self.records = [{'id': 'frame', 'path': 'images/test/frame.png'}]
        self.images = [{'file': 'frame.png'}]

    def tearDown(self):
        self.temp.cleanup()

    def verify(self):
        with ZipFile(self.buffer) as archive:
            verify_remote_pixels(archive, self.records, self.images, self.root)

    def test_equal_decoded_pixels(self):
        self.verify()

    def test_changed_pixels_rejected(self):
        Image.new('RGB', (12, 8), 'blue').save(self.root/'frame.png')
        with self.assertRaisesRegex(ValueError, 'pixels differ'):
            self.verify()

    def test_changed_dimensions_rejected(self):
        Image.new('RGB', (8, 12), 'red').save(self.root/'frame.png')
        with self.assertRaisesRegex(ValueError, 'pixels differ'):
            self.verify()

    def test_escape_and_missing_rejected(self):
        self.images = [{'file': '../frame.png'}]
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.verify()
        self.images = []
        with self.assertRaisesRegex(ValueError, 'one-to-one'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
