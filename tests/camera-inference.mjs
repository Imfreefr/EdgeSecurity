import { chromium, expect } from '@playwright/test';

// The production UI, camera capture, Worker and model are real. Account/API
// responses stay in this browser so this check does not create production data.
const base = process.env.EDGE_TEST_URL || 'http://127.0.0.1:5501';
const user = { id: 'camera-smoke', nome: 'Camera smoke', cargo: 'administrador' };
const cameras = [];
const browser = await chromium.launch({ channel: 'msedge', headless: true,
  args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
try {
  const page = await browser.newPage();
  await page.context().grantPermissions(['camera'], { origin: base });
  page.on('pageerror', error => console.error(error.message));
  await page.addInitScript(user => {
    sessionStorage.setItem('edge_token', 'browser-only-smoke');
    sessionStorage.setItem('edge_session', JSON.stringify(user));
  }, user);
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let data = {};
    if (path === '/api/me') data = user;
    else if (path === '/api/users') data = [user];
    else if (path === '/api/cameras') {
      if (route.request().method() === 'POST') {
        const camera = { ...route.request().postDataJSON(), id: 'camera-smoke' };
        cameras.push(camera);
        data = camera;
      } else data = cameras;
    } else if (path === '/api/alerts' || path === '/api/activities') data = [];
    await route.fulfill({ json: data });
  });
  await page.goto(`${base}/pages/cameras.html`);
  await page.waitForFunction(() => window.EdgeDB?.users.length > 0);
  await page.evaluate(() => {
    window.smokeResults = 0;
    const connect = window.EdgeAILocal.connect;
    window.EdgeAILocal.connect = (id, result, error, ready) => connect(id, data => {
      window.smokeResults++;
      result(data);
    }, error, ready);
  });
  await page.locator('#detect-cameras').click();
  await expect(page.locator('#camera-select')).toBeEnabled();
  await page.locator('#camera-select').selectOption({ index: 0 });
  await expect(page.locator('#start-ai')).toBeEnabled();
  await page.locator('#register-camera').click();
  await expect(page.locator('#registered-cameras')).toContainText('Remover');
  await page.locator('#start-ai').click();
  await expect(page.locator('#ai-status')).toHaveText('IA local ao vivo', { timeout: 60000 });
  await page.waitForFunction(() => window.smokeResults >= 3, { timeout: 60000 });
  await page.locator('#stop-ai').click();
  await expect(page.locator('#ai-status')).toHaveText('Detecção desligada');
  console.log('PASS: published camera UI -> video frames -> ONNX Worker -> results -> stop (simulated webcam; API mocked)');
} finally {
  await browser.close();
}
