"""Independent captures and a fair, single-model latest-frame scheduler."""
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import Condition, Event, Thread
from time import monotonic, time

from .risk_engine import assess_risk


def open_capture(source):
    import cv2
    # Network sources only; local file replay belongs in explicit verification tools.
    if not isinstance(source, str) or not source.startswith(('rtsp://', 'http://', 'https://')):
        raise ValueError('Unsupported camera source')
    capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG, [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000,
    ])
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


@dataclass
class CameraFlow:
    company_id: str | None
    camera_id: str
    source: str | None
    stop: Event = field(default_factory=Event)
    thread: Thread | None = None
    frame: object = None
    jpeg: bytes | None = None
    sequence: int = 0
    dispatched: int = 0
    processed: int = 0
    dropped: int = 0
    reconnects: int = 0
    connection_state: str = 'waiting_for_frames'
    processing_state: str = 'waiting_for_frames'
    last_captured_at: float | None = None
    last_processed_at: float | None = None
    error_code: str | None = None


class CameraPipeline:
    def __init__(self, detector_provider, results, capture_factory=open_capture,
                 alert_callback=None, capture_fps=5, reconnect_delay=1, capacity=256):
        if capture_fps <= 0 or reconnect_delay < 0 or capacity <= 0:
            raise ValueError('Invalid pipeline limits')
        self.detector_provider = detector_provider
        self.results = results
        self.capture_factory = capture_factory
        self.alert_callback = alert_callback
        self.capture_interval = 1/capture_fps
        self.reconnect_delay = reconnect_delay
        self.capacity = capacity
        self._condition = Condition()
        self._flows = OrderedDict()
        self._stop = Event()
        self._worker = None
        self._detector = None

    def start(self):
        with self._condition:
            if self._worker is not None:
                return
            if self._stop.is_set():
                raise RuntimeError('Closed pipeline cannot restart')
            self._worker = Thread(target=self._process, name='edge-shared-inference', daemon=True)
            self._worker.start()

    def add_camera(self, company_id, camera_id, source=None):
        if not isinstance(camera_id, str) or not camera_id:
            raise ValueError('Camera identity is required')
        if source is not None and (not isinstance(source, str) or not source.startswith(('rtsp://','http://','https://'))):
            raise ValueError('Unsupported network camera source')
        key = (company_id, camera_id)
        with self._condition:
            if self._stop.is_set():
                raise RuntimeError('Pipeline is closed')
            previous = self._flows.get(key)
            if previous is not None:
                if previous.source != source:
                    raise ValueError('Remove old source before replacing it')
                return
            if len(self._flows) >= self.capacity:
                raise ValueError('Configured camera capacity reached')
            flow = CameraFlow(company_id, camera_id, source)
            self._flows[key] = flow
            if source is not None:
                flow.connection_state = 'connecting'
                flow.thread = Thread(target=self._capture, args=(flow,), name=f'edge-capture-{camera_id}', daemon=True)
                flow.thread.start()
            self._condition.notify_all()

    def remove_camera(self, company_id, camera_id):
        with self._condition:
            flow = self._flows.pop((company_id, camera_id), None)
            if flow:
                flow.stop.set()
            self._condition.notify_all()
        if self._detector is not None:
            self._detector.release_camera(camera_id, company_id)
        self.results.remove(company_id, camera_id)
        if flow and flow.thread:
            flow.thread.join(timeout=0.1)

    def has_network_capture(self, company_id, camera_id):
        with self._condition:
            flow = self._flows.get((company_id, camera_id))
            return flow is not None and flow.source is not None

    def _publish_frame(self, flow, frame):
        import cv2
        import numpy as np
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3 or min(frame.shape[:2]) <= 0:
            raise ValueError('Invalid BGR frame')
        if max(frame.shape[:2]) > 1280:
            scale = 1280/max(frame.shape[:2])
            frame = cv2.resize(frame, (max(1,round(frame.shape[1]*scale)), max(1,round(frame.shape[0]*scale))))
        else:
            frame = frame.copy()
        ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise ValueError('Cannot encode preview')
        with self._condition:
            if self._flows.get((flow.company_id, flow.camera_id)) is not flow or flow.stop.is_set():
                return None
            if flow.sequence > flow.dispatched:
                flow.dropped += 1
            flow.frame, flow.jpeg = frame, encoded.tobytes()
            flow.sequence += 1
            flow.last_captured_at = time()
            flow.connection_state = 'connected'
            if flow.processing_state == 'waiting_for_frames':
                flow.processing_state = 'queued'
            self._condition.notify_all()
            return flow.sequence

    def submit_frame(self, company_id, camera_id, frame):
        with self._condition:
            flow = self._flows.get((company_id, camera_id))
            if flow is None or flow.source is not None:
                raise ValueError('Browser camera not registered')
        try:
            return self._publish_frame(flow, frame)
        except ValueError:
            with self._condition:
                flow.connection_state = 'error'
                flow.error_code = 'invalid_frame'
                self._condition.notify_all()
            raise

    def _capture(self, flow):
        while not self._stop.is_set() and not flow.stop.is_set():
            capture = None
            try:
                capture = self.capture_factory(flow.source)
                if capture is None or not capture.isOpened():
                    raise ValueError('Capture unavailable')
                while not self._stop.is_set() and not flow.stop.is_set():
                    started = monotonic()
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        raise ValueError('No valid frame')
                    self._publish_frame(flow, frame)
                    flow.stop.wait(max(0, self.capture_interval-(monotonic()-started)))
            except Exception:
                with self._condition:
                    flow.connection_state = 'reconnecting'
                    flow.error_code = 'capture_unavailable'
                    flow.reconnects += 1
                    self._condition.notify_all()
            finally:
                if capture is not None:
                    capture.release()
            flow.stop.wait(self.reconnect_delay)

    def _next(self):
        for key, flow in list(self._flows.items()):
            if flow.frame is not None and flow.sequence > flow.dispatched and not flow.stop.is_set():
                flow.dispatched = flow.sequence
                flow.processing_state = 'processing'
                self._flows.move_to_end(key)
                frame = flow.frame
                flow.frame = None
                return flow, frame, flow.sequence, flow.last_captured_at
        return None

    def _process(self):
        while not self._stop.is_set():
            with self._condition:
                job = self._next()
                if job is None:
                    self._condition.wait(timeout=.2)
                    continue
            flow, frame, sequence, captured_at = job
            try:
                if self._detector is None:
                    self._detector = self.detector_provider()
                detections = self._detector.infer(frame, camera_id=flow.camera_id, company_id=flow.company_id)
                risk = assess_risk(detections, frame_width=frame.shape[1])
                alert_id, alert_error = None, None
                if self.alert_callback:
                    with self._condition:
                        if self._flows.get((flow.company_id,flow.camera_id)) is not flow:
                            continue
                    try:
                        alert_id = self.alert_callback(flow.camera_id, risk, flow.company_id)
                    except Exception:
                        alert_error = 'alert_persistence_failed'
                with self._condition:
                    if self._flows.get((flow.company_id,flow.camera_id)) is not flow:
                        continue
                    result = self.results.record(flow.company_id, flow.camera_id, dict(
                        type='result', camera_id=flow.camera_id, detections=detections, risk=risk,
                        frame_width=frame.shape[1], frame_height=frame.shape[0],
                        source_sequence=sequence, captured_at=captured_at, alert_created=alert_id))
                    flow.processed += 1
                    flow.last_processed_at = result['processed_at']
                    flow.processing_state = 'processing'
                    flow.error_code = alert_error
                    self._condition.notify_all()
            except Exception:
                with self._condition:
                    flow.processing_state = 'error'
                    flow.error_code = 'inference_failed'
                    self._condition.notify_all()

    def snapshot(self, company_id, camera_id):
        with self._condition:
            flow = self._flows.get((company_id, camera_id))
            if flow is None:
                return None
            state = dict(camera_id=camera_id, connection_state=flow.connection_state,
                         processing_state=flow.processing_state, captured_frames=flow.sequence,
                         processed_frames=flow.processed, dropped_frames=flow.dropped,
                         pending_frames=int(flow.sequence>flow.dispatched), reconnect_attempts=flow.reconnects,
                         last_captured_at=flow.last_captured_at, last_processed_at=flow.last_processed_at,
                         error_code=flow.error_code)
            age = time()-flow.last_captured_at if flow.last_captured_at is not None else None
            state['last_capture_age_seconds'] = age
            if flow.connection_state == 'connected' and age is not None and age > 5:
                state['connection_state'] = 'no_signal'
            state['processing_active'] = state['connection_state']=='connected' and flow.processing_state=='processing'
        state['result'] = self.results.latest(company_id, camera_id)
        return state

    def wait_for_result(self, company_id, camera_id, after_sequence=0, timeout=10):
        deadline = monotonic()+timeout
        with self._condition:
            while not self._stop.is_set():
                if (company_id, camera_id) not in self._flows:
                    return None
                result = self.results.latest(company_id, camera_id)
                if result and result['source_sequence'] > after_sequence:
                    return result
                remaining = deadline-monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=remaining)
        return None

    def wait_for_jpeg(self, company_id, camera_id, after_sequence=0, timeout=2):
        deadline = monotonic()+timeout
        with self._condition:
            while not self._stop.is_set():
                flow = self._flows.get((company_id,camera_id))
                if flow is None:
                    return None
                if flow.jpeg and flow.sequence > after_sequence:
                    return flow.sequence, flow.jpeg
                remaining = deadline-monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=remaining)
        return None

    def close(self, timeout=5):
        self._stop.set()
        with self._condition:
            flows = list(self._flows.values())
            for flow in flows:
                flow.stop.set()
            self._condition.notify_all()
        deadline = monotonic()+timeout
        threads = [f.thread for f in flows if f.thread] + ([self._worker] if self._worker else [])
        for thread in threads:
            thread.join(timeout=max(0,deadline-monotonic()))
        remaining = sum(thread.is_alive() for thread in threads)
        if remaining == 0:
            for flow in flows:
                if self._detector is not None:
                    self._detector.release_camera(flow.camera_id, flow.company_id)
                self.results.remove(flow.company_id, flow.camera_id)
            with self._condition:
                self._flows.clear()
        return {'remaining_threads': remaining}
