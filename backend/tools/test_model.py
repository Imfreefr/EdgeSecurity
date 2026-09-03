"""Teste rápido do edgev1.pt em uma imagem.
Uso: python tools/test_model.py caminho\para\imagem.jpg
"""

import sys
from pathlib import Path

from ultralytics import YOLO

BASE = Path(__file__).resolve().parents[1]
MODEL = BASE / "model" / "edgev1.pt"

if not MODEL.exists():
    raise SystemExit(f"Modelo não encontrado: {MODEL}")
if len(sys.argv) != 2:
    raise SystemExit("Uso: python tools/test_model.py caminho\\para\\imagem.jpg")

source = Path(sys.argv[1])
if not source.exists():
    raise SystemExit(f"Imagem não encontrada: {source}")

model = YOLO(str(MODEL))
result = model.predict(source=str(source), conf=0.40, verbose=False)[0]
print("Modelo:", MODEL)
print("Classes:", model.names)
print("Detecções:")
for box in result.boxes:
    cls = int(box.cls.item())
    conf = float(box.conf.item())
    print(f"  - {model.names[cls]}: {conf:.3f}")
print("Teste concluído.")
