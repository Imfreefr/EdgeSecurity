import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const storage=()=>{
  const map=new Map();
  return {getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,String(v)),removeItem:k=>map.delete(k)};
};
const localStorage=storage(),sessionStorage=storage();
let refreshes=0,requests=0;
const context={window:null,localStorage,sessionStorage,location:{},console,Event,
  fetch:async url=>{
    if(url.endsWith('/auth/refresh')) {
      refreshes++; await new Promise(r=>setTimeout(r,10));
      return new Response(JSON.stringify({token:'renewed'}));
    }
    requests++;
    return new Response(JSON.stringify(requests<=3?{detail:'expired'}:{ok:true}),{status:requests<=3?401:200});
  }};
context.window=context;
vm.createContext(context);
for(const file of ['js/api.js','js/auth.js']) vm.runInContext(fs.readFileSync(file,'utf8'),context);
localStorage.setItem('edge_session',JSON.stringify({id:'remembered'}));
localStorage.setItem('edge_token','remembered-token');
sessionStorage.setItem('edge_session',JSON.stringify({id:'tab'}));
sessionStorage.setItem('edge_token','tab-token');
assert.equal(context.EdgeAuth.current().id,'tab');
assert.equal(context.EdgeAPI.token(),'tab-token');
await Promise.all(['/me','/users','/cameras'].map(p=>context.EdgeAPI.get(p)));
assert.equal(refreshes,1,'concurrent 401s share a single refresh');
assert.equal(sessionStorage.getItem('edge_token'),'renewed');
assert.equal(localStorage.getItem('edge_token'),null);
context.EdgeAuth.expire('tab-token');
assert.equal(sessionStorage.getItem('edge_token'),'renewed','late rejected request preserves newer token');
context.EdgeAuth.expire('renewed');
assert.equal(context.EdgeAuth.current(),null);
assert.equal(context.location.href,'/index.html?session=expired');
sessionStorage.setItem('edge_session',JSON.stringify({id:'stale'}));
localStorage.setItem('edge_session',JSON.stringify({id:'other'}));
localStorage.setItem('edge_token','other-token');
assert.equal(context.EdgeAPI.token(),'','never pair a tab user with another storage token');
assert.equal(context.EdgeAuth.current(),null);
context.EdgeAPI.clearToken();
context.fetch=async()=>new Response(JSON.stringify({detail:'revoked'}),{status:401});
sessionStorage.setItem('edge_token','revoked');
await assert.rejects(context.EdgeAPI.get('/me'),/revoked/);
assert.equal(sessionStorage.getItem('edge_token'),null);
assert.equal(context.EdgeAuth.current(),null);
console.log('PASS: matching user/token storage, one concurrent refresh, stale response protection, rejected-session login recovery.');
