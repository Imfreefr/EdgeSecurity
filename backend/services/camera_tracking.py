"""ByteTrack state and ID allocator belonging to exactly one camera context."""


def create_camera_tracker():
    from types import SimpleNamespace
    from ultralytics.trackers.byte_tracker import BYTETracker, STrack
    from ultralytics.utils import ROOT, YAML

    next_identity = 0

    class CameraTrack(STrack):
        def next_id(self):
            nonlocal next_identity
            next_identity += 1
            return next_identity

    class CameraTracker(BYTETracker):
        track_class = CameraTrack

        @staticmethod
        def reset_id():
            # Constructing/removing a camera must not reset another camera's IDs.
            # Keep this camera's allocator monotonic even if its tracker resets.
            pass

    settings = YAML.load(ROOT/'cfg/trackers/bytetrack.yaml')
    return CameraTracker(SimpleNamespace(**settings))
