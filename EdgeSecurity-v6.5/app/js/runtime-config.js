/*
 * EdgeSecurity - configuração de rede para acesso externo.
 *
 * COMO USAR COM DOIS CLOUDFLARE QUICK TUNNELS:
 * 1. Abra um tunnel para o frontend (:5500).
 * 2. Abra outro tunnel para o backend (:8000).
 * 3. Copie a URL HTTPS do backend para EDGE_API_BASE abaixo.
 * 4. Recarregue o frontend no tablet.
 *
 * Exemplo:
 * window.EDGE_API_BASE = 'https://seu-backend.trycloudflare.com';
 *
 * Deixe vazio ('') para usar detecção automática em localhost/LAN.
 */
window.EDGE_API_BASE = '';
