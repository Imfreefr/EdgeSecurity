import sys

print("EdgeSecurity v6.1 - verificação do ambiente")
print(f"Python: {sys.version.split()[0]}")

try:
    import fastapi
    print(f"FastAPI: {fastapi.__version__}")
except Exception:
    print("FastAPI: não instalado")

try:
    import uvicorn
    print(f"Uvicorn: {uvicorn.__version__}")
except Exception:
    print("Uvicorn: não instalado")

print("\nSe as dependências estiverem instaladas, execute:")
print("1) cd backend")
print("2) python -m uvicorn app:app --host 127.0.0.1 --port 8000")
print("3) Em outro terminal, na pasta principal: python serve.py")
print("4) Abra http://localhost:5500")
