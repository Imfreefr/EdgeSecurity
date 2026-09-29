import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
const b=await chromium.launch({channel:'msedge'}),p=await b.newPage({viewport:{width:1440,height:900}}),errors=[];
p.on('pageerror',e=>errors.push(e.message));p.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
for(const port of [5502,5503]){
 await p.goto(`http://127.0.0.1:${port}/landing.html`);await p.waitForTimeout(1800);
 assert.equal(await p.locator('h1').innerText(),'Antes do\nimpacto.');
 await p.locator('#risk').scrollIntoViewIfNeeded();await p.waitForTimeout(800);
 assert.equal(await p.locator('canvas').count(),1);
 console.log('Production smoke passed',port);
}
console.log('Errors',errors);assert.deepEqual(errors,[]);
await p.goto('http://127.0.0.1:5503/landing.html');await p.waitForTimeout(1800);
for(const section of ['hero','manifesto','risk-stage','observe','detect','local','control','trace','product','pricing','faq','finale']){
 await p.locator('.'+section).scrollIntoViewIfNeeded();await p.waitForTimeout(1400);
 await p.locator('.'+section).screenshot({path:`.impeccable/review/section-${section}.png`});
}
await b.close();
