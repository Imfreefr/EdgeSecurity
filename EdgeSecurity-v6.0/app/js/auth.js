window.EdgeAuth = {
  current(){ try{return JSON.parse(sessionStorage.getItem('edge_session')||localStorage.getItem('edge_session')||'null');}catch(_){return null;} },
  async login(username,password,remember){
    const result=await EdgeAPI.post('/auth/login',{username,password});
    EdgeAPI.setToken(result.token,remember);
    const storage=remember?localStorage:sessionStorage; storage.setItem('edge_session',JSON.stringify(result.user));
    return result;
  },
  async logout(){ try{await EdgeAPI.post('/auth/logout',{});}catch(_){} EdgeAPI.clearToken();sessionStorage.removeItem('edge_session');localStorage.removeItem('edge_session');location.href='../index.html'; },
  require(role){const s=this.current();if(!s){location.href='../index.html';return null;}if(role&&s.cargo!==role){location.href='dashboard.html';return null;}return s;}
};
