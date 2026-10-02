import assert from 'node:assert/strict';
import {chromium} from '@playwright/test';
import fs from 'node:fs';
const base=process.env.EDGE_TEST_URL || 'http://127.0.0.1:8000';
const browser=await chromium.launch({channel:'msedge'});
const page=await browser.newPage();
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
const results=[];
try {
  await page.goto(base+'/index.html');
  await page.locator('#username').fill(process.env.EDGE_TEST_EMAIL || 'admin-a@example.invalid');
  await page.locator('#password').fill(process.env.EDGE_TEST_PASSWORD || 'test-password-123');
  await page.locator('#auth-submit').click();
  await page.waitForURL('**/pages/dashboard.html');
  const sizes=[[1920,1080],[1440,900],[1366,768],[1280,720],[1024,768],[768,1024],[430,932],[390,844],[360,800]];
  for(const [width,height] of process.env.EDGE_WIDTH ? sizes.filter(s=>process.env.EDGE_WIDTH.split(',').map(Number).includes(s[0])) : sizes) {
    await page.setViewportSize({width,height});
    for(const route of ['dashboard','usuarios','cameras','alertas','relatorios','atividades','configuracoes']) {
      await page.goto(`${base}/pages/${route}.html`);
      await page.waitForFunction(()=>!!window.EdgeDB?.users?.length);
      await page.waitForTimeout(800);
      const check=async()=>page.evaluate(()=>{
        const s=document.querySelector('.sidebar').getBoundingClientRect();
        const c=document.querySelector('.content').getBoundingClientRect();
        return {overflow:Math.max(document.body.scrollWidth,document.documentElement.scrollWidth)>innerWidth+1,sidebarRight:s.right,contentLeft:c.left,contentRight:c.right};
      });
      let state=await check();
      if(state.overflow) console.log(await page.evaluate(()=>Array.from(document.querySelectorAll('.content *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right})).slice(0,20)));
      assert(!state.overflow,`${route} ${width}: page overflow ${JSON.stringify(state)}`);
      if(width>=768) {
        await page.locator('.sidebar').hover();
        await page.waitForTimeout(600);
        state=await check();
        assert(state.contentLeft>=state.sidebarRight-1,`${route} ${width}: overlap ${JSON.stringify(state)}`);
        assert(!state.overflow,`${route} ${width}: expanded overflow`);
        await page.mouse.move(width-5,height-5);
      } else {
        assert.equal(state.contentLeft,0);
        await page.locator('#menu-btn').click();
        await page.locator('.drawer-open').waitFor();
        await page.locator('#m-scrim').click({position:{x:width-5,y:height/2}});
        assert.equal(await page.locator('.drawer-open').count(),0);
        await page.waitForTimeout(350);
        await page.locator('#menu-btn').click();
        await page.locator('.drawer-open').waitFor();
        await page.waitForTimeout(500);
        if(process.env.EDGE_DEBUG) console.log(await page.locator('.sb-close').evaluate(e=>({rect:e.getBoundingClientRect().toJSON(),display:getComputedStyle(e).display,sidebar:e.parentElement.getBoundingClientRect().toJSON(),scroll:e.parentElement.scrollTop,body:document.body.className})));
        await page.locator('.sb-close').click();
        assert.equal(await page.locator('.drawer-open').count(),0);
      }
      if(route==='usuarios') {
        await page.locator('#add-user').click();
        await page.locator('#user-modal:not(.hidden)').waitFor();
        assert(await page.locator('#user-modal').evaluate(e=>e.scrollWidth<=innerWidth+1),`modal ${width}`);
        await page.locator('#close-user').click();
      }
      if([1440,390].includes(width)) {
        fs.mkdirSync('.impeccable/responsive',{recursive:true});
        await page.screenshot({path:`.impeccable/responsive/${route}-${width}.png`,fullPage:true});
      }
      results.push({route,width,height,...state});
    }
    console.log(`PASS ${width}x${height}: seven pages`);
  }
  assert.deepEqual(errors,[]);
  fs.mkdirSync('.impeccable/responsive',{recursive:true});
  fs.writeFileSync('.impeccable/responsive/results.json',JSON.stringify(results,null,2));
  console.log(`PASS: ${results.length} route/viewport combinations; expanded sidebar, mobile overlay, no page overflow/runtime errors.`);
} finally { await browser.close(); }
