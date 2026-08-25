window.EdgeAuth = {
  current() {
    try {
      return JSON.parse(sessionStorage.getItem('edge_session') || localStorage.getItem('edge_session') || 'null');
    } catch (_) {
      return null;
    }
  },

  login(username, password, remember) {
    const value = String(username || '').trim().toLowerCase();
    const u = EdgeDB.users.find(x =>
      (String(x.email).toLowerCase() === value || String(x.nome).toLowerCase() === value) &&
      x.senha === password
    );

    if (!u) return { ok: false, message: 'Usuário ou senha inválidos.' };
    if (u.status !== 'ativo') return { ok: false, message: 'Esta conta não está ativa.' };

    const now = new Date().toISOString();
    u.ultimo_login = now;
    EdgeDB.save();

    const session = { id: u.id, nome: u.nome, email: u.email, cargo: u.cargo, loginAt: Date.now() };
    const storage = remember ? localStorage : sessionStorage;
    storage.setItem('edge_session', JSON.stringify(session));
    return { ok: true, user: session };
  },

  logout() {
    const s = this.current();
    if (s) {
      const u = EdgeDB.users.find(x => x.id === s.id);
      if (u) u.ultimo_logout = new Date().toISOString();
      EdgeDB.save();
    }
    sessionStorage.removeItem('edge_session');
    localStorage.removeItem('edge_session');
  },

  require(role) {
    const s = this.current();
    if (!s) {
      location.href = '../index.html';
      return null;
    }
    if (role && s.cargo !== role) {
      location.href = 'dashboard.html';
      return null;
    }
    return s;
  }
};
