import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";

const base = process.env.EDGE_TEST_URL || "http://127.0.0.1:5174";
const browser = await chromium.launch({
  channel: process.env.EDGE_BROWSER || "msedge",
});
const out = ".impeccable/review";
await mkdir(out, { recursive: true });
const report = [];
try {
  for (const [width, height] of [
    [1920, 1080],
    [1440, 900],
    [768, 1024],
    [390, 844],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    await page.goto(`${base}/landing.html`);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${out}/landing-${width}.png` });
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    );
    assert.equal(overflow, false, `landing overflow at ${width}`);
    await page.getByRole("button", { name: "Menu", exact: true }).click();
    assert.equal(await page.locator("dialog").evaluate((e) => e.open), true);
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("dialog").evaluate((e) => e.open), false);
    assert.equal(
      await page
        .getByRole("button", { name: "Menu", exact: true })
        .evaluate((e) => e === document.activeElement),
      true,
    );
    // Visit the full scroll narrative so lazy images, WebGL and reveal timelines run.
    const total = await page.evaluate(
      () => document.documentElement.scrollHeight,
    );
    for (let y = 0; y < total; y += height * 0.85) {
      await page.evaluate((y) => scrollTo(0, y), y);
      await page.waitForTimeout(80);
    }
    await page.waitForTimeout(700);
    assert.equal(
      await page
        .locator("img")
        .evaluateAll((images) =>
          images.every((i) => i.complete && i.naturalWidth > 0),
        ),
      true,
    );
    await page.getByRole("button", { name: "Operador", exact: true }).click();
    assert.equal(
      await page.locator(".restricted").textContent(),
      "CAM 03Restrita",
    );
    await page.locator(".faq summary").first().click();
    assert.equal(
      await page
        .locator(".faq details")
        .first()
        .evaluate((e) => e.open),
      true,
    );
    await page.locator("#risk").scrollIntoViewIfNeeded();
    await page.waitForTimeout(700);
    await page.screenshot({ path: `${out}/risk-${width}.png` });
    await page
      .getByRole("button", { name: "Desativar visão computacional" })
      .click();
    assert.equal(
      await page
        .locator(".risk-model")
        .evaluate((e) => e.classList.contains("vision-on")),
      false,
    );
    await page
      .getByRole("button", { name: "Ativar visão computacional" })
      .click();
    for (const value of ["4.8", "2.1", "0.8"]) {
      await page.locator("input[type=range]").fill(value);
      await page.locator("input[type=range]").dispatchEvent("input");
      assert.ok(
        (await page.locator(".distance output").textContent()).startsWith(
          value,
        ),
      );
    }
    assert.equal(await page.locator(".risk-state").textContent(), "CRÍTICO");
    await page.evaluate(() => scrollTo(0, 0));
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${out}/full-${width}.png`, fullPage: true });
    assert.deepEqual(errors, [], `browser errors at ${width}`);
    report.push({ surface: "landing", width, errors, overflow });
    await page.close();
  }
  const reduced = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  await reduced.goto(`${base}/landing.html`);
  await reduced.locator("#risk").scrollIntoViewIfNeeded();
  await reduced.waitForTimeout(500);
  assert.equal(await reduced.locator("canvas").count(), 0);
  assert.equal(await reduced.locator(".pin-spacer").count(), 0);
  await reduced.close();
  report.push({ surface: "reduced-motion", passed: true });

  // Contract fixtures: no live signups, charges or account changes are made.
  const user = {
    id: 1,
    nome: "Teste visual",
    cargo: "administrador",
    company: { nome_fantasia: "Empresa de teste" },
    subscription: { status: "ativa" },
  };
  for (const [width, height] of [
    [1440, 900],
    [390, 844],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } }),
      errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/api/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let data = [];
      if (path.endsWith("/auth/login"))
        data = { token: "visual-test-only", user };
      else if (path.endsWith("/me")) data = user;
      else if (path.endsWith("/companies/signup"))
        data = { transacao_id: "visual-test", valor: 149.9 };
      else if (path.endsWith("/auth/heartbeat")) data = { ok: true };
      await route.fulfill({
        json: data,
        headers: {
          "Access-Control-Allow-Origin": new URL(base).origin,
          "Access-Control-Allow-Credentials": "true",
        },
      });
    });
    for (const [name, path] of [
      ["cadastro", "pages/cadastro.html"],
      ["login", "index.html"],
      ["pagamento", "pages/pagamento.html"],
    ]) {
      await page.goto(`${base}/${path}`);
      await page.waitForTimeout(350);
      assert.equal(await page.locator('script[src*="landing"]').count(), 0);
      assert.equal(await page.locator("canvas").count(), 0);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      report.push({ surface: name, width, overflow });
      await page.screenshot({
        path: `${out}/${name}-${width}.png`,
        fullPage: true,
      });
      if (name === "cadastro") {
        assert.equal(
          await page
            .locator(".cad-grid")
            .first()
            .evaluate((e) => getComputedStyle(e).display),
          "grid",
        );
        await page.locator("#cad-submit").click();
        assert.ok(
          (await page.locator("#cad-error").textContent()).includes("Senha"),
        );
      }
    }
    await page.evaluate((u) => {
      sessionStorage.setItem("edge_session", JSON.stringify(u));
      sessionStorage.setItem("edge_token", "visual-test-only");
    }, user);
    await page.goto(`${base}/pages/dashboard.html`);
    await page.locator("#dashboard-stats .stat").first().waitFor();
    await page.waitForTimeout(1600);
    await page.screenshot({
      path: `${out}/dashboard-${width}.png`,
      fullPage: true,
    });
    assert.equal(await page.locator("#dashboard-stats .stat").count(), 4);
    assert.deepEqual(errors, []);
    report.push({ surface: "dashboard", width, errors });
    await page.close();
  }
  await writeFile(`${out}/test-results.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
