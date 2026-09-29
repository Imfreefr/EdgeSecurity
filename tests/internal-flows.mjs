import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
const base = process.env.EDGE_TEST_URL || 'http://127.0.0.1:5503';
const browser = await chromium.launch({channel:process.env.EDGE_BROWSER || 'msedge'});
const user={id:1,nome:'Teste visual',email:'visual@example.invalid',cargo:'administrador',status:'Ativo',company:{nome_fantasia:'Teste'},subscription:{status:'ativa'}};
try {
 for(const width of [1440,390]) {
  const page=await browser.newPage({viewport:{width,height:width===390?844:900}}), errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  let signupPayload;
  await page.route('**/api/**',async route=>{
   const path=new URL(route.request().url()).pathname;
   let data=[];
   if(path.endsWith('/me'))data=user;
   else if(path.endsWith('/auth/login'))data={token:'test-only',user};
   else if(path.endsWith('/setup/status'))data={has_admin:true};
   else if(path.endsWith('/companies/signup')){signupPayload=route.request().postDataJSON();data={transacao_id:'test-only',valor:149.90};}
   else if(path.endsWith('/reports'))data={cameras:0,active_cameras:0,users:1,active_users:1,online_users:1,alerts:0,open_alerts:0,total_seconds:0,alert_levels:{}};
   else if(path.endsWith('/users'))data=[user];
   else if(path.endsWith('/admin/dashboard'))data={total_companies:0,ativas:0,subs_ativas:0,receita_mensal:0,subs_pendentes:0,subs_atrasadas:0,subs_canceladas:0,bloqueadas:0,pagamentos_recentes:[]};
   await route.fulfill({json:data,headers:{'Access-Control-Allow-Origin':new URL(base).origin,'Access-Control-Allow-Credentials':'true'}});
  });
  await page.goto(`${base}/pages/cadastro.html`);
  for(const [id,value] of Object.entries({razao:'Empresa de teste',fantasia:'Teste',cnpj:'00.000.000/0001-00',cnpj_email:'empresa@example.invalid',adm_nome:'Teste visual',adm_email:'visual@example.invalid',adm_senha:'test-password-123',adm_senha2:'test-password-123'})) await page.locator('#'+id).fill(value);
  await page.locator('#cad-submit').click();await page.waitForURL('**/pagamento.html?tid=test-only');
  assert.equal(signupPayload.admin_email,'visual@example.invalid');assert.equal(signupPayload.nome_fantasia,'Teste');
  assert.equal(await page.locator('#pay-valor').textContent(),'149,90');
  await page.locator('#btn-mock').click();await page.waitForURL('**/index.html');
  await page.locator('#username').fill('visual@example.invalid');await page.locator('#password').fill('test-password-123');
  await page.locator('#auth-submit').click();await page.waitForURL('**/pages/dashboard.html');
  await page.locator('#dashboard-stats .stat').first().waitFor();await page.waitForTimeout(1800);
  await page.screenshot({path:`.impeccable/review/dashboard-${width}.png`,fullPage:true});
  for(const route of ['cameras','usuarios','alertas','relatorios','atividades','configuracoes']){
   await page.goto(`${base}/pages/${route}.html`);await page.waitForTimeout(1000);
   assert.equal(await page.locator('.app-shell').count(),1,route);
   assert.equal(await page.locator('script[src*="landing-"]').count(),0,route);
   assert.equal(await page.locator('.toast.show').count(),0,`${route}: visible error`);
  }
  await page.evaluate(u=>sessionStorage.setItem('edge_session',JSON.stringify({...u,cargo:'super_admin'})),user);
  await page.goto(`${base}/pages/admin.html`);await page.locator('#admin-stats .stat').first().waitFor();
  assert.equal(await page.locator('#admin-stats .stat').count(),8);
  assert.deepEqual(errors,[],`internal browser errors at ${width}`);
  console.log(`Signup → payment → login → dashboard; six internal routes + admin passed at ${width}px (mock API).`);
  await page.close();
 }
} finally {await browser.close();}
