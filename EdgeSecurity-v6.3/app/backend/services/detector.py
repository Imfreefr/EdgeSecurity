import os
from pathlib import Path
import cv2
from ultralytics import YOLO


class SafetyDetector:
    def __init__(self, model_path: str, confidence: float = 0.40, iou: float = 0.50):
        self.model_path = model_path
        self.confidence = confidence
        self.iou = iou
        model_file = Path(model_path)
        if not model_file.is_absolute():
            model_file = (Path(__file__).resolve().parents[1] / model_file).resolve()
        if not model_file.exists():
            raise FileNotFoundError(f'Modelo YOLO não encontrado: {model_file}')
        self.model_path = str(model_file)
        self.model = YOLO(str(model_file))

        names = self.model.names
        self.names = {int(k): str(v) for k, v in names.items()} if isinstance(names, dict) else dict(enumerate(names))

    def infer(self, frame):
        result = self.model.track(
            source=frame,
            persist=True,
            conf=self.confidence,
            iou=self.iou,
            verbose=False,
            tracker="bytetrack.yaml",
        )[0]

        detections = []
        if result.boxes is None:
            return detections

        boxes = result.boxes
        ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
        xyxy = boxes.xyxy.cpu().tolist()
        confs = boxes.conf.cpu().tolist()
        classes = boxes.cls.int().cpu().tolist()

        for bbox, conf, cls_id, track_id in zip(xyxy, confs, classes, ids):
            raw_name = self.names.get(cls_id, str(cls_id)).lower().strip()
            # O modelo treinado deve usar estas classes. Também aceitamos aliases comuns.
            if raw_name in {"person", "pessoa", "human", "humano", "worker", "trabalhador"}:
                class_name = "human"
            elif raw_name in {"forklift", "empilhadeira", "fork lift", "fork-lift"}:
                class_name = "forklift"
            elif raw_name in {"machine", "máquina", "maquina", "vehicle", "veiculo", "veículo"}:
                class_name = "machine"
            else:
                class_name = raw_name

            detections.append({
                "class_id": cls_id,
                "class_name": class_name,
                "label": raw_name,
                "confidence": round(float(conf), 4),
                "bbox": [round(float(v), 2) for v in bbox],
                "track_id": track_id,
            })
        return detections
