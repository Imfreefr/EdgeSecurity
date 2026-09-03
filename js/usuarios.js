const CURRENT_SESSION = EdgeAuth.require("administrador");
const USER_PERMISSIONS = [
  ["visualizar_cameras", "Visualizar câmeras"],
  ["usar_camera_dispositivo", "Usar câmera deste dispositivo"],
  ["gerenciar_cameras", "Gerenciar câmeras"],
  ["visualizar_alertas", "Visualizar alertas"],
  ["visualizar_relatorios", "Visualizar relatórios"],
  ["gerenciar_usuarios", "Gerenciar usuários"],
  ["gerenciar_permissoes", "Gerenciar permissões"],
  ["acessar_configuracoes", "Acessar configurações"],
];
const defaultPermissions = (c) => {
  const a = c === "administrador";
  return Object.fromEntries(
    USER_PERMISSIONS.map(([k]) => [
      k,
      [
        "visualizar_cameras",
        "usar_camera_dispositivo",
        "visualizar_alertas",
        "visualizar_relatorios",
        "acessar_configuracoes",
      ].includes(k) || a,
    ]),
  );
};
function renderUsers() {
  const active = EdgeDB.users.filter((u) => u.status === "ativo").length;
  const online = EdgeDB.users.filter(
    (u) => u.status === "ativo" && u.ultimo_login && !u.ultimo_logout,
  ).length;
  document.getElementById("user-stats").innerHTML = [
    ["Usuários cadastrados", EdgeDB.users.length],
    ["Contas ativas", active],
    [
      "Administradores",
      EdgeDB.users.filter((u) => u.cargo === "administrador").length,
    ],
    ["Sessões atuais", online],
  ]
    .map(
      (x) =>
        `<div class="stat"><div class="label">${x[0]}</div><div class="value">${x[1]}</div><div class="hint">${x[1] ? "Dados no sistema" : x[0] === "Sessões atuais" ? "Ninguém online no momento" : "Nenhum registro ainda"}</div></div>`,
    )
    .join("");
  document.getElementById("users-table").innerHTML = EdgeDB.users.length
    ? `<table><thead><tr><th>Nome</th><th>E-mail</th><th>Cargo</th><th>Status</th><th>Permissões</th><th>Último acesso</th><th>Ações</th></tr></thead><tbody>${EdgeDB.users
        .map((u) => {
          const p = Object.values(u.permissoes || {}).filter(Boolean).length;
          const canDelete =
            (u.cargo !== "administrador" ||
              CURRENT_SESSION.administrador_primario) &&
            u.id !== CURRENT_SESSION.id;
          return `<tr><td>${escapeHtml(u.nome)}</td><td>${escapeHtml(u.email)}</td><td>${escapeHtml(u.cargo)}${u.administrador_primario ? ' <span class="badge blue">primário</span>' : ""}</td><td><span class="badge ${u.status === "ativo" ? "green" : u.status === "bloqueado" ? "red" : "amber"}">${escapeHtml(u.status)}</span></td><td>${p}/${USER_PERMISSIONS.length}</td><td>${u.ultimo_login ? formatDate(u.ultimo_login) : "Nunca"}</td><td><button class="btn btn-secondary btn-small" onclick="editUser('${escapeHtml(u.id)}')">Editar</button> <button class="btn ${u.status === "ativo" ? "btn-danger" : "btn-secondary"} btn-small" onclick="toggleUser('${escapeHtml(u.id)}')">${u.status === "ativo" ? "Bloquear" : "Ativar"}</button> ${canDelete ? `<button class="btn btn-danger btn-small" onclick="deleteUser('${escapeHtml(u.id)}')">Excluir</button>` : ""}</td></tr>`;
        })
        .join("")}</tbody></table>`
    : '<div class="empty">Nenhum usuário cadastrado.</div>';
}
function permissionFields(selected) {
  return USER_PERMISSIONS.map(
    ([k, l]) =>
      `<label class="permission-check"><input type="checkbox" name="perm" value="${k}" ${selected[k] ? "checked" : ""}><span>${l}</span></label>`,
  ).join("");
}
function openUserForm(user = null) {
  const modal = document.getElementById("user-modal"),
    edit = !!user,
    cargo = user?.cargo || "usuario",
    perms = user?.permissoes || defaultPermissions(cargo);
  modal.className = "modal";
  modal.innerHTML = `<div class="modal-box modal-user-card"><div class="card-head"><div><h2>${edit ? "Editar usuário" : "Criar usuário"}</h2><p>${edit ? "Atualize os dados deste usuário." : "Preencha os dados para criar um novo acesso."}</p></div><button class="btn btn-secondary" id="close-user">Fechar</button></div><form id="user-form" class="form-grid"><label>Nome<input id="u-name" required value="${escapeHtml(user?.nome || "")}"></label><label>E-mail<input id="u-email" type="email" required value="${escapeHtml(user?.email || "")}"></label><label>${edit ? "Nova senha (opcional)" : "Senha"}<input id="u-pass" type="password" ${edit ? "" : "required"} minlength="4"></label><label>Cargo<select id="u-role"><option value="usuario" ${cargo === "usuario" ? "selected" : ""}>Usuário</option><option value="administrador" ${cargo === "administrador" ? "selected" : ""}>Administrador</option></select></label><fieldset class="permission-box"><legend>Permissões</legend><div class="permission-grid">${permissionFields(perms)}</div></fieldset><fieldset class="permission-box"><legend>Câmeras permitidas</legend><div class="camera-permission-grid">${EdgeDB.cameras.length ? EdgeDB.cameras.map((c) => `<label class="permission-check"><input type="checkbox" name="cam" value="${c.id}" ${(user?.cameras || []).includes(c.id) ? "checked" : ""}><span>${escapeHtml(c.nome)}</span></label>`).join("") : '<div class="empty">Nenhuma câmera cadastrada ainda.</div>'}</div></fieldset><div id="user-form-error" class="form-error"></div><div class="form-actions"><button class="btn btn-primary" type="submit">${edit ? "Salvar alterações" : "Criar usuário"}</button></div></form></div>`;
  document.getElementById("close-user").onclick = () =>
    (modal.className = "modal hidden");
  document.getElementById("u-role").onchange = (e) => {
    const p = defaultPermissions(e.target.value);
    document.querySelector(".permission-grid").innerHTML = permissionFields(p);
  };
  document.getElementById("user-form").onsubmit = async (e) => {
    e.preventDefault();
    const error = document.getElementById("user-form-error");
    const data = {
      nome: document.getElementById("u-name").value.trim(),
      email: document.getElementById("u-email").value.trim().toLowerCase(),
      senha: document.getElementById("u-pass").value || null,
      cargo: document.getElementById("u-role").value,
      status: user?.status || "ativo",
      permissoes: Object.fromEntries(
        [...document.querySelectorAll('input[name="perm"]')].map((x) => [
          x.value,
          x.checked,
        ]),
      ),
      cameras: [...document.querySelectorAll('input[name="cam"]:checked')].map(
        (x) => x.value,
      ),
    };
    try {
      if (edit) await EdgeAPI.put(`/users/${user.id}`, data);
      else await EdgeAPI.post("/users", data);
      await EdgeData.load();
      modal.className = "modal hidden";
      renderUsers();
      showToast(edit ? "Usuário atualizado." : "Usuário cadastrado.");
    } catch (err) {
      error.textContent = err.message;
    }
  };
}
window.editUser = (id) => {
  const u = EdgeDB.users.find((x) => x.id === id);
  if (u) openUserForm(u);
};
window.toggleUser = async (id) => {
  try {
    await EdgeAPI.patch(`/users/${id}/status`, {});
    await EdgeData.load();
    renderUsers();
    showToast("Status da conta atualizado.");
  } catch (e) {
    showToast(e.message);
  }
};
window.deleteUser = async (id) => {
  const u = EdgeDB.users.find((x) => x.id === id);
  if (!u) return;
  if (
    !confirm(
      `Excluir permanentemente o usuário "${u.nome}"? Esta ação não pode ser desfeita.`,
    )
  )
    return;
  try {
    await EdgeAPI.del(`/users/${id}`);
    await EdgeData.load();
    renderUsers();
    showToast("Usuário excluído.");
  } catch (e) {
    showToast(e.message);
  }
};
document.getElementById("add-user").onclick = () => openUserForm();
window.addEventListener("edge-data-ready", renderUsers);
