# EdgeSecurity v6.1 — UI refinada

Versão sem arquivos `.bat`. O projeto usa:

- Frontend estático
- FastAPI
- SQLite
- Python

## Requisitos

Python 3.11 ou superior recomendado.

Verifique:

```cmd
python --version
```

## 1. Instalar dependências

Abra o terminal na pasta `backend`:

```cmd
cd backend
python -m pip install -r requirements.txt
```

## 2. Iniciar a API

Ainda dentro de `backend`:

```cmd
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Mantenha esse terminal aberto.

A API ficará disponível em:

`http://127.0.0.1:8000`

A documentação interativa da API ficará em:

`http://127.0.0.1:8000/docs`

## 3. Iniciar o frontend

Abra um segundo terminal na pasta principal do projeto:

```cmd
python serve.py
```

Mantenha esse segundo terminal aberto.

O frontend ficará disponível em:

`http://localhost:5500`

## 4. Abrir o sistema

Abra no navegador:

`http://localhost:5500`

Não abra `index.html` diretamente com `file:///...`.

## 5. Banco de dados

O SQLite é criado pelo backend conforme a configuração da aplicação. O banco começa sem usuários, câmeras e alertas fictícios.

No primeiro acesso, utilize a configuração inicial para criar o administrador.

## 6. Ordem recomendada para o TCC

1. Confirmar frontend.
2. Confirmar FastAPI.
3. Criar administrador.
4. Criar usuário e permissões.
5. Testar cadastro de câmeras quando houver uma câmera disponível.
6. Treinar e validar o YOLO26.
7. Integrar o modelo ao backend.
8. Implementar análise de risco.
9. Registrar alertas no SQLite.

## Observação

Esta versão não contém arquivos `.bat`. A inicialização é feita diretamente pelos comandos acima.


## Interface v6.1

A interface inclui sidebar recolhível com animação, layout responsivo, estados de foco/hover, sombras, transições e suporte aprimorado ao tema escuro, incluindo formulários e permissões de usuários.
