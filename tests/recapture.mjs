import { chromium } from '@playwright/test';
const b=await chromium.launch({channel:'msedge'});
for(const width of [1440,390]){
 const p=await b.newPage({viewport:{width,height:width===390?844:900}});
 await p.goto('http://127.0.0.1:5503/landing.html');await p.waitForTimeout(2000);
 for(const section of ['manifesto','observe','local','control','trace','finale']){
  await p.locator('.'+section).scrollIntoViewIfNeeded();await p.waitForTimeout(1600);
  await p.locator('.'+section).screenshot({path:`.impeccable/review/settled-${section}-${width}.png`});
 }
 await p.close();
}await b.close();
