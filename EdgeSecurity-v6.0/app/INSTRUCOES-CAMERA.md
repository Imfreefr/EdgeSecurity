# Teste da câmera no EdgeSecurity

1. Abra um terminal na pasta do projeto.
2. Execute `python serve.py`.
3. Abra `http://localhost:5500` no navegador.
4. Crie ou entre com um administrador.
5. Abra **Câmeras**.
6. Clique em **Detectar câmeras** e permita o acesso quando o navegador solicitar.
7. Selecione a câmera encontrada.
8. Clique em **Usar câmera**.
9. Depois clique em **Cadastrar câmera selecionada**.

## Se aparecer "Não foi possível acessar a câmera"

- Não abra `index.html` com duplo clique (`file://`).
- Use `http://localhost:5500`.
- Verifique o ícone de câmera/cadeado na barra de endereço e permita a câmera.
- Feche outros programas que estejam usando a webcam (Teams, Zoom, OBS etc.).
- Se o navegador já tiver negado a permissão, abra as permissões do site e redefina a câmera para **Permitir**.

## YOLO26

O botão **Iniciar análise YOLO26** depende do backend em `backend/` e de um modelo treinado em `backend/model/best.pt`. A câmera pode ser testada e cadastrada sem o modelo estar instalado.
