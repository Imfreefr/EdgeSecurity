import sys
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("DB_PATH", "/tmp/edgesecurity.db")
os.environ.setdefault("MODEL_PATH", str(ROOT / "backend" / "model" / "edgev1-int8.onnx"))
os.environ["AI_LOCAL"] = "false"

from unittest.mock import MagicMock
sys.modules.setdefault("cv2", MagicMock())
sys.modules.setdefault("ultralytics", MagicMock())

from backend.app import app
