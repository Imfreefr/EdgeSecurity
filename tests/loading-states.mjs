import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';

const base = process.env.EDGE_TEST_URL || 'http://127.0.0.1:5503';
const browser = await chromium.launch({ channel: 'msedge' });
const user = { id: 1, nome: 'Teste', email: 'test@example.invalid', cargo: 'administrador', status: 'Ativo', subscription: { status: 'ativa' } };
const areas = {
  dashboard: ['dashboard-stats', 'recent-alerts', 'recent-activities'],
  cameras: ['registered-cameras'],
  alertas: ['alerts-table'],
  relatorios: ['report-stats'],
  atividades: ['activity-stats', 'activities-table'],
  configuracoes: ['account-loading'],
  admin: ['admin-stats', 'admin-payments', 'admin-companies'],
};
try {
  for (const width of [1440, 390]) {
    for (const [name, ids] of Object.entries(areas)) {
      for (const failure of [false, true]) {
        const page = await browser.newPage({ viewport: { width, height: 900 } });
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.addInitScript(u => {
          sessionStorage.setItem('edge_session', JSON.stringify(u));
          sessionStorage.setItem('edge_token', 'test-only');
        }, { ...user, cargo: name === 'admin' ? 'super_admin' : user.cargo });
        let release;
        const gate = new Promise(resolve => { release = resolve; });
        await page.route('**/api/**', async route => {
          await gate;
          const path = new URL(route.request().url()).pathname;
          let data = [];
          if (path.endsWith('/me')) data = user;
          else if (path.endsWith('/users')) data = [user];
          else if (path.endsWith('/reports')) data = { cameras: 0, active_cameras: 0, users: 1, active_users: 1, online_users: 0, alerts: 0, open_alerts: 0, total_seconds: 0, alert_levels: {} };
          else if (path.endsWith('/admin/dashboard')) data = { total_companies: 0, ativas: 0, subs_ativas: 0, receita_mensal: 0, subs_pendentes: 0, subs_atrasadas: 0, subs_canceladas: 0, bloqueadas: 0, pagamentos_recentes: [] };
          await route.fulfill({ status: failure ? 503 : 200, json: failure ? { detail: 'Falha de teste' } : data });
        });
        await page.goto(`${base}/pages/${name}.html`, { waitUntil: 'domcontentloaded' });
        for (const id of ids) {
          await page.locator(`#${id}[aria-busy="true"] [role="status"]`).waitFor();
          assert.match(await page.locator(`#${id}`).textContent(), /Carregando/);
        }
        release();
        for (const id of ids) {
          await page.waitForFunction(id => !document.getElementById(id).hasAttribute('aria-busy'), id);
          if (failure) await page.locator(`#${id} [role="alert"] button`).waitFor();
          else assert.equal(await page.locator(`#${id} [role="status"]`).count(), 0);
        }
        if (name === 'configuracoes') assert.equal(await page.locator('#save-account').isDisabled(), failure);
        assert.deepEqual(errors, [], `${name} ${width}px`);
        await page.close();
      }
    }
    console.log(`PASS: loading → success/error on seven pages at ${width}px.`);
  }
} finally { await browser.close(); }
