import { readFileSync } from "node:fs";
import vm from "node:vm";
import assert from "node:assert/strict";
const workers = [];
let alerts = 0;
const scope = {
  window: {}, document: { currentScript: { src: "https://example.test/js/ai-local.js" } },
  URL, Date, Map, console,
  EdgeAPI: { post: async () => { alerts++; } },
  Worker: class {
    constructor(url) { this.url = String(url); this.messages = []; workers.push(this); }
    postMessage(message) { this.messages.push(message); }
    terminate() {}
  },
};
scope.window.RiskEngine = { assess: () => ({level:"high", pairs:[]}) };
vm.createContext(scope);
vm.runInContext(readFileSync("js/ai-local.js", "utf8"), scope);
const ai = scope.window.EdgeAILocal;
ai.connect("camera-a", () => {}, () => {}, () => {});
const worker = workers[0];
assert.equal(worker.url, "https://example.test/js/ai-worker.js");
worker.onmessage({data:{type:"ready"}});
const canvas = {width:2,height:2,getContext:()=>({getImageData:()=>({data:new Uint8ClampedArray(16)})})};
assert.equal(ai.sendFrame(canvas,"camera-a"),true);
assert.equal(ai.sendFrame(canvas,"camera-a"),false);
worker.onmessage({data:{type:"result",cameraId:"camera-a",detections:[]}});
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(ai.sendFrame(canvas,"camera-a"),true);
worker.onmessage({data:{type:"result",cameraId:"camera-a",detections:[]}});
await new Promise(resolve=>setTimeout(resolve,0));
assert.equal(alerts,1);
ai.close();
assert.equal(ai.sendFrame(canvas,"camera-a"),false);
console.log("PASS: Worker URL, bounded frames, cooldown, shutdown");
