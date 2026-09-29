import { chromium } from '@playwright/test';
const b=await chromium.launch({channel:'msedge'}),p=await b.newPage();
p.on('pageerror',e=>console.log('ERROR',e.message));p.on('console',m=>console.log(m.type(),m.text()));
await p.route('**/api/**',async r=>{console.log('API',r.request().url());await r.fulfill({json:r.request().url().endsWith('/me')?{subscription:{status:'ativa'}}:[],headers:{'Access-Control-Allow-Origin':'*'}})});
await p.goto('http://127.0.0.1:5174/index.html');await p.evaluate(()=>{sessionStorage.setItem('edge_session',JSON.stringify({id:1,nome:'Teste',cargo:'administrador'}));sessionStorage.setItem('edge_token','visual-test')});await p.goto('http://127.0.0.1:5174/pages/dashboard.html');await p.waitForTimeout(3000);console.log(await p.locator('body').innerText());await b.close();
