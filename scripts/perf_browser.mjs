// Browser A/B measurement: deployed baseline vs local candidate loader,
// both use the same real deployment/API and authorized test account.
import {chromium} from '@playwright/test';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const base=process.env.EDGE_TEST_URL || 'https://edgesecurity.vercel.app';
const browser=await chromium.launch({channel:'msedge'});
const page=await browser.newPage({viewport:{width:1440,height:900}});
const reports=[];
await page.addInitScript(()=>window.addEventListener('edge-data-ready',()=>{
  performance.mark('data-ready');
  requestAnimationFrame(()=>requestAnimationFrame(()=>performance.mark('data-painted')));
}));
try {
  await page.goto(base+'/index.html');
  await page.locator('#username').fill(process.env.EDGE_TEST_EMAIL);
  await page.locator('#password').fill(process.env.EDGE_TEST_PASSWORD);
  await page.locator('#auth-submit').click();
  await page.waitForURL('**/pages/dashboard.html');
  await page.locator('#dashboard-stats .stat').first().waitFor();
  const baseline=execFileSync('git',['show','a3076db:js/api.js'],{encoding:'utf8'});
  for (const [variant,source] of [['before',baseline],['candidate',fs.readFileSync('js/api.js','utf8')]]) {
    await page.route('**/js/api.js',route=>route.fulfill({body:source,contentType:'application/javascript'}));
    for(let run=1;run<=3;run++) {
      await page.goto(base+'/pages/usuarios.html');
      await page.waitForFunction(()=>performance.getEntriesByName('data-painted').length>0);
      const metrics=await page.evaluate(()=>({
        layout_dom_ms:performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd,
        data_ready_ms:performance.getEntriesByName('data-ready')[0].startTime,
        data_painted_ms:performance.getEntriesByName('data-painted')[0].startTime,
        requests:performance.getEntriesByType('resource').map(r=>({
          path:new URL(r.name).pathname,initiator:r.initiatorType,start_ms:r.startTime,
          duration_ms:r.duration,status:r.responseStatus,transfer_bytes:r.transferSize,body_bytes:r.encodedBodySize,
        })),
      }));
      reports.push({variant,run,temperature:run===1?'first observed, not proven cold':'warm',...metrics});
      console.log(variant,run,Math.round(metrics.data_painted_ms)+'ms');
    }
    await page.unroute('**/js/api.js');
  }
  fs.writeFileSync('docs/perf-browser-ab.json',JSON.stringify({base,scope:'real browser and production API; only js/api.js replaced in browser memory for controlled A/B; cold start not controlled',reports},null,2));
} finally {await browser.close();}
