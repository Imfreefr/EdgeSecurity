const API_BASE = 'http://127.0.0.1:8000/api';

window.EdgeAPI = {
    base() {
        return API_BASE;
    },
    token() {
        return localStorage.getItem('edge_token') || sessionStorage.getItem('edge_token') || '';
    },
    async request(path, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };
        const token = this.token();
        if (token) headers.Authorization = `Bearer ${token}`;

        const res = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers
        });

        let body = null;
        try {
            body = await res.json();
        } catch (_) {
            // Some streaming/non-JSON responses do not have a JSON body.
        }

        if (!res.ok) {
            throw new Error(body?.detail || `Erro de comunicação com a API (${res.status}).`);
        }

        return body;
    },
    get(path) {
        return this.request(path);
    },
    post(path, data) {
        return this.request(path, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    put(path, data) {
        return this.request(path, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    patch(path, data) {
        return this.request(path, {
            method: 'PATCH',
            body: JSON.stringify(data)
        });
    },
    del(path) {
        return this.request(path, {
            method: 'DELETE'
        });
    },
    setToken(token, remember) {
        (remember ? localStorage : sessionStorage).setItem('edge_token', token);
    },
    clearToken() {
        localStorage.removeItem('edge_token');
        sessionStorage.removeItem('edge_token');
    }
};

window.EdgeDB = {
    users: [],
    cameras: [],
    alerts: [],
    activities: [],
    usage: []
};

window.EdgeData = {
    async load() {
        const session = EdgeAuth.current();
        if (!session) return;

        EdgeDB.cameras = await EdgeAPI.get('/cameras');
        EdgeDB.alerts = await EdgeAPI.get('/alerts');

        if (session.cargo === 'administrador') {
            EdgeDB.users = await EdgeAPI.get('/users');
            EdgeDB.activities = await EdgeAPI.get('/activities');
        } else {
            EdgeDB.users = [await EdgeAPI.get('/me')];
            EdgeDB.activities = [];
        }

        window.dispatchEvent(new Event('edge-data-ready'));
    }
};

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
    }[c]));
}

function formatDate(value) {
    if (!value) return '—';
    return new Date(value).toLocaleString('pt-BR', {
        dateStyle: 'short',
        timeStyle: 'short'
    });
}

function cameraById(id) {
    return EdgeDB.cameras.find(camera => String(camera.id) === String(id));
}

function showToast(message) {
    const toast = document.getElementById('toast');
    if (!toast) return;

    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove('show'), 3000);
}
