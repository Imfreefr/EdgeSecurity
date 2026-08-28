# EdgeSecurity v6.4 — execução somente local

## 1. Instalar

Use Python 3.11+ (Python 3.12 é suportado). No Windows:

```cmd
cd app
py -m venv .venv
.venv\Scripts\activate
py -m pip install --upgrade pip
py -m pip install -r backend\requirements.txt
```

## 2. Modelo

Coloque `edgev1.pt` em:

`app\backend\model\edgev1.pt`

## 3. Iniciar backend

Terminal 1:

```cmd
cd app\backend
..\.venv\Scripts\python.exe run.py
```

Backend: `http://127.0.0.1:8000`

## 4. Iniciar frontend

Terminal 2:

```cmd
cd app
.venv\Scripts\python.exe serve.py
```

Frontend: `http://127.0.0.1:5500`

## 5. Testar IA

Abra `http://127.0.0.1:8000/api/ai/status`. O campo `ready` deve aparecer como `true`.

Depois abra o EdgeSecurity em `http://127.0.0.1:5500`, entre no sistema, cadastre/detecte a câmera e use **Iniciar análise YOLO26**.

