import base64
import json
import os
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.detector import SafetyDetector
from services.risk_engine import assess_risk

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "model" / "best.pt"))
CONF = float(os.getenv("AI_CONFIDENCE", "0.40"))
IOU = float(os.getenv("AI_IOU", "0.50"))
FPS = max(1, int(os.getenv("AI_FPS", "8")))

app = FastAPI(title="EdgeSecurity AI API", version="0.1.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5500").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_detector = None


class Health(BaseModel):
    model_loaded: bool
    model_path: str
    classes: list[str]
    target_fps: int


def get_detector():
    global _detector
    if _detector is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Modelo não encontrado: {MODEL_PATH}")
        _detector = SafetyDetector(MODEL_PATH, CONF, IOU)
    return _detector


@app.get("/api/health", response_model=Health)
def health():
    try:
        detector = get_detector()
        return Health(model_loaded=True, model_path=MODEL_PATH, classes=list(detector.names.values()), target_fps=FPS)
    except Exception:
        return Health(model_loaded=False, model_path=MODEL_PATH, classes=[], target_fps=FPS)


@app.websocket("/ws/detection")
async def detection_socket(websocket: WebSocket):
    await websocket.accept()
    try:
        detector = get_detector()
        await websocket.send_json({"type": "ready", "fps": FPS, "classes": list(detector.names.values())})
        while True:
            message = await websocket.receive_text()
            payload = json.loads(message)
            image_data = payload.get("image")
            if not image_data:
                continue

            if "," in image_data:
                image_data = image_data.split(",", 1)[1]
            raw = base64.b64decode(image_data)
            frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            detections = detector.infer(frame)
            risk = assess_risk(detections)
            await websocket.send_json({
                "type": "result",
                "camera_id": payload.get("camera_id"),
                "detections": detections,
                "risk": risk,
            })
    except WebSocketDisconnect:
        return
    except FileNotFoundError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close(code=1011)
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        finally:
            await websocket.close(code=1011)
