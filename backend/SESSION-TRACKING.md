# Rastreamento de tempo de sessão

O tempo de utilização agora é persistido no SQLite enquanto a sessão permanece aberta.

- Login registra `ultimo_login` e inicia o cronômetro da sessão no backend.
- O frontend envia um heartbeat a cada 10 segundos para `/api/auth/heartbeat`.
- Cada heartbeat grava apenas o intervalo ainda não registrado, evitando contagem duplicada.
- Logout grava o intervalo restante e `ultimo_logout`.
- Se o navegador/PC for fechado sem logout, o banco conserva o tempo até o último heartbeat (no máximo cerca de 10 segundos de diferença em condições normais).
- `tempo_total_ativo` continua sendo o acumulado persistido no usuário e alimenta os relatórios.
