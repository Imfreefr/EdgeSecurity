function applyFontSize(size) {
  document.documentElement.classList.remove(
    "font-small",
    "font-normal",
    "font-large",
    "font-xlarge",
  );
  document.documentElement.classList.add("font-" + (size || "normal"));
}
(function () {
  const page = document.body.dataset.page;
  const template = document.getElementById("page-template");
  const original = template ? template.innerHTML : "";
  const s = EdgeAuth.require();
  if (!s) return;
  if (s.cargo === "super_admin") { location.href = "admin.html"; return; }
  const nav = [
    ["dashboard", "bx bx-grid-alt", "Visão geral"],
    ["cameras", "bx bx-video", "Câmeras"],
    ["alertas", "bx bx-bell", "Alertas"],
    ["relatorios", "bx bx-bar-chart-alt-2", "Relatórios"],
    ["atividades", "bx bx-history", "Atividades"],
    ["configuracoes", "bx bx-cog", "Configurações"],
  ];
  if (s.cargo === "administrador")
    nav.splice(2, 0, ["usuarios", "bx bx-group", "Usuários e Permissões"]);
  const companyLabel = s.company ? escapeHtml(s.company.nome_fantasia) : "";
  const subLabel = s.subscription ? `<span style="font-size:.62rem;color:#94a3b8">${escapeHtml(s.subscription.status)}${s.subscription.proximo_vencimento ? " • " + formatDate(s.subscription.proximo_vencimento) : ""}</span>` : "";
  const labels = { dashboard: "Visão geral", cameras: "Câmeras", alertas: "Alertas", relatorios: "Relatórios", atividades: "Atividades", configuracoes: "Configurações", usuarios: "Usuários e Permissões" };
  document.getElementById("app").innerHTML =
    `<div class="app-shell"><header class="m-header"><div class="m-brand"><img src="../assets/logo.png" alt="EdgeSecurity" /><b>EDGE</b></div><span class="m-section">${escapeHtml(labels[page] || page)}</span><span class="m-status"><i></i>LOCAL</span><button id="menu-btn" aria-label="Abrir menu" aria-expanded="false" aria-controls="sidebar"><i class="bx bx-menu" aria-hidden="true"></i></button></header><aside class="sidebar collapsed" id="sidebar"><div class="sb-brand"><img src="../assets/logo.png" alt="EdgeSecurity" /><b>EDGE<span>SECURITY</span><small>Operação local</small></b></div><div class="sb-live" aria-hidden="true"><i></i><span>Sistema online</span></div><nav class="sb-nav">${nav.map((n) => `<button class="sb-item ${page === n[0] ? "active" : ""}" data-go="${n[0]}" title="${n[2]}" aria-label="${n[2]}"><i class="ico ${n[1]}" aria-hidden="true"></i><span class="sb-label">${n[2]}</span></button>`).join("")}</nav><div class="sb-user"><strong>${escapeHtml(s.nome)}</strong><span>${s.cargo === "administrador" ? "Administrador" : "Usuário"}</span>${companyLabel ? `<span style="margin-top:4px;color:#7dd3fc;font-weight:700">${companyLabel}</span>` : ""}${subLabel}</div><button class="sb-logout" id="logout" title="Sair" aria-label="Sair"><i class="bx bx-log-out ico" aria-hidden="true"></i><span class="sb-label">Sair</span></button></aside><div class="m-scrim" id="m-scrim"></div><main class="content"><div class="app-topbar"><span>${escapeHtml(labels[page] || page)} — EdgeSecurity</span><span class="tb-status"><i></i>Operação local</span></div>${original}</main></div><div id="toast" class="toast"></div>`;
  document
    .querySelectorAll("[data-go]")
    .forEach(
      (b) =>
        (b.onclick = () =>
          (location.href =
            b.dataset.go === "dashboard"
              ? "dashboard.html"
              : b.dataset.go + ".html")),
    );
  const sidebar = document.getElementById("sidebar");
  const menuBtn = document.getElementById("menu-btn");
  const scrim = document.getElementById("m-scrim");
  const setDrawer = (open) => {
    document.body.classList.toggle("drawer-open", open);
    menuBtn.setAttribute("aria-expanded", String(open));
    menuBtn.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
  };
  menuBtn.onclick = () => {
    const open = !document.body.classList.contains("drawer-open");
    setDrawer(open);
    if (open) sidebar.querySelector(".sb-item")?.focus();
    else menuBtn.focus();
  };
  scrim.onclick = () => setDrawer(false);
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.body.classList.contains("drawer-open")) {
      setDrawer(false);
      menuBtn.focus();
    }
  });
  const desktopQuery = window.matchMedia("(min-width: 768px)");
  const syncSidebarMode = () => {
    if (desktopQuery.matches) {
      sidebar.classList.add("auto-hide");
      sidebar.classList.remove("collapsed");
    } else {
      sidebar.classList.remove("auto-hide");
      sidebar.classList.remove("collapsed");
    }
  };
  syncSidebarMode();
  desktopQuery.addEventListener?.("change", () => {
    syncSidebarMode();
    setDrawer(false);
  });
  document.getElementById("logout").onclick = () => EdgeAuth.logout();
  document.querySelectorAll(".admin-only").forEach((el) => {
    if (s.cargo !== "administrador") el.remove();
  });
  document.body.classList.toggle(
    "dark",
    localStorage.getItem("edge_theme") === "dark",
  );
  applyFontSize(localStorage.getItem("edge_font") || "normal");
  // Mantém o tempo de sessão enquanto a página fica aberta. O backend grava apenas o
  // trecho ainda não registrado, então heartbeats repetidos nunca contam o mesmo tempo duas vezes.
  const heartbeat = async () => {
    try {
      await EdgeAPI.post("/auth/heartbeat", {});
    } catch (_) {}
  };
  heartbeat();
  const heartbeatTimer = setInterval(heartbeat, 10000);
  window.addEventListener("pagehide", () => clearInterval(heartbeatTimer));
  EdgeData.load().catch((e) => showToast(e.message));
})();
