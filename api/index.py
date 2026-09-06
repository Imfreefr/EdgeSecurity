import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import os
if os.getenv("VERCEL"):
    os.environ.setdefault("DB_PATH", "/tmp/edgesecurity.db")
    os.environ.setdefault("MODEL_PATH", str(ROOT / "backend" / "model" / "edgev1-int8.onnx"))

from backend.app import app
