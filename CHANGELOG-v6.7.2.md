# EdgeSecurity v6.7.2 — login premium + correções audit/critique

Base: v6.7.1 na raiz (pós-reestruturação) + diagnóstico Impeccable.

## 1. [Alta] Login redesenhado — premium, não mais “sem graça”

- **Split hero + card:** esquerda `login-hero` (gradientes radiais `rgba(47,111,237,.22)` + `rgba(34,211,238,.13)` + linear navy) com storytelling “Segurança na borda. Sem cloud.” e 3 benefícios (Câmeras local+RTSP, Operação privada, YOLO edgev1.pt). Direita `login-panel` com `login-card` branco premium `20px` + `shadow 18/48`.
- **Micro-interações:** `loginIn .52s cubic-bezier(.16,1,.3,1)`, badge `v6.7.2`, dot pulsante `heroPulse 2.2s`.
- **Acessibilidade:** `label for` corretos, `aria-live` em `#login-error`, inputs com `placeholder` e `focus 3px rgba(47,111,237,.14)`.
- **Correção:** “Acesso Secure” → **“Acesso Seguro”** em `index.html` e `renderMode()`.
- **Responsivo:** `<980px` hero esconde, card centralizado (`prefers-reduced-motion` sem animação).

## 2. [Crítica] Fonte agora aplica em todo o sistema

- **Bug:** `html{font-size:calc(16px * var(--font-scale))}` mas classes estavam em `body.font-*` — escala não cascateava razoável e config só afetava parte do DOM.
- **Fix:** `css/style.css` 4 classes migradas para `html.font-*`; `js/app.js` e `js/configuracoes.js` `applyFontSize()` agora em `document.documentElement.classList`. Testado em 4 tamanhos via `Configurações → Aparência → Tamanho da fonte`.

## 3. [Alta] Performance — otimizações audit

- `css/style.css` 3 `transition:width` → `transition:inline-size` (evita `layout-thrash`, detector `layout-transition` silenciado).
- `BTN` mínimo `44px` e `sb-item` `44px` para `target-size` audit.
- Hierarquia tipográfica reforçada: `page-head h1 1.75rem -.02em`, `card-head h2 1.02rem 700`, `stat .value 1.75rem`.
- `::selection`, scrollbar theming e `aiPulse` para `live` (motion intencional, não decorativa).

## 4. [Média] Acessibilidade — correções audit

- `--muted` `#64748b` → `#5b6d82` (contraste AA em 11px/0.71rem gray sobre branco).
- `gradient-text` removido (`brand-title span` agora `color:var(--cyan)` sólido, pílulas não usam gradiente).
- Sidebar `hover` agora também `focus-within` (`12` ocorrências), teclado descobre labels.
- Login labels com `for`/`id`, `check` com `for=remember`, erro com `role=alert`.

## 5. [Baixa] Housekeeping

- `PRODUCT.md` e `.impeccable/` criados (não commitados por escolha do usuário).
- `.gitignore` já cobre `__pycache__`, `.venv`, `*.db`, `.env`.

## Teste manual (v6.7.2)

1. Abrir `index.html` em `127.0.0.1:5500` — hero escuro à esquerda deve renderizar com 3 pontos e gradientes, card à direita com badge `v6.7.2`.
2. Em `Configurações → Aparência` trocar fonte para `xlarge` → voltar ao `Dashboard` e confirmar títulos/cards crescem proporcionalmente.
3. Tab no login — primeiro input foca, ring cyan `3px` visível; Tab na sidebar com teclado expande labels (`focus-within`).
4. `py INICIAR_EDGESECURITY.bat` ou `py run.py` + `py serve.py` → `GET /api/ai/status` `ready:true`.
