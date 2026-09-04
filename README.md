# EdgeSecurity v6.7.4 â€” Plataforma Local com IA no Dispositivo (Edge AI) & SaaS Multiempresa

EdgeSecurity Ã© uma plataforma de seguranÃ§a privada para gestÃ£o local de cÃ¢meras com inferÃªncia de IA executada **directamente no navegador/dispositivo do cliente** (`onnxruntime-web` + `edgev1-int8.onnx`), eliminando a necessidade de servidores VPS com GPU.

> **Tudo em portuguÃªs do Brasil, cÃ³digo formatado, sem dados fictÃ­cios e totalmente auditado.**

---

## ðŸš€ O que hÃ¡ na versÃ£o 6.7.4

### ðŸ¤– IA 100% no Dispositivo (Sem Custo de VPS)
- **Modelo Quantizado:** `edgev1.pt` (5.3MB) â†’ `edgev1.onnx` â†’ `edgev1-int8.onnx` (**~2.7MB**, 3-4x mais rÃ¡pido).
- **Inference Worker:** `js/ai-local.js` roda a inferÃªncia via WebAssembly/WebGL em thread separada (`Worker`), garantindo que o vÃ­deo processe a **8 fps** sem travar a interface.
- **Motor de Risco Local:** `js/risk-engine.js` calcula a distÃ¢ncia em pixels (`gap_pixels`) e os nÃ­veis de risco (**seguro, atenÃ§Ã£o, alto, CRÃTICO**), disparando o alerta sonoro no alto-falante do computador/celular.
- **Hospedagem Hostinger Compartilhada:** Roda com PHP + MySQL estÃ¡tico, permitindo deploy completo no plano bÃ¡sico da Hostinger sem contratar VPS.

### ðŸ¢ SaaS Multiempresa & Assinaturas
- **Isolamento de Dados:** Cada empresa possui um identificador Ãºnico `company_id`. Uma empresa **nunca** acessa dados de outra.
- **Assinatura por Empresa (R$ 149,90/mÃªs):** UsuÃ¡rios ilimitados por conta. Se a assinatura ficar `pendente`, `atrasada` ou `cancelada`, o acesso interno Ã© bloqueado automaticamente pelo servidor com mensagem explicativa e botÃ£o de regularizaÃ§Ã£o.
- **Gateway Mercado Pago:** IntegraÃ§Ã£o preparada via `https://api.mercadopago.com/preapproval` para assinaturas recorrentes com webhook autenticado por HMAC.

### âš¡ Redesenho & Polish da Landing Page e Login
- **Rigor Editorial:** Landing page totalmente reescrita com foco no produto, removendo jargÃµes tÃ©cnicos que nÃ£o interessam ao cliente.
- **Card de PreÃ§os Ajustado:** EspaÃ§amento corrigido entre os benefÃ­cios e o botÃ£o "Assinar agora".
- **Login Protegido:** Corrigido o fluxo de entrada e bloqueado o bypass de criaÃ§Ã£o de administrador via `/setup`.

---

## ðŸ› ï¸ Como Executar em Desenvolvimento

### OpÃ§Ã£o A â€” ExecuÃ§Ã£o Local com Backend Python (FastAPI)
```cmd
INICIAR_EDGESECURITY.bat
```
ou manualmente:
```cmd
py -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt

:: Terminal 1 â€” Backend API
python backend\run.py

:: Terminal 2 â€” Frontend
python serve.py
```
Acesse **http://127.0.0.1:5500** (ou `landing.html`).

### OpÃ§Ã£o B â€” Hospedagem Hostinger (Sem VPS)
1. Suba todo o conteÃºdo da pasta raiz para o `public_html` da sua hospedagem.
2. Certifique-se de que o arquivo quantizado `backend/model/edgev1-int8.onnx` estÃ¡ acessÃ­vel.
3. A detecÃ§Ã£o ocorrerÃ¡ localmente no navegador de cada operador via WebAssembly.

---

## ðŸ›¡ï¸ SeguranÃ§a & Auditoria
- **Sem ExposiÃ§Ã£o de Secrets:** Credenciais e chaves nunca sÃ£o salvas no Git. `.gitignore` protege arquivos `.db`, `.env` e `.onnx` quando necessÃ¡rio.
- **ProteÃ§Ã£o contra Brute Force:** Rate limit no login e cadastro + honeypot `website`.
- **Criptografia & SanitizaÃ§Ã£o:** Suporte a Fernet para dados sensÃ­veis, sanitizaÃ§Ã£o de inputs e headers de seguranÃ§a (`Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`).

---

**EdgeSecurity v6.7.4 Â© 2026** Â· Privado por padrÃ£o Â· IA na Borda.
