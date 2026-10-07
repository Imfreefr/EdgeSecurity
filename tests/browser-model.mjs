import { chromium } from 'playwright';

const base = process.env.EDGE_TEST_URL || 'http://127.0.0.1:5501';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage();
  await page.goto(base);
  const result = await page.evaluate(() => new Promise((resolve, reject) => {
    const worker = new Worker('/js/ai-worker.js');
    const timer = setTimeout(() => { worker.terminate(); reject(new Error('Worker initialization/inference timeout')); }, 60000);
    worker.onerror = event => { clearTimeout(timer); worker.terminate(); reject(new Error(event.message)); };
    worker.onmessage = event => {
      if (event.data.type === 'ready') {
        const pixels = new Uint8ClampedArray(640 * 480 * 4);
        worker.postMessage({ type: 'infer', payload: { buffer: pixels.buffer, width: 640, height: 480, cameraId: 'test' } }, [pixels.buffer]);
      } else {
        clearTimeout(timer);
        worker.terminate();
        resolve(event.data);
      }
    };
    worker.postMessage({ type: 'init', payload: { modelUrl: '/assets/edgev1.onnx' } });
  }));
  console.log(JSON.stringify(result));
  if (result.type !== 'result') throw new Error(result.message || 'No inference result');
} finally {
  await browser.close();
}
