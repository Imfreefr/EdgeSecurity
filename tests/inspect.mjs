import { chromium } from '@playwright/test';
const b=await chromium.launch({channel:'msedge'});
const p=await b.newPage({viewport:{width:1440,height:900}});
p.on('pageerror',e=>console.log('ERROR',e.message));p.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',m.text())});
await p.goto('http://127.0.0.1:5174/landing.html');await p.waitForTimeout(2500);await p.screenshot({path:'.impeccable/review/desktop.png'});
console.log(await p.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth,fonts:document.fonts.status})));
await p.setViewportSize({width:390,height:844});await p.waitForTimeout(1000);await p.screenshot({path:'.impeccable/review/mobile.png'});
await b.close();

