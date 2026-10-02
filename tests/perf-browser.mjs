// Real HTTP/FastAPI browser regression. Start tests/perf_backend.py --serve first.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {chromium} from '@playwright/test';
const base='http://127.0.0.1:8000';
const browser=await chromium.launch({channel:'msedge'});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
const requests=[];
page.on('response',async r=>{
  if(r.url().includes('/api/')) requests.push({path:new URL(r.url()).pathname,status:r.status()});
});
await page.addInitScript(()=>window.addEventListener('edge-data-ready',()=>performance.mark('edge-data-ready')));
try {
  await page.goto(base+'/index.html');
  await page.locator('#username').fill('admin-a@example.invalid');
  await page.locator('#password').fill('test-password-123');
  await page.locator('#auth-submit').click();
  await page.waitForURL('**/pages/dashboard.html');
  await page.locator('#dashboard-stats .stat').first().waitFor();
  for(const name of ['usuarios','cameras','alertas','dashboard','relatorios','atividades','configuracoes']) {
    await page.goto(`${base}/pages/${name}.html`);
    await page.waitForFunction(()=>performance.getEntriesByName('edge-data-ready').length===1);
    if(name==='alertas') await page.locator('#alerts-table table').waitFor();
    if(name==='relatorios') await page.locator('#report-stats .stat').first().waitFor();
    if(name==='atividades') await page.locator('#activity-stats .stat').first().waitFor();
    if(name==='configuracoes') await page.waitForFunction(()=>document.querySelector('#setting-name').value==='admin-a');
    if(name==='usuarios') {
      await page.locator('#users-table tbody tr').waitFor();
      assert.equal(await page.locator('#users-table tbody tr').count(),1);
      assert.equal(await page.locator('.users-skeleton').count(),0);
      fs.mkdirSync('.impeccable/perf',{recursive:true});
      await page.screenshot({path:'.impeccable/perf/users-loaded.png',fullPage:true});
    }
    assert.equal(await page.locator('.toast.show').count(),0,name);
    if(['usuarios','cameras','alertas','dashboard'].includes(name)) {
      await page.reload();
      await page.waitForFunction(()=>performance.getEntriesByName('edge-data-ready').length===1);
      assert.equal(await page.locator('.toast.show').count(),0,`refresh ${name}`);
    }
  }
  await page.setViewportSize({width:390,height:844});
  // A second login revokes the original session under the existing backend policy.
  const replacement=await page.request.post(base+'/api/auth/login',{data:{username:'admin-a@example.invalid',password:'test-password-123'}});
  assert.equal(replacement.status(),200);
  await page.goto(base+'/pages/usuarios.html');
  await page.waitForURL('**/index.html?session=expired');
  assert.match(await page.locator('#login-error').innerText(),/sessão expirou/);
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('edge_token')),null);
  await page.locator('#username').fill('admin-a@example.invalid');
  await page.locator('#password').fill('test-password-123');
  await page.locator('#auth-submit').click();
  await page.waitForURL('**/pages/dashboard.html');
  await page.locator('#dashboard-stats .stat').first().waitFor();
  // Delay responses only for verifying the transient skeleton, not benchmarks.
  await page.route('**/api/users',async route=>{
    const response=await route.fetch();
    await new Promise(resolve=>setTimeout(resolve,700));
    await route.fulfill({response});
  });
  await page.goto(base+'/pages/usuarios.html',{waitUntil:'domcontentloaded'});
  await page.locator('#users-table[aria-busy="true"]').waitFor();
  await page.screenshot({path:'.impeccable/perf/users-loading-mobile.png',fullPage:true});
  await page.locator('#users-table tbody tr').waitFor();
  await page.screenshot({path:'.impeccable/perf/users-loaded-mobile.png',fullPage:true});
  await page.unroute('**/api/users');
  await page.route('**/api/users',route=>route.fulfill({status:503,json:{detail:'test failure'}}));
  await page.reload();
  await page.getByRole('button',{name:'Tentar novamente'}).waitFor();
  assert.equal(await page.locator('.users-skeleton').count(),0);
  await page.unroute('**/api/users');
  await page.getByRole('button',{name:'Tentar novamente'}).click();
  await page.locator('#users-table tbody tr').waitFor();
  const token=await page.evaluate(()=>sessionStorage.getItem('edge_token'));
  await page.locator('#menu-btn').click();
  await page.locator('#logout').click();
  await page.waitForURL('**/index.html');
  const result=await page.request.get(base+'/api/me',{headers:{Authorization:`Bearer ${token}`}});
  assert.equal(result.status(),401);
  assert.deepEqual(errors,[]);
  assert(requests.some(r=>r.status===401),'revoked session must be rejected by the server');
  assert(requests.every(r=>[200,401,503].includes(r.status)),JSON.stringify(requests.filter(r=>![200,401,503].includes(r.status))));
  console.log(JSON.stringify({security:'PASS: login, four refreshes, seven fully rendered pages, logout invalidation',ui:'PASS: desktop/mobile, skeleton, error and retry',request_count:requests.length},null,2));
} finally {await browser.close();}
