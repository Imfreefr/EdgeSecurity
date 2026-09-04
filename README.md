# EdgeSecurity v6.7.3 — Plataforma Local com IA no Dispositivo (Edge AI) & SaaS Multiempresa

EdgeSecurity é uma plataforma de segurança privada para gestão local de câmeras com inferência de IA executada **directamente no navegador/dispositivo do cliente** (`onnxruntime-web` + `edgev1-int8.onnx`), eliminando a necessidade de servidores VPS com GPU.

> **Tudo em português do Brasil, código formatado, sem dados fictícios e totalmente auditado.**

---

## 🚀 O que há na versão 6.7.3

### 🤖 IA 100% no Dispositivo (Sem Custo de VPS)
- **Modelo Quantizado:** `edgev1.pt` (5.3MB) → `edgev1.onnx` → `edgev1-int8.onnx` (**~2.7MB**, 3-4x mais rápido).
- **Inference Worker:** `js/ai-local.js` roda a inferência via WebAssembly/WebGL em thread separada (`Worker`), garantindo que o vídeo processe a **8 fps** sem travar a interface.
- **Motor de Risco Local:** `js/risk-engine.js` calcula a distância em pixels (`gap_pixels`) e os níveis de risco (**seguro, atenção, alto, CRÍTICO**), disparando o alerta sonoro no alto-falante do computador/celular.
- **Hospedagem Hostinger Compartilhada:** Roda com PHP + MySQL estático, permitindo deploy completo no plano básico da Hostinger sem contratar VPS.

### 🏢 SaaS Multiempresa & Assinaturas
- **Isolamento de Dados:** Cada empresa possui um identificador único `company_id`. Uma empresa **nunca** acessa dados de outra.
- **Assinatura por Empresa (R$ 149,90/mês):** Usuários ilimitados por conta. Se a assinatura ficar `pendente`, `atrasada` ou `cancelada`, o acesso interno é bloqueado automaticamente pelo servidor com mensagem explicativa e botão de regularização.
- **Gateway Mercado Pago:** Integração preparada via `https://api.mercadopago.com/preapproval` para assinaturas recorrentes com webhook autenticado por HMAC.

### ⚡ Redesenho & Polish da Landing Page e Login
- **Rigor Editorial:** Landing page totalmente reescrita com foco no produto, removendo jargões técnicos que não interessam ao cliente.
- **Card de Preços Ajustado:** Espaçamento corrigido entre os benefícios e o botão "Assinar agora".
- **Login Protegido:** Corrigido o fluxo de entrada e bloqueado o bypass de criação de administrador via `/setup`.

---

## 🛠️ Como Executar em Desenvolvimento

### Opção A — Execução Local com Backend Python (FastAPI)
```cmd
INICIAR_EDGESECURITY.bat
```
ou manualmente:
```cmd
py -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt

:: Terminal 1 — Backend API
python backend\run.py

:: Terminal 2 — Frontend
python serve.py
```
Acesse **http://127.0.0.1:5500** (ou `landing.html`).

### Opção B — Hospedagem Hostinger (Sem VPS)
1. Suba todo o conteúdo da pasta raiz para o `public_html` da sua hospedagem.
2. Certifique-se de que o arquivo quantizado `backend/model/edgev1-int8.onnx` está acessível.
3. A detecção ocorrerá localmente no navegador de cada operador via WebAssembly.

---

## 🛡️ Segurança & Auditoria
- **Sem Exposição de Secrets:** Credenciais e chaves nunca são salvas no Git. `.gitignore` protege arquivos `.db`, `.env` e `.onnx` quando necessário.
- **Proteção contra Brute Force:** Rate limit no login e cadastro + honeypot `website`.
- **Criptografia & Sanitização:** Suporte a Fernet para dados sensíveis, sanitização de inputs e headers de segurança (`Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`).

---

**EdgeSecurity v6.7.3 © 2026** · Privado por padrão · IA na Borda.
