import { chromium } from "@playwright/test";
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { distanceAt, riskState } from "../src/landing/riskState.js";

for (const [distance, label] of [[4.8, "SEGURO"], [3.1, "SEGURO"], [3, "ATENÇÃO"], [1.6, "ATENÇÃO"], [1.5, "CRÍTICO"], [0.8, "CRÍTICO"]]) {
  assert.equal(riskState(distance).label, label);
  assert.equal(distanceAt((4.8 - distance) / 4), distance);
}

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
    if (width < 900) {
      assert.equal(await page.locator("html.lenis").count(), 0, "native mobile scroll");
      assert.equal(await page.locator("canvas, .pin-spacer").count(), 0);
    }
    await page.screenshot({ path: `${out}/landing-${width}.png` });
    await page.keyboard.press("Tab");
    assert.equal(await page.locator(".skip").evaluate(e => e === document.activeElement), true);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    );
    assert.equal(overflow, false, `landing overflow at ${width}`);
    await page.getByRole("button", { name: "Abrir menu" }).click();
    assert.equal(await page.locator("#staggered-panel").getAttribute("aria-hidden"), "false");
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("#staggered-panel").getAttribute("aria-hidden"), "true");
    assert.equal(
      await page
        .getByRole("button", { name: "Abrir menu" })
        .evaluate((e) => e === document.activeElement),
      true,
    );
    await page.getByRole("button", { name: "Abrir menu" }).click();
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${out}/menu-open-${width}.png` });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
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
    if (width >= 900) {
      assert.equal(await page.locator('.risk-model[data-webgl="ready"]').count(), 1);
      assert.equal(await page.locator('.risk-fallback').isVisible(), false, "no duplicate fallback after React update");
    }
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
    if (width === 1440 || width === 390) {
      for (const section of ["manifesto", "observe", "detect", "local", "control", "trace", "pricing", "faq", "finale"]) {
        await page.locator(`.${section}`).scrollIntoViewIfNeeded();
        await page.waitForTimeout(1000);
        await page.screenshot({ path: `${out}/${section}-${width}.png` });
      }
    }
    await page.evaluate(() => scrollTo(0, 0));
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${out}/full-${width}.png`, fullPage: true });
    assert.deepEqual(errors, [], `browser errors at ${width}`);
    report.push({ surface: "landing", width, errors, overflow });
    await page.close();
  }
  const contrast = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await contrast.goto(`${base}/landing.html`);
  await contrast.waitForTimeout(1500);
  for (const [name, sel] of [["hero", "#top"], ["dark", "#risk"], ["photo", ".finale"], ["foot", ".footer"]]) {
    await contrast.locator(sel).scrollIntoViewIfNeeded();
    await contrast.waitForTimeout(800);
    const theme = await contrast.locator(".edge-landing").getAttribute("data-nav");
    assert.ok(["dark", "light"].includes(theme), `nav theme at ${name}`);
    await contrast.getByRole("button", { name: "Abrir menu" }).click();
    await contrast.waitForTimeout(900);
    assert.equal(await contrast.locator("#staggered-panel").getAttribute("aria-hidden"), "false");
    const box = await contrast.getByRole("button", { name: "Fechar menu" }).boundingBox();
    assert.ok(box && box.width > 0 && box.height > 0, `close visible at ${name}`);
    const pill = await contrast.locator(".sm-bar").evaluate((e) => {
      const m = getComputedStyle(e).backgroundColor.match(/,\s*([\d.]+)\)/);
      return m ? Number(m[1]) : 1;
    });
    assert.ok(pill > 0.3, `pill surface at ${name}`);
    await contrast.screenshot({ path: `${out}/menu-${name}-1440.png` });
    await contrast.keyboard.press("Escape");
    await contrast.waitForTimeout(500);
  }
  const gap = await contrast.evaluate(() => {
    scrollTo(0, 0);
    const bar = document.querySelector(".sm-bar").getBoundingClientRect();
    const h1 = document.querySelector(".hero-title h1").getBoundingClientRect();
    return h1.top >= bar.bottom - 4;
  });
  assert.ok(gap, "hero headline abaixo da navbar");
  await contrast.close();
  report.push({ surface: "nav-contrast", passed: true });
  const reduced = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  await reduced.goto(`${base}/landing.html`);
  await reduced.locator("#risk").scrollIntoViewIfNeeded();
  await reduced.waitForTimeout(500);
  assert.equal(await reduced.locator("canvas").count(), 0);
  assert.equal(await reduced.locator(".pin-spacer").count(), 0);
  assert.equal(await reduced.locator("html.lenis").count(), 0);
  await reduced.emulateMedia({ reducedMotion: "no-preference" });
  await reduced.locator('.risk-model[data-webgl="ready"]').waitFor();
  await reduced.emulateMedia({ reducedMotion: "reduce" });
  await reduced.locator("canvas").waitFor({ state: "detached" });
  assert.equal(await reduced.locator(".pin-spacer, html.lenis").count(), 0, "live preference cleanup");
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
      assert.equal(overflow, false, `${name}: horizontal overflow at ${width}`);
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
  const navigation = await browser.newPage();
  await navigation.route("**/api/**", route => route.fulfill({ json: {} }));
  await navigation.goto(`${base}/landing.html`);
  await navigation.getByRole("link", { name: "Cadastrar minha empresa", exact: true }).first().click();
  await navigation.waitForURL("**/pages/cadastro.html");
  assert.equal(await navigation.locator(".cad-grid").first().evaluate(e => getComputedStyle(e).display), "grid");
  assert.equal(await navigation.locator("canvas, .pin-spacer, html.lenis").count(), 0);
  await navigation.getByRole("link", { name: "Voltar ao site", exact: true }).click();
  await navigation.waitForURL("**/landing.html");
  await navigation.getByRole("link", { name: "Entrar", exact: true }).click();
  await navigation.waitForURL("**/index.html");
  assert.equal(await navigation.locator("canvas, .pin-spacer, html.lenis").count(), 0);
  assert.equal(await navigation.locator("body").getAttribute("style"), null);
  await navigation.goBack();
  await navigation.waitForURL("**/landing.html");
  await navigation.close();
  report.push({ surface: "landing-signup-landing-login-landing", passed: true });
  await writeFile(`${out}/test-results.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
