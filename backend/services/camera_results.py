"""Bounded, tenant-scoped latest detection results, independent of visibility."""
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import time


class CameraResults:
    def __init__(self, capacity=256):
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValueError('Result capacity must be positive')
        self.capacity = capacity
        self._results = OrderedDict()
        self._lock = Lock()

    def record(self, company_id, camera_id, result):
        if not isinstance(camera_id, str) or not camera_id:
            raise ValueError('Camera identity is required')
        if result.get('camera_id') != camera_id:
            raise ValueError('Result camera differs from source camera')
        counts = {'people': 0, 'forklifts': 0, 'operators': 0, 'objects': 0}
        names = {0: 'people', 1: 'forklifts', 2: 'operators', 3: 'objects'}
        for detection in result.get('detections', []):
            category = names.get(detection.get('class_id'))
            if category is not None:
                counts[category] += 1
        snapshot = deepcopy(result)
        snapshot.update(counts=counts, processed_at=time())
        key = (company_id, camera_id)
        with self._lock:
            self._results[key] = snapshot
            self._results.move_to_end(key)
            while len(self._results) > self.capacity:
                self._results.popitem(last=False)
        return deepcopy(snapshot)

    def latest(self, company_id, camera_id):
        with self._lock:
            return deepcopy(self._results.get((company_id, camera_id)))

    def remove(self, company_id, camera_id):
        with self._lock:
            self._results.pop((company_id, camera_id), None)
