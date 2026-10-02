import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

async function scenario({role='administrador',fail,subscription='ativa'}={}) {
  const calls=[],pending=[],events=[];
  const session={id:'one',cargo:role};
  const context={window:null,console,Event,location:{},document:{body:{}},
    localStorage:{getItem:()=>null},sessionStorage:{getItem:k=>k==='edge_token'?'test-token':null},
    EdgeAuth:{current:()=>session},dispatchEvent:e=>events.push(e.type),
    fetch:(url,options)=>new Promise(resolve=>{
      const path=new URL(url).pathname;
      calls.push(path);
      assert.equal(options.headers.Authorization,'Bearer test-token');
      assert.equal(options.credentials,'include');
      pending.push(()=>resolve(new Response(JSON.stringify(path===fail?{detail:'Unavailable'}:
        path==='/api/me'?{...session,subscription:{status:subscription}}:[{id:path}]),{status:path===fail?503:200})));
    }),
  };
  context.window=context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('js/api.js','utf8'),context);
  const loaded=context.EdgeData.load();
  loaded.catch(()=>{}); // Observe early rejection while the remaining request is pending.
  assert.equal(calls.length,role==='administrador'?5:3,'independent requests start before any finishes');
  assert.equal(events.length,0);
  pending.slice(1).forEach(done=>done());
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(events.length,0,'no render before /me validates subscription');
  assert.equal(context.EdgeDB.users.length,0,'no partial data published');
  pending[0]();
  if(fail) await assert.rejects(loaded,/Unavailable/); else await loaded;
  assert.equal(events.length,fail||subscription!=='ativa'?0:1);
  if(role!=='administrador') {
    assert.equal(calls.filter(p=>p==='/api/me').length,1);
    assert.equal(context.EdgeDB.users[0].id,'one');
  }
}
await scenario();
await scenario({role:'usuario'});
await scenario({fail:'/api/users'});
await scenario({fail:'/api/me'});
await scenario({subscription:'cancelada'});
console.log('PASS: concurrency, all-or-nothing render, subscription gate, error propagation, single /me for member, Bearer headers');
