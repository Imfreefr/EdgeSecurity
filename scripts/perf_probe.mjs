// Actual EdgeData loader + real HTTP. Never exports credentials or response bodies.
// Set EDGE_TEST_URL, EDGE_TEST_EMAIL, EDGE_TEST_PASSWORD and EDGE_PERF_OUTPUT.
import fs from 'node:fs';
import vm from 'node:vm';
const base = process.env.EDGE_TEST_URL || 'https://edgesecurity.vercel.app';
const login = await fetch(`${base}/api/auth/login`, {
  method:'POST', headers:{'Content-Type':'application/json'},
  body:JSON.stringify({username:process.env.EDGE_TEST_EMAIL,password:process.env.EDGE_TEST_PASSWORD}),
});
if (!login.ok) throw new Error(`Login HTTP ${login.status}`);
const session = await login.json();
const storage = new Map([['edge_token',session.token],['edge_session',JSON.stringify(session.user)]]);
const reports = [];
for (let run=0; run<3; run++) {
  const requests=[];
  const start=performance.now();
  const context={
    window:null, EDGE_API_BASE:base, console, Event,
    document:{body:{dataset:{page:process.env.EDGE_TEST_PAGE||'usuarios'}}},
    location:{}, localStorage:{getItem:()=>null,removeItem(){}},
    sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    EdgeAuth:{current:()=>session.user}, dispatchEvent(){},
    fetch:async (url,options)=>{
      const begin=performance.now();
      const response=await fetch(url,options);
      const bytes=await response.arrayBuffer();
      requests.push({endpoint:new URL(url).pathname,method:options?.method||'GET',
        start_ms:+(begin-start).toFixed(2),duration_ms:+(performance.now()-begin).toFixed(2),
        status:response.status,bytes:bytes.byteLength,server_timing:response.headers.get('server-timing')});
      return new Response(bytes,{status:response.status,headers:response.headers});
    },
  };
  context.window=context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('js/api.js','utf8'),context);
  const heartbeat=context.EdgeAPI.post('/auth/heartbeat',{});
  await context.EdgeData.load();
  const ready_ms=+(performance.now()-start).toFixed(2);
  await heartbeat;
  reports.push({run:run+1,kind:run?'warm':'first observed (not proven cold)',ready_ms,requests});
}
const result={base,scope:'actual frontend loader + real HTTP; excludes HTML, assets and DOM painting',reports};
if (process.env.EDGE_PERF_OUTPUT) fs.writeFileSync(process.env.EDGE_PERF_OUTPUT,JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));
