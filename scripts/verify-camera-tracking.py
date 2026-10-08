"""Real ByteTrack checks using synthetic boxes, optionally real-model smoke inference."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from services.camera_tracking import create_camera_tracker


def main():
    from ultralytics.engine.results import Boxes
    boxes = Boxes(np.array([[10+100*c, 20, 60+100*c, 100, .95, c] for c in range(4)], dtype=np.float32), (480,640))
    trackers = [create_camera_tracker() for _ in range(30)]
    results = [tracker.update(boxes) for tracker in trackers]
    assert all(len(result)==4 for result in results)
    assert all([int(r[4]) for r in result]==[1,2,3,4] for result in results)
    for index, tracker in enumerate(trackers):
        repeated = tracker.update(boxes)
        assert [int(r[4]) for r in repeated]==[1,2,3,4]
        assert tracker.frame_id==2
    new_tracker = create_camera_tracker()
    assert trackers[0].frame_id==2
    new_tracker.update(boxes)
    assert trackers[0].frame_id==2
    expanded = Boxes(np.vstack([boxes.data, [450, 20, 500, 100, .95, 0]]).astype(np.float32), (480,640))
    trackers[0].update(expanded)
    expanded_result = trackers[0].update(expanded)
    assert {int(row[4]) for row in expanded_result}=={1,2,3,4,5}
    report = dict(real_bytetrack=True, tracker_contexts=30,
                  synthetic_box_fixture=True, live_camera_validation=False,
                  repeated_ids_stable=True, four_classes_retained=True)
    report['new_camera_does_not_reset_existing_id_allocator'] = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model')
    parser.add_argument('--image')
    args = parser.parse_args()
    if bool(args.model) != bool(args.image):
        parser.error('Model and image must be provided together')
    if args.model:
        import cv2
        from services.detector import SafetyDetector
        image = cv2.imread(args.image)
        if image is None:
            raise ValueError('Cannot decode smoke-test image')
        detector = SafetyDetector(args.model)
        first = detector.infer(image, 'smoke-a', 'local-verification')
        second = detector.infer(image, 'smoke-b', 'local-verification')
        again = detector.infer(image, 'smoke-a', 'local-verification')
        assert all(d['camera_id']=='smoke-a' for d in first+again)
        assert all(d['camera_id']=='smoke-b' for d in second)
        assert not ({d['track_key'] for d in first if d['track_key']} &
                    {d['track_key'] for d in second if d['track_key']})
        report.update(real_model_smoke=True, model_classes=detector.names,
                      detections_per_call=[len(first),len(second),len(again)],
                      fixture='same image replayed for two camera IDs; not two physical cameras')
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
