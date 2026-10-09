from collections import OrderedDict
from threading import Lock
from uuid import uuid4
from pathlib import Path
from ultralytics import YOLO
from .camera_tracking import create_camera_tracker


class SafetyDetector:
    def __init__(self, model_path: str, confidence: float = 0.40, iou: float = 0.50):
        self.model_path = model_path
        self.confidence = confidence
        self.iou = iou
        model_file = Path(model_path)
        if not model_file.is_absolute():
            # Resolve relative to project root (where .env is)
            project_root = Path(__file__).resolve().parents[2]
            model_file = (project_root / model_file).resolve()
        if not model_file.exists():
            raise FileNotFoundError(f"Modelo YOLO não encontrado: {model_file}")
        self.model_path = str(model_file)
        self.model = YOLO(str(model_file))
        self._inference_lock = Lock()
        self._camera_trackers = OrderedDict()
        self._tracker_capacity = 256

        names = self.model.names
        self.names = (
            {int(k): str(v) for k, v in names.items()}
            if isinstance(names, dict)
            else dict(enumerate(names))
        )

    def infer(self, frame, camera_id='default', company_id=None):
        if not isinstance(camera_id, str) or not camera_id:
            raise ValueError('Camera identity is required for inference')
        # YOLO predictor and tracker updates are mutable, so serialize shared access.
        with self._inference_lock:
            return self._infer_locked(frame, camera_id, company_id)

    def release_camera(self, camera_id, company_id=None):
        with self._inference_lock:
            self._camera_trackers.pop((company_id, camera_id), None)

    def _infer_locked(self, frame, camera_id, company_id):
        key = (company_id, camera_id)
        shape = tuple(frame.shape[:2])
        context = self._camera_trackers.get(key)
        if context is None or context['shape'] != shape:
            context = {'tracker': create_camera_tracker(), 'epoch': uuid4().hex, 'shape': shape}
            self._camera_trackers[key] = context
        self._camera_trackers.move_to_end(key)
        while len(self._camera_trackers) > self._tracker_capacity:
            self._camera_trackers.popitem(last=False)
        result = self.model.predict(
            source=frame,
            conf=self.confidence,
            iou=self.iou,
            verbose=False,
        )[0]

        detections = []
        if result.boxes is None:
            return detections

        boxes = result.boxes
        tracks = context['tracker'].update(boxes.cpu().numpy(), frame)
        ids = [None] * len(boxes)
        for track in tracks:
            index = int(track[-1])
            if not 0 <= index < len(ids):
                raise ValueError('Tracker returned an invalid detection index')
            ids[index] = int(track[4])
        xyxy = boxes.xyxy.cpu().tolist()
        confs = boxes.conf.cpu().tolist()
        classes = boxes.cls.int().cpu().tolist()

        for bbox, conf, cls_id, track_id in zip(xyxy, confs, classes, ids):
            raw_name = self.names.get(cls_id, str(cls_id)).lower().strip().lstrip(".")
            # O modelo treinado deve usar estas classes. Também aceitamos aliases comuns.
            if raw_name in {
                "person",
                "pessoa",
                "pedestre",
                "pedestrian",
                "human",
                "humano",
                "worker",
                "trabalhador",
            }:
                class_name = "human"
            elif raw_name in {"operador", "operator", "driver", "condutor"}:
                class_name = "operator"
            elif raw_name in {
                "machine",
                "máquina",
                "maquina",
                "vehicle",
                "veiculo",
                "veículo",
                "forklift",
                "empilhadeira",
            }:
                class_name = "forklift"
            else:
                class_name = raw_name

            detections.append(
                {
                    "class_id": cls_id,
                    "class_name": class_name,
                    "label": raw_name,
                    "confidence": round(float(conf), 4),
                    "bbox": [round(float(v), 2) for v in bbox],
                    "track_id": track_id,
                    "camera_id": camera_id,
                    "track_key": f"{camera_id}:{context['epoch']}:{track_id}" if track_id is not None else None,
                }
            )
        return detections
