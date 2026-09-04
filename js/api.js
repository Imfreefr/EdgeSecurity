const API_BASE = (window.EDGE_API_BASE || "http://127.0.0.1:8000") + "/api";

window.EdgeAPI = {
  base() {
    return API_BASE;
  },
  token() {
    return (
      localStorage.getItem("edge_token") ||
      sessionStorage.getItem("edge_token") ||
      ""
    );
  },
  async request(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    const token = this.token();
    if (token) headers.Authorization = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });

    let body = null;
    try {
      body = await res.json();
    } catch (_) {
      // Algumas respostas de streaming ou não-JSON não possuem corpo JSON.
    }

    if (!res.ok) {
      throw new Error(
        body?.detail ||
          `Falha de comunicação com o serviço. Tente novamente (${res.status}).`,
      );
    }

    return body;
  },
  get(path) {
    return this.request(path);
  },
  post(path, data) {
    return this.request(path, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  put(path, data) {
    return this.request(path, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },
  patch(path, data) {
    return this.request(path, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  del(path) {
    return this.request(path, {
      method: "DELETE",
    });
  },
  setToken(token, remember) {
    (remember ? localStorage : sessionStorage).setItem("edge_token", token);
  },
  clearToken() {
    localStorage.removeItem("edge_token");
    sessionStorage.removeItem("edge_token");
  },
};

window.EdgeDB = {
  users: [],
  cameras: [],
  alerts: [],
  activities: [],
  usage: [],
};

window.EdgeData = {
  async load() {
    const session = EdgeAuth.current();
    if (!session) return;
    if (session.cargo === "super_admin") {
      location.href = "admin.html";
      return;
    }
    try {
      const me = await EdgeAPI.get("/me");
      if (me.subscription && me.subscription.status !== "ativa") {
        const msg = me.subscription.status === "pendente" ? "Pagamento pendente. Finalize sua assinatura para acessar o sistema." : me.subscription.status === "atrasada" || me.subscription.status === "bloqueada" ? "Sua assinatura está vencida. Regularize o pagamento para continuar." : me.subscription.status === "cancelada" ? "Sua assinatura foi cancelada." : "Assinatura inativa.";
        document.body.innerHTML = `<div style="min-height:100vh;display:grid;place-items:center;padding:24px;background:#f8fafc"><div style="max-width:520px;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:28px;text-align:center;box-shadow:0 10px 28px rgba(15,23,42,.07)"><div style="display:inline-flex;padding:8px 12px;border-radius:999px;background:#fef3c7;border:1px solid #fde68a;color:#92400e;font-size:.72rem;font-weight:700">ASSINATURA ${escapeHtml(me.subscription.status.toUpperCase())}</div><h1 style="margin-top:14px;font-size:1.35rem;font-weight:800">Assinatura vencida</h1><p style="margin-top:8px;color:#475569;font-size:.85rem;line-height:1.6">${escapeHtml(msg)}</p><p style="margin-top:6px;color:#64748b;font-size:.78rem">Empresa: ${escapeHtml(me.company ? me.company.nome_fantasia : "")} • Próximo vencimento: ${me.subscription.proximo_vencimento ? formatDate(me.subscription.proximo_vencimento) : "—"}</p><div style="margin-top:16px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap"><a class="btn btn-primary" href="pagamento.html?tid=${encodeURIComponent(me.subscription.transacao_id || "")}">Regularizar pagamento</a><button class="btn btn-secondary" onclick="EdgeAuth.logout()">Sair</button></div></div></div>`;
        return;
      }
    } catch (e) {
      if (String(e.message).includes("Assinatura") || String(e.message).includes("Pagamento") || String(e.message).includes("Empresa bloqueada") || String(e.message).includes("cancelada")) {
        document.body.innerHTML = `<div style="min-height:100vh;display:grid;place-items:center;padding:24px;background:#f8fafc"><div style="max-width:520px;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:28px;text-align:center"><h1 style="font-size:1.25rem;font-weight:800">Acesso bloqueado</h1><p style="margin-top:8px;color:#475569">${escapeHtml(e.message)}</p><div style="margin-top:16px"><button class="btn btn-secondary" onclick="EdgeAuth.logout()">Sair</button> <a class="btn btn-primary" href="pagamento.html">Regularizar</a></div></div></div>`;
        return;
      }
    }
    EdgeDB.cameras = await EdgeAPI.get("/cameras");
    EdgeDB.alerts = await EdgeAPI.get("/alerts");
    if (session.cargo === "administrador") {
      EdgeDB.users = await EdgeAPI.get("/users");
      EdgeDB.activities = await EdgeAPI.get("/activities");
    } else {
      EdgeDB.users = [await EdgeAPI.get("/me")];
      EdgeDB.activities = [];
    }
    window.dispatchEvent(new Event("edge-data-ready"));
  },
};

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>'"]/g,
    (c) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "'": "&#39;",
        '"': "&quot;",
      })[c],
  );
}

function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function cameraById(id) {
  return EdgeDB.cameras.find((camera) => String(camera.id) === String(id));
}

function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;

  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove("show"), 3000);
}
