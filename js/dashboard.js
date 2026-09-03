function initDashboard() {
  const s = EdgeAuth.current();
  const cams = EdgeDB.cameras;
  const alerts = EdgeDB.alerts;
  document.getElementById("dashboard-stats").innerHTML = [
    [
      "Câmeras cadastradas",
      cams.length,
      cams.length ? "Total no sistema" : "Vá em Câmeras para adicionar",
    ],
    [
      "Câmeras ativas",
      cams.filter((c) => c.status === "online").length,
      cams.length
        ? cams.filter((c) => c.status === "online").length
          ? "Prontas para uso"
          : "Nenhuma ativa no momento"
        : "Cadastre uma câmera primeiro",
    ],
    ["Usuários cadastrados", EdgeDB.users.length, "Contas no sistema"],
    [
      "Alertas abertos",
      alerts.filter((a) => a.status === "Aberto").length,
      "Aguardando verificação",
    ],
  ]
    .map(
      (x) =>
        `<div class="stat"><div class="label">${x[0]}</div><div class="value">${x[1]}</div><div class="hint">${x[2]}</div></div>`,
    )
    .join("");
  const c = cams[0];
  document.getElementById("camera-name").textContent =
    c?.nome || "Nenhuma câmera cadastrada";
  document.getElementById("camera-location").textContent =
    c?.localizacao || "Vá em Câmeras para adicionar a primeira";
  document.getElementById("camera-status").textContent = c
    ? c.status === "online"
      ? "Disponível"
      : "Offline"
    : "Nenhuma câmera cadastrada";
  document.querySelector(".live").style.display =
    c?.status === "online" ? "" : "none";
  document.getElementById("dashboard-camera-btn").onclick = () =>
    (location.href = "cameras.html");
  document.getElementById("recent-alerts").innerHTML = alerts.length
    ? alerts
        .slice(0, 4)
        .map(
          (a) =>
            `<div class="list-item"><div><strong>${escapeHtml(a.tipo)}</strong><br><span>${cameraById(a.camera_id)?.nome || "—"} · ${formatDate(a.data_hora)}</span></div><span class="level ${a.nivel === "Crítico" ? "critical" : a.nivel === "Alto" ? "high" : "normal"}">${a.nivel}</span></div>`,
        )
        .join("")
    : '<div class="empty">Nenhum alerta registrado.</div>';
  document.getElementById("recent-activities").innerHTML = EdgeDB.activities
    .length
    ? `<table><thead><tr><th>Usuário</th><th>Ação</th><th>Descrição</th><th>Data</th></tr></thead><tbody>${EdgeDB.activities
        .slice(0, 6)
        .map(
          (a) =>
            `<tr><td>${escapeHtml(EdgeDB.users.find((u) => u.id === a.usuario_id)?.nome || "—")}</td><td>${escapeHtml(a.acao)}</td><td>${escapeHtml(a.descricao)}</td><td>${formatDate(a.data_hora)}</td></tr>`,
        )
        .join("")}</tbody></table>`
    : '<div class="empty">Nenhuma atividade registrada.</div>';
}
window.addEventListener("edge-data-ready", initDashboard);
