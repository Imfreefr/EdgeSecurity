import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
await mkdir('.impeccable/review',{recursive:true});
const b=await chromium.launch({channel:"msedge"}); const p=await b.newPage({viewport:{width:1440,height:900}});
await p.goto('http://127.0.0.1:5501/landing.html'); await p.waitForTimeout(2000); await p.screenshot({path:'.impeccable/review/before.png'});
await p.goto('https://casadisolare.com/');await p.waitForTimeout(2500);await p.screenshot({path:'.impeccable/review/reference.png'});await b.close();

