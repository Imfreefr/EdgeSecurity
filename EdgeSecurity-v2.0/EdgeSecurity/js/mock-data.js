/* Estado local inicial deliberadamente vazio. Nenhum dado fictício é criado. */
window.EdgeDB = { users: [], cameras: [], alerts: [], activities: [], usage: [] };
const DB_KEY = 'edgesecurity_db_v2';

window.EdgeDB.save = function () {
  localStorage.setItem(DB_KEY, JSON.stringify({
    users: EdgeDB.users,
    cameras: EdgeDB.cameras,
    alerts: EdgeDB.alerts,
    activities: EdgeDB.activities,
    usage: EdgeDB.usage
  }));
};

window.EdgeDB.load = function () {
  try {
    const raw = localStorage.getItem(DB_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    EdgeDB.users = Array.isArray(data.users) ? data.users : [];
    EdgeDB.cameras = Array.isArray(data.cameras) ? data.cameras : [];
    EdgeDB.alerts = Array.isArray(data.alerts) ? data.alerts : [];
    EdgeDB.activities = Array.isArray(data.activities) ? data.activities : [];
    EdgeDB.usage = Array.isArray(data.usage) ? data.usage : [];
  } catch (_) {
    localStorage.removeItem(DB_KEY);
  }
};
EdgeDB.load();
