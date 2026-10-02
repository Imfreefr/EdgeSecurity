window.EdgeAuth = {
  // Trade-off consciente: o token Bearer fica em localStorage/sessionStorage
  // (ver EdgeAPI.setToken/token em api.js), o que é comum em SPAs simples mas
  // deixa o token acessível a qualquer script executado na página (risco de
  // exfiltração via XSS). Isso só é seguro na medida em que TODO valor vindo
  // do usuário/API interpolado em innerHTML passar por escapeHtml() sem
  // exceção — não usar innerHTML com dados não sanitizados no futuro.
  current() {
    if (!EdgeAPI.token()) return null;
    try {
      return JSON.parse(
        sessionStorage.getItem("edge_session") ||
          localStorage.getItem("edge_session") ||
          "null",
      );
    } catch (_) {
      return null;
    }
  },
  async login(username, password, remember) {
    const result = await EdgeAPI.post("/auth/login", { username, password });
    sessionStorage.removeItem("edge_session");
    localStorage.removeItem("edge_session");
    EdgeAPI.setToken(result.token, remember);
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem("edge_session", JSON.stringify(result.user));
    return result;
  },
  expire(rejectedToken) {
    // An old in-flight request must never clear a newer login.
    if (!rejectedToken || EdgeAPI.token() !== rejectedToken) return;
    EdgeAPI.clearToken();
    sessionStorage.removeItem("edge_session");
    localStorage.removeItem("edge_session");
    location.href = "/index.html?session=expired";
  },
  async logout() {
    try {
      await EdgeAPI.post("/auth/logout", {});
    } catch (_) {}
    EdgeAPI.clearToken();
    sessionStorage.removeItem("edge_session");
    localStorage.removeItem("edge_session");
    location.href = "../index.html";
  },
  require(role) {
    const s = this.current();
    if (!s) {
      location.href = "../index.html";
      return null;
    }
    if (role && s.cargo !== role) {
      location.href = "dashboard.html";
      return null;
    }
    return s;
  },
};
