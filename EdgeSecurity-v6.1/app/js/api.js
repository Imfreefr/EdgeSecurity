const API_BASE = 'http://localhost:8000/api';
window.EdgeAPI = {
  token(){ return localStorage.getItem('edge_token') || sessionStorage.getItem('edge_token') || ''; },
  async request(path, options={}){
    const headers = {'Content-Type':'application/json', ...(options.headers||{})};
    const token=this.token(); if(token) headers.Authorization=`Bearer ${token}`;
    const res=await fetch(`${API_BASE}${path}`, {...options, headers});
    let body=null; try{ body=await res.json(); }catch(_){ }
    if(!res.ok) throw new Error(body?.detail || 'Erro de comunicação com a API.');
    return body;
  },
  get(path){ return this.request(path); },
  post(path,data){ return this.request(path,{method:'POST',body:JSON.stringify(data)}); },
  put(path,data){ return this.request(path,{method:'PUT',body:JSON.stringify(data)}); },
  patch(path,data){ return this.request(path,{method:'PATCH',body:JSON.stringify(data)}); },
  del(path){ return this.request(path,{method:'DELETE'}); },
  setToken(token, remember){ (remember?localStorage:sessionStorage).setItem('edge_token',token); },
  clearToken(){ localStorage.removeItem('edge_token'); sessionStorage.removeItem('edge_token'); }
};

window.EdgeDB = { users:[], cameras:[], alerts:[], activities:[], usage:[] };
window.EdgeData = {
  async load(){
    const session=EdgeAuth.current();
    if(!session) return;
    EdgeDB.cameras=await EdgeAPI.get('/cameras');
    EdgeDB.alerts=await EdgeAPI.get('/alerts');
    if(session.cargo==='administrador'){
      EdgeDB.users=await EdgeAPI.get('/users');
      EdgeDB.activities=await EdgeAPI.get('/activities');
    } else {
      EdgeDB.users=[await EdgeAPI.get('/me')];
      EdgeDB.activities=[];
    }
    window.dispatchEvent(new Event('edge-data-ready'));
  }
};
function escapeHtml(value){return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
function formatDate(v){if(!v)return '—'; return new Date(v).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'});}
function cameraById(id){return EdgeDB.cameras.find(c=>String(c.id)===String(id));}
function showToast(message){const t=document.getElementById('toast');if(!t)return;t.textContent=message;t.classList.add('show');clearTimeout(t._timer);t._timer=setTimeout(()=>t.classList.remove('show'),3000);}
