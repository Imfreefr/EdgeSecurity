import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from services.camera_results import CameraResults


class CameraResultTests(unittest.TestCase):
    def test_all_classes_and_multiple_occurrences_are_counted(self):
        store = CameraResults()
        result = store.record('company', 'camera', {
            'camera_id': 'camera',
            'detections': [{'class_id': cls} for cls in [0, 0, 1, 2, 3, 3, 3]],
        })
        self.assertEqual(result['counts'], {'people': 2, 'forklifts': 1, 'operators': 1, 'objects': 3})

    def test_camera_and_tenant_results_do_not_mix(self):
        store = CameraResults()
        for company, camera, cls in [('a', 'one', 0), ('a', 'two', 2), ('b', 'one', 3)]:
            store.record(company, camera, {'camera_id': camera, 'detections': [{'class_id': cls}]})
        self.assertEqual(store.latest('a', 'one')['counts']['people'], 1)
        self.assertEqual(store.latest('a', 'two')['counts']['operators'], 1)
        self.assertEqual(store.latest('b', 'one')['counts']['objects'], 1)
        self.assertIsNone(store.latest('b', 'two'))

    def test_snapshots_cannot_mutate_stored_results(self):
        store = CameraResults()
        source = {'camera_id': 'one', 'detections': [{'class_id': 0, 'bbox': [1, 2, 3, 4]}]}
        returned = store.record('a', 'one', source)
        source['detections'].clear()
        returned['detections'].clear()
        first = store.latest('a', 'one')
        first['detections'][0]['bbox'][0] = 999
        self.assertEqual(store.latest('a', 'one')['detections'][0]['bbox'][0], 1)

    def test_bounded_and_rejects_wrong_camera(self):
        store = CameraResults(capacity=2)
        for camera in ['one', 'two', 'three']:
            store.record('a', camera, {'camera_id': camera, 'detections': []})
        self.assertIsNone(store.latest('a', 'one'))
        self.assertIsNotNone(store.latest('a', 'two'))
        with self.assertRaises(ValueError):
            store.record('a', 'one', {'camera_id': 'two'})
        store.remove('a', 'two')
        self.assertIsNone(store.latest('a', 'two'))

    def test_thirty_camera_results_survive_without_display_selection(self):
        store = CameraResults()
        for index in range(30):
            camera = str(index)
            store.record('a', camera, {'camera_id': camera, 'detections': [{'class_id': index % 4}]})
        self.assertTrue(all(store.latest('a', str(index)) is not None for index in range(30)))


if __name__ == '__main__':
    unittest.main()
