"""Regression checks for review gating, geometry and scene leakage."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from build_cctv_review import normalize, validate_record, check_integrity


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory=Path(self.temp.name)
        self.path=self.directory/'a.png'
        Image.new('RGB',(100,80),'red').save(self.path)

    def tearDown(self):self.temp.cleanup()

    def record(self,**updates):
        base={'id':'a','path':str(self.path),'width':100,'height':80,
              'boxes':[[0,.5,.5,.2,.2]],'status':'approved_visual_review',
              'confirmed_negative':False,'group':'camera-a','split':'train'}
        return {**base,**updates}

    def test_pixel_normalization(self):
        self.assertEqual(normalize([[2,10,20,30,60]],100,80),[[2,.2,.5,.2,.5]])

    def test_empty_labels_not_automatically_negative(self):
        with self.assertRaises(ValueError):validate_record(self.record(boxes=[]))
        validate_record(self.record(boxes=[],confirmed_negative=True))

    def test_pending_labels_not_exported(self):
        with self.assertRaises(ValueError):validate_record(self.record(status='pending_label_review'))

    def test_outside_image_and_invalid_class(self):
        for box in [[0,.95,.5,.2,.2],[5,.5,.5,.2,.2],[0,float('nan'),.5,.2,.2]]:
            with self.assertRaises(ValueError):validate_record(self.record(boxes=[box]))

    def test_dimension_mismatch(self):
        with self.assertRaises(ValueError):validate_record(self.record(width=99))

    def test_duplicate_decoded_pixels(self):
        with self.assertRaises(ValueError):check_integrity([self.record(),self.record(id='b')])

    def test_camera_split_leakage(self):
        path=self.directory/'b.png'
        Image.new('RGB',(100,80),'blue').save(path)
        with self.assertRaises(ValueError):
            check_integrity([self.record(),self.record(id='b',path=str(path),split='test')])

    def test_distinct_camera_groups_allowed(self):
        path=self.directory/'b.png'
        Image.new('RGB',(100,80),'blue').save(path)
        result=check_integrity([self.record(),self.record(id='b',path=str(path),group='camera-b',split='test')])
        self.assertEqual(result['reviewed_records'],2)


if __name__=='__main__':unittest.main()
