import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from services.camera_pipeline import CameraPipeline
from services.camera_results import CameraResults


def wait_until(predicate, timeout=3):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('Condition not reached before deadline')


class CameraPipelineTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.loads = []
        self.frame = np.zeros((48,64,3),dtype=np.uint8)
        self.results = CameraResults()

        def infer(frame, camera_id, company_id):
            self.calls.append((company_id,camera_id))
            if camera_id == 'inference-error':
                raise ValueError('Simulated detector failure')
            return [dict(class_id=cls,class_name=name,bbox=[cls*12,1,cls*12+10,20],track_id=cls+1)
                    for cls,name in enumerate(['human','forklift','operator','objeto'])]

        self.detector = SimpleNamespace(infer=infer,release_camera=lambda *args: None)

        def provider():
            self.loads.append(True)
            return self.detector

        self.pipeline = CameraPipeline(provider,self.results,reconnect_delay=.01,capture_fps=100)
        self.addCleanup(self.pipeline.close)

    def test_thirty_sources_all_processed_without_any_display_state(self):
        for index in range(30):
            camera = str(index)
            self.pipeline.add_camera('tenant',camera)
            self.pipeline.submit_frame('tenant',camera,self.frame)
        self.pipeline.start()
        wait_until(lambda: len(self.calls)==30)
        self.assertEqual(len(self.loads),1)
        self.assertEqual([camera for company,camera in self.calls],[str(i) for i in range(30)])
        for index in range(30):
            snapshot = self.pipeline.snapshot('tenant',str(index))
            self.assertEqual(snapshot['processed_frames'],1)
            self.assertEqual(snapshot['pending_frames'],0)
            self.assertEqual(snapshot['result']['counts'],{'people':1,'forklifts':1,'operators':1,'objects':1})
        self.assertIsNone(self.pipeline.snapshot('other','0'))

    def test_latest_slot_drops_redundant_frames_instead_of_growing_queue(self):
        self.pipeline.add_camera('tenant','one')
        for _ in range(100):
            self.pipeline.submit_frame('tenant','one',self.frame)
        snapshot = self.pipeline.snapshot('tenant','one')
        self.assertEqual(snapshot['pending_frames'],1)
        self.assertEqual(snapshot['dropped_frames'],99)
        self.pipeline.start()
        result = self.pipeline.wait_for_result('tenant','one',after_sequence=99)
        self.assertEqual(result['source_sequence'],100)
        self.assertEqual(len(self.calls),1)

    def test_inference_and_alert_failures_do_not_stop_other_camera(self):
        self.pipeline.alert_callback = lambda *args: (_ for _ in ()).throw(ValueError('Test alert failure'))
        for camera in ['inference-error','good']:
            self.pipeline.add_camera('tenant',camera)
            self.pipeline.submit_frame('tenant',camera,self.frame)
        self.pipeline.start()
        wait_until(lambda:self.pipeline.snapshot('tenant','good')['processed_frames']==1)
        self.assertEqual(self.pipeline.snapshot('tenant','inference-error')['processing_state'],'error')
        self.assertIsNotNone(self.pipeline.snapshot('tenant','good')['result'])

    def test_capture_failure_reconnects_while_other_camera_runs(self):
        attempts = []

        class Capture:
            def __init__(self, source):
                self.source = source
                attempts.append(source)
            def isOpened(self):
                return self.source.endswith('good')
            def read(self):
                return True,np.zeros((48,64,3),dtype=np.uint8)
            def release(self):
                pass

        self.pipeline.capture_factory = Capture
        self.pipeline.add_camera('tenant','bad','rtsp://test/bad')
        self.pipeline.add_camera('tenant','good','rtsp://test/good')
        self.pipeline.start()
        wait_until(lambda:self.pipeline.snapshot('tenant','bad')['reconnect_attempts']>=2 and
                   self.pipeline.snapshot('tenant','good')['processed_frames']>=2)
        self.assertTrue(self.pipeline.has_network_capture('tenant','good'))
        self.assertEqual(self.pipeline.snapshot('tenant','bad')['connection_state'],'reconnecting')
        self.assertEqual(self.pipeline.close()['remaining_threads'],0)

    def test_dynamic_remove_and_invalid_frames(self):
        self.pipeline.add_camera('tenant','one')
        with self.assertRaises(ValueError):
            self.pipeline.submit_frame('tenant','one',None)
        self.assertEqual(self.pipeline.snapshot('tenant','one')['error_code'],'invalid_frame')
        self.pipeline.submit_frame('tenant','one',self.frame)
        self.pipeline.start()
        self.assertIsNotNone(self.pipeline.wait_for_result('tenant','one'))
        preview = self.pipeline.wait_for_jpeg('tenant','one')
        self.assertTrue(preview[1].startswith(b'\xff\xd8'))
        self.pipeline.remove_camera('tenant','one')
        self.assertIsNone(self.pipeline.snapshot('tenant','one'))
        self.assertIsNone(self.results.latest('tenant','one'))
        self.pipeline.add_camera('tenant','two')
        self.pipeline.submit_frame('tenant','two',self.frame)
        self.assertIsNotNone(self.pipeline.wait_for_result('tenant','two'))


if __name__ == '__main__':
    unittest.main()
