"""Decoded geometry checks for read-only original recovery; no network calls."""
from io import BytesIO
import unittest
from PIL import Image
from recover_originals_public_api import validate_geometry, identity


class PublicOriginalRecoveryTests(unittest.TestCase):
    def encoded(self, size=(20, 30)):
        stream = BytesIO()
        Image.new('RGB', size, 'red').save(stream, format='PNG')
        return stream.getvalue()

    def test_decoded_dimensions_match_metadata(self):
        digest = validate_geometry({'width': 20, 'height': 30}, self.encoded())
        self.assertEqual(len(digest), 64)

    def test_thumbnail_dimensions_cannot_replace_full_image(self):
        with self.assertRaises(ValueError):
            validate_geometry({'width': 200, 'height': 300}, self.encoded())

    def test_identity_detects_dataset_changes(self):
        before = {'id': 'a', 'imageCount': 340, 'annotationCount': 1322, 'updatedAt': 'old'}
        self.assertNotEqual(identity(before), identity(dict(before, updatedAt='new')))
        self.assertNotEqual(identity(before), identity(dict(before, annotationCount=1323)))


if __name__ == '__main__':
    unittest.main()
