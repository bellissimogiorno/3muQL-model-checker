#!/usr/bin/env node
/**
 * Exercise the real diagram DOM with Chromium, independently of Pyodide.
 * Run: node tests/browser/model-view.mjs (requires Playwright + Chromium).
 * Uses a temporary local HTTP server; no build or internet connection is used.
 */
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require("playwright"); }
catch (error) {
  if (!process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES) throw error;
  playwright = require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, "playwright"));
}
const project = fileURLToPath(new URL("../../", import.meta.url));
const web = path.join(project, "web");
const artifacts = path.resolve(process.env.MUQL_BROWSER_ARTIFACTS || path.join(project, "tests/browser/artifacts"));
await mkdir(artifacts, { recursive: true });
const checks = [], errors = [];
const fixture = `<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model diagram browser verification</title><link rel="stylesheet" href="/style.css">
<style>body{padding:24px}.diagram-fixture{width:100%;max-width:960px;margin:auto}.diagram-fixture h1{font-size:1.5rem}
@media(max-width:480px){body{padding:12px}}</style>
<main class="diagram-fixture"><h1>Counterexample model</h1><article class="property-card" id="mount"></article></main>
<script type="module">
import {createModelView} from '/model-view.js';
window.diagramDownloads=[];window.fullModelRequests=0;
window.mountModel=(model,propertyName=model.property||'Property')=>{
 for(const view of document.querySelectorAll('.model-view')) view.dispose?.();
 document.getElementById('mount').replaceChildren(createModelView(model,{
  propertyName,onDownload:(filename,content,mime)=>window.diagramDownloads.push({filename,content,mime}),
  onShowFullModel:()=>{window.fullModelRequests++;}
 }));
};
window.appendModel=model=>document.getElementById('mount').append(createModelView(model,{propertyName:model.property||'Property'}));
</script></html>`;

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://localhost");
    if (url.pathname === "/") {
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      response.end(fixture); return;
    }
    // Serve only flat, expected static assets, not arbitrary filesystem paths.
    if (!/^\/[A-Za-z0-9-]+\.(js|css|svg)$/.test(url.pathname)) {
      response.writeHead(404); response.end(); return;
    }
    const content = await readFile(path.join(web, url.pathname.slice(1)));
    const type = url.pathname.endsWith(".js") ? "text/javascript" : url.pathname.endsWith(".css") ? "text/css" : "image/svg+xml";
    response.writeHead(200, { "Content-Type": `${type}; charset=utf-8` });
    response.end(content);
  } catch { response.writeHead(404); response.end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const url = `http://127.0.0.1:${server.address().port}/`;
let browser, page, failure;

async function test(name, action) {
  process.stdout.write(`${name} … `);
  try { await action(); checks.push({ name, status: "passed" }); console.log("passed"); }
  catch (error) { checks.push({ name, status: "failed", error: error.stack }); console.log("FAILED"); throw error; }
}
async function witness(name) {
  return JSON.parse(await readFile(path.join(project, "reports", `${name}.countermodel.json`), "utf8"));
}
function synthetic({ points = ["a", "b", "c"], stages = 3, atoms = true, time = "finite" } = {}) {
  const model = {
    property: "Illustrative property",
    scope: { points, values: ["red"], quorums: points.length === 1 ? [[...points]] : [points.slice(0, 1), [...points]], stages, time },
    failure: { point: points.at(-1), time: stages - 1, quorum: points.slice(0, 1), value: "f" },
    valuation: [],
  };
  if (atoms) for (let time = 0; time < stages; time++) for (const [number, point] of points.entries()) {
    model.valuation.push({ predicate: "voted", args: ["red"], point, time, value: ["t", "b", "f"][(number + time) % 3] });
  }
  return model;
}
async function mount(model, propertyName = model.property) {
  await page.evaluate(({ model, propertyName }) => window.mountModel(model, propertyName), { model, propertyName });
  await page.locator(".model-map").waitFor({ state: "visible" });
  await page.waitForFunction(() => [...document.querySelectorAll(".model-map")].every(image => image.complete && image.naturalWidth > 0));
}
async function mapText() { return await page.locator(".model-map").getAttribute("alt"); }
async function visibleMapText() {
  return page.locator(".model-map").evaluate(image => {
    const svg = decodeURIComponent(image.src.slice(image.src.indexOf(",") + 1));
    const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
    return [...doc.querySelectorAll("text")].map(node => node.textContent).join("\n");
  });
}
async function selectAtom(label) { await page.getByLabel("Atoms shown", { exact: true }).selectOption({ label }); }
async function noPageOverflow() {
  const dimensions = await page.evaluate(() => ({ width: innerWidth, content: document.documentElement.scrollWidth }));
  assert.ok(dimensions.content <= dimensions.width + 1, `Page overflows: ${JSON.stringify(dimensions)}`);
}

try {
  browser = await playwright.chromium.launch({ headless: true });
  page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  page.on("pageerror", error => errors.push(error.stack || String(error)));
  await page.goto(url);
  await page.waitForFunction(() => typeof window.mountModel === "function");

  await test("real Voting witness renders exact participants and complete quorum choices", async () => {
    const model = await witness("voting_without_correct--Agreement");
    await mount(model);
    for (const point of model.scope.points) assert.ok((await mapText()).includes(point));
    assert.equal(await page.getByLabel("Quorum highlighted", { exact: true }).locator("option").count(), model.scope.quorums.length);
    assert.equal(await page.getByLabel("Atoms shown", { exact: true }).locator("option").count(), 3);
    assert.equal(await page.getByLabel("Atoms shown", { exact: true }).inputValue(), "");
    assert.ok((await visibleMapText()).includes("vote"));
    assert.ok((await visibleMapText()).includes("observe"));
    assert.equal(await page.locator(".model-time-details").isHidden(), true);
    await noPageOverflow();
    await page.screenshot({ path: path.join(artifacts, "model-desktop.png"), fullPage: true });
  });

  await test("the default diagram and snapshot reveal simultaneous true choices and support keyboard inspection", async () => {
    await mount(await witness("search_choices--AtMostOne"));
    const initialVisible = await visibleMapText();
    assert.ok(initialVisible.includes("chosen(v0)")); assert.ok(initialVisible.includes("chosen(value0)"));
    assert.equal((initialVisible.match(/\bt true\b/g) || []).length, 2);
    const rows = page.locator(".model-snapshot tbody tr");
    assert.equal(await rows.count(), 2);
    assert.deepEqual(await rows.locator("td").allTextContents(), ["t", "t"]);
    assert.deepEqual(await rows.locator("th").allTextContents(), ["chosen(v0)", "chosen(value0)"]);
    await page.getByRole("button", { name: "Inspect atom: chosen(value0)", exact: true }).focus();
    await page.keyboard.press("Enter");
    assert.match(await mapText(), /Selected atom: chosen\(value0\)/);
    assert.equal(await page.locator(":focus").getAttribute("aria-label"), "Inspect atom: chosen(value0)");
    assert.equal(await page.getByLabel("Atoms shown", { exact: true }).inputValue(), JSON.stringify(["chosen", ["value0"]]));
    await page.getByLabel("Atoms shown", { exact: true }).focus();
    await page.emulateMedia({ forcedColors: "active" });
    const selectedStyle = await page.locator('.model-atom-button[aria-pressed="true"]').evaluate(node => {
      const style = getComputedStyle(node);
      return { outline: style.outlineStyle, width: style.outlineWidth };
    });
    assert.deepEqual(selectedStyle, { outline: "solid", width: "2px" },
      "The selected atom must remain distinguishable without color or keyboard focus");
    await page.emulateMedia({ forcedColors: "none" });
    await selectAtom("All atoms");
    assert.equal(await visibleMapText(), initialVisible);
    await page.screenshot({ path: path.join(artifacts, "model-simultaneous-choices.png"), fullPage: true });
  });

  await test("quorum inspection preserves atomic truth and return restores the failure context", async () => {
    const model = synthetic();
    await mount(model);
    const summary = page.locator(".model-quorum-summary");
    assert.equal(await summary.isVisible(), true);
    assert.equal(await summary.locator(".model-quorum-members").textContent(), "Q1 = {a}");
    const summaryBox = await summary.boundingBox(), figureBox = await page.locator(".model-figure").boundingBox();
    assert.ok(summaryBox && figureBox && summaryBox.y + summaryBox.height <= figureBox.y,
      "The complete selected quorum must be prominent before the figure");
    assert.match(await visibleMapText(), /Highlighted quorum Q1/);
    assert.match(await visibleMapText(), /Q1 = \{a\}/);
    assert.match(await visibleMapText(), /Outside Q1/);
    await selectAtom("voted(red)");
    const timeline = await page.locator(".model-time-details .model-timeline").innerText();
    await page.getByLabel("Quorum highlighted", { exact: true }).selectOption({ index: 1 });
    assert.equal(await summary.locator(".model-quorum-members").textContent(), "Q2 = {a, b, c}");
    assert.match(await visibleMapText(), /Q2 = \{a, b, c\}/);
    assert.doesNotMatch(await visibleMapText(), /Outside Q2/);
    assert.equal(await page.locator(".model-time-details .model-timeline").innerText(), timeline);
    await page.getByLabel("Stage", { exact: true }).selectOption({ index: 0 });
    await page.getByRole("button", { name: "Return to failing context", exact: true }).click();
    assert.equal(await page.getByLabel("Stage", { exact: true }).inputValue(), "2");
    assert.equal(await page.getByLabel("Quorum highlighted", { exact: true }).inputValue(), "0");
    assert.equal(await summary.locator(".model-quorum-members").textContent(), "Q1 = {a}");
    assert.ok((await mapText()).includes("c"), "A failing participant outside its quorum must remain visible");
  });

  await test("a one-stage, one-quorum model keeps its fixed context visible with disabled controls", async () => {
    await mount(await witness("search_choices--AtMostOne"));
    assert.equal(await page.getByLabel("Stage", { exact: true }).isDisabled(), true);
    assert.equal(await page.getByLabel("Quorum highlighted", { exact: true }).isDisabled(), true);
    assert.equal(await page.getByLabel("Atoms shown", { exact: true }).isEnabled(), true);
    assert.match(await page.locator(".model-quorum-members").innerText(), /^Q1 = \{.+\}$/);
    assert.match(await visibleMapText(), /Highlighted quorum Q1/);
    assert.match(await visibleMapText(), /In Q1/);
  });

  await test("native stage controls and timeline are usable by keyboard", async () => {
    await mount(synthetic());
    await selectAtom("voted(red)");
    const stage = page.getByLabel("Stage", { exact: true });
    await stage.focus();
    await page.keyboard.press("Home");
    await page.keyboard.press("Enter");
    assert.equal(await stage.inputValue(), "0");
    await page.getByRole("button", { name: "View stage 1", exact: true }).focus();
    await page.keyboard.press("Enter");
    assert.equal(await stage.inputValue(), "1");
    assert.equal(await page.locator(":focus").count(), 1, "Activating a timeline cell must not discard keyboard focus");
  });

  await test("three-stage stuttering witness exposes each represented stage", async () => {
    const model = await witness("fixedpoints--UnfoldingRequiresMonotonicity");
    await mount(model);
    assert.equal(await page.getByLabel("Stage", { exact: true }).locator("option").count(), 3);
    for (let time = 0; time < 3; time++) {
      await page.getByLabel("Stage", { exact: true }).selectOption(String(time));
      assert.match(await mapText(), new RegExp(`stage ${time}`, "i"));
    }
    assert.match(await page.locator(".model-view").innerText(), /stutter|repeats|last stage.*itself/i);
  });

  await test("a constant-false property still has a visible frame without atomic predicates", async () => {
    await mount(synthetic({ atoms: false }));
    assert.match(await page.locator(".model-view").innerText(), /no atomic predicates/i);
    const atom = page.getByLabel("Atoms shown", { exact: true });
    if (await atom.count()) assert.equal(await atom.isDisabled(), true);
    for (const point of ["a", "b", "c"]) assert.ok((await mapText()).includes(point));
    await page.getByRole("button", { name: "Download this view (SVG)", exact: true }).click();
    assert.ok(await page.evaluate(() => window.diagramDownloads.length > 0));
  });

  await test("axiom models have no invented failure marker or return action", async () => {
    const model = synthetic(); delete model.failure;
    await mount(model);
    assert.equal(await page.getByRole("button", { name: "Return to failing context", exact: true }).count(), 0);
    assert.match(await page.locator(".model-view").innerText(), /satisfies all retained axioms/i);
    assert.equal(await page.locator(".model-context").isVisible(), true);
    assert.equal(await page.locator(".model-failure").count(), 0);
    assert.doesNotMatch(await mapText(), /recorded property failure here/i);
  });

  await test("the full selected quorum remains visible when its members are on other participant pages", async () => {
    const points = Array.from({ length: 14 }, (_, i) => `p${i}`), model = synthetic({ points, stages: 1 });
    model.scope.quorums = [["p0", "p6", "p12"], ["p0", "p1"]];
    model.failure.quorum = ["p0", "p6", "p12"];
    await mount(model);
    assert.equal(await page.locator(".model-quorum-members").textContent(), "Q1 = {p0, p6, p12}");
    assert.match(await page.locator(".model-quorum-note").textContent(), /2 on other participant pages/);
    assert.match(await visibleMapText(), /Q1 = \{p0, p6, p12\}/);
    await page.getByLabel("Quorum highlighted", { exact: true }).selectOption("1");
    assert.equal(await page.locator(".model-quorum-members").textContent(), "Q2 = {p0, p1}");
    assert.match(await page.locator(".model-quorum-note").textContent(), /0 shown here/);
    const drawing = await visibleMapText();
    assert.equal((drawing.match(/Outside Q2/g) || []).length, 2);
    assert.doesNotMatch(drawing, /\bIn Q2\b/);
  });

  await test("large scopes paginate participants and time without removing the original failure", async () => {
    const points = Array.from({ length: 20 }, (_, i) => `participant_${i}`);
    await mount(synthetic({ points, stages: 250 }));
    await selectAtom("voted(red)");
    assert.match(await mapText(), /participants 19–20 of 20/);
    assert.equal(await page.locator(".model-time-details .model-timeline tbody tr").count(), 2);
    assert.ok(await page.locator(".model-time-details .model-timeline thead button").count() <= 12);
    await page.getByRole("button", { name: "Previous participants", exact: true }).click();
    assert.match(await mapText(), /participants 13–18 of 20/);
    assert.equal(await page.locator(".model-time-details .model-timeline tbody tr").count(), 6);
    const stage = page.getByLabel("Stage", { exact: true });
    await stage.fill("12"); await stage.press("Tab");
    assert.match(await mapText(), /Stage 12\b/);
    assert.equal(await page.locator(".model-time-details .model-timeline thead button").count(), 12);
    await stage.fill(""); await stage.press("Tab");
    assert.equal(await stage.inputValue(), "12", "A cleared numeric stage must restore the current stage");
    assert.match(await mapText(), /Stage 12\b/);
    await page.getByRole("button", { name: "Return to failing context", exact: true }).click();
    assert.equal(await stage.inputValue(), "249");
    assert.match(await mapText(), /participants 19–20 of 20/);
    assert.match(await mapText(), /participant_19.*recorded property failure here/);
  });

  await test("a large atom list remains searchable with bounded native options", async () => {
    const model = synthetic({ points: ["a", "b"], stages: 1, atoms: false });
    for (let i = 0; i < 125; i++) for (const point of model.scope.points) {
      model.valuation.push({ predicate: `predicate_${i}`, args: [], time: 0, point, value: ["t", "b", "f"][i % 3] });
    }
    await mount(model);
    const atom = page.getByLabel("Atoms shown", { exact: true });
    assert.ok(await atom.locator("option").count() <= 102);
    await page.getByLabel("Find an atom", { exact: true }).fill("predicate_124");
    await atom.selectOption({ label: "predicate_124" });
    assert.match(await mapText(), /Selected atom: predicate_124\./);
    assert.match(await mapText(), /b \(broken\)/);
  });

  await test("the Simpler Paxos overview shows every recorded atom and distinguishes equal-leader models", async () => {
    const agreement = await witness("spax_without_write_affine--Agreement");
    const validity = await witness("spax_without_accept_back--Validity");
    agreement.property = validity.property = "Same title";
    await mount(agreement);
    const agreementText = await visibleMapText();
    for (const label of ["leader", "propose(red)", "propose(blue)", "write(red)", "write(blue)", "accept(red)", "accept(blue)", "decide(red)", "decide(blue)"]) assert.ok(agreementText.includes(label), `Missing visible atom ${label}`);
    assert.equal((agreementText.match(/\bt true\b/g) || []).length, 9);
    await page.screenshot({ path: path.join(artifacts, "model-paxos-overview.png"), fullPage: true });
    await selectAtom("leader"); const agreementLeader = await visibleMapText();
    await mount(validity);
    const validityText = await visibleMapText();
    assert.notEqual(validityText, agreementText);
    assert.match(validityText, /\bf false\b/);
    await selectAtom("leader"); assert.equal(await visibleMapText(), agreementLeader);
  });

  await test("diagram atom paging stays accessible with its table collapsed and restores overview", async () => {
    const model = synthetic({ points: ["a"], stages: 1, atoms: false });
    for (let i = 0; i < 31; i++) model.valuation.push({ predicate: `p${i}`, args: [], time: 0, point: "a", value: ["t", "b", "f"][i % 3] });
    await mount(model);
    assert.equal(await page.locator(".model-snapshot tbody tr").count(), 12);
    await page.locator(".model-snapshot-details summary").click();
    const next = page.getByRole("button", { name: "Next atoms", exact: true });
    assert.equal(await next.isVisible(), true); await next.click();
    assert.match(await visibleMapText(), /\bp12\b/); assert.match(await visibleMapText(), /\bp23\b/);
    assert.doesNotMatch(await visibleMapText(), /\bp0\b/);
    await selectAtom("p13"); assert.match(await mapText(), /Selected atom: p13/);
    await next.click();
    assert.equal(await page.getByLabel("Atoms shown", { exact: true }).inputValue(), "");
    assert.match(await visibleMapText(), /\bp30\b/); assert.equal(await next.isDisabled(), true);
    await page.locator(".model-snapshot-details summary").click();
    assert.equal(await page.locator(".model-snapshot tbody tr").count(), 7);
  });

  await test("whole-model totals and the scope of each view remain explicit during keyboard exploration", async () => {
    const model = synthetic({ points: Array.from({ length: 20 }, (_, i) => `participant_${i}`), stages: 25, atoms: false });
    for (let i = 0; i < 31; i++) for (let time = 0; time < 25; time++) for (const point of model.scope.points) {
      model.valuation.push({ predicate: `atom_${i}`, args: [], time, point, value: ["t", "b", "f"][i % 3] });
    }
    await mount(model);
    assert.equal(await page.getByRole("heading", { name: "Explore this model", exact: true }).count(), 1);
    const whole = await page.locator(".model-scope").innerText();
    for (const phrase of ["Whole model", "20 participants", "2 quorums", "25 stages", "31 atoms"]) assert.ok(whole.includes(phrase));
    const coverage = page.locator(".model-view-summary");
    assert.match(await coverage.innerText(), /1 of 25 stages/);
    assert.match(await coverage.innerText(), /1 of 2 quorums/);
    assert.match(await coverage.innerText(), /Participants 19–20 of 20/);
    assert.match(await coverage.innerText(), /Atoms 1–12 of 31/);
    assert.equal(await page.getByLabel("Atoms shown", { exact: true }).locator("option").first().textContent(), "All atoms (paged)");
    assert.match(await visibleMapText(), /View at stage 24/);
    await selectAtom("atom_16");
    assert.match(await coverage.innerText(), /1 of 31 atoms/);
    const tableCaption = page.locator(".model-snapshot caption");
    assert.match(await tableCaption.innerText(), /[Aa]toms 13–24 of 31/);
    assert.match(await tableCaption.innerText(), /[Pp]articipants 19–20 of 20/);
    await page.getByRole("button", { name: "Previous participants", exact: true }).click();
    await page.getByLabel("Stage", { exact: true }).selectOption("0");
    await page.getByLabel("Quorum highlighted", { exact: true }).selectOption("1");
    assert.equal(await page.locator(".model-scope").innerText(), whole);
    assert.match(await coverage.innerText(), /Participants 13–18 of 20/);
    assert.equal(await page.locator(".model-snapshot-details summary").innerText(), "Atom values at stage 0");
    assert.match(await page.locator(".model-time-details").innerText(), /[Ss]tages 0–11/);
    assert.doesNotMatch(await page.locator(".model-view").innerText() + await visibleMapText(), /Model state/i);
    await noPageOverflow();
    await page.screenshot({ path: path.join(artifacts, "model-view-scope.png"), fullPage: true });
  });

  await test("the complete-data action is keyboard accessible and preserves view selection", async () => {
    await mount(synthetic());
    await selectAtom("voted(red)");
    await page.getByLabel("Stage", { exact: true }).selectOption("0");
    const before = await visibleMapText();
    const count = await page.evaluate(() => window.fullModelRequests);
    await page.getByRole("button", { name: "Full model data", exact: true }).focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.evaluate(() => window.fullModelRequests), count + 1);
    assert.equal(await visibleMapText(), before);
  });

  await test("hostile and long labels are literal text in the page and downloaded SVG", async () => {
    const hostile = '<img src=x onerror="window.diagramInjected=true"> & "😀"';
    const model = synthetic({ points: [hostile, "participant_" + "long".repeat(30), "第三位参与者"], stages: 2 });
    model.property = '<script>window.diagramInjected=true</script> & property';
    for (const row of model.valuation) row.predicate = hostile;
    await mount(model);
    assert.equal(await page.locator(".model-quorum-members").textContent(), `Q1 = {${JSON.stringify(hostile)}}`);
    assert.equal(await page.locator(".model-quorum-summary img, .model-quorum-summary script").count(), 0);
    await page.getByRole("button", { name: "Download this view (SVG)", exact: true }).click();
    const exported = await page.evaluate(() => {
      const item = window.diagramDownloads.at(-1);
      const document = new DOMParser().parseFromString(item.content, "image/svg+xml");
      return { filename: item.filename, mime: item.mime, text: document.documentElement.textContent,
        parseErrors: document.querySelectorAll("parsererror").length,
        scripts: document.querySelectorAll("script,foreignObject,image").length,
        handlers: [...document.querySelectorAll("*")].flatMap(node => [...node.attributes]).filter(a => /^on/i.test(a.name)).length,
        injected: window.diagramInjected === true };
    });
    assert.equal(exported.parseErrors, 0);
    assert.equal(exported.scripts, 0);
    assert.equal(exported.handlers, 0);
    assert.equal(exported.injected, false);
    assert.match(exported.filename, /\.svg$/);
    assert.match(exported.mime, /^image\/svg\+xml/);
    assert.ok(exported.text.includes(model.property));
    assert.ok(exported.text.includes(hostile));
    await noPageOverflow();
  });

  await test("mobile layouts fit 390 px and 320 px, retaining readable diagram labels", async () => {
    await mount(await witness("voting_without_correct--Agreement"));
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await noPageOverflow();
      const map = await page.locator(".model-map").boundingBox();
      assert.ok(map && map.width > 200 && map.height > 100);
      await page.screenshot({ path: path.join(artifacts, `model-mobile-${width}.png`), fullPage: true });
    }
    await mount(await witness("spax_without_write_affine--Agreement"));
    await noPageOverflow();
    assert.ok((await visibleMapText()).includes("decide(blue)"));
    await page.screenshot({ path: path.join(artifacts, "model-paxos-mobile.png"), fullPage: true });
    await mount(synthetic({ points: ["a_" + "very_long_name_".repeat(25), "b", "c"] }));
    const memberSet = page.locator(".model-quorum-members");
    assert.ok((await memberSet.textContent()).includes("very_long_name_".repeat(25)), "Full HTML quorum set must remain available on mobile");
    const memberBox = await memberSet.boundingBox();
    assert.ok(memberBox && memberBox.width <= 320, "Long member names must wrap within the mobile layout");
    await noPageOverflow();
    await mount(await witness("voting_without_correct--Agreement"));
    await page.setViewportSize({ width: 1280, height: 1000 });
    await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
    await noPageOverflow();
    await page.screenshot({ path: path.join(artifacts, "model-text-200-percent.png"), fullPage: true });
    await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
  });

  await test("multiple witnesses have distinct control IDs and every control has an accessible name", async () => {
    const model = synthetic();
    await mount(model);
    await page.evaluate(model => window.appendModel(model), model);
    const result = await page.evaluate(() => {
      const nodes = [...document.querySelectorAll(".model-view [id]")];
      const ids = nodes.map(node => node.id);
      const unnamed = [...document.querySelectorAll(".model-view button, .model-view select, .model-view input")].filter(node => {
        return !(node.getAttribute("aria-label") || (node.tagName === "BUTTON" && node.textContent.trim())
          || [...(node.labels || [])].some(label => label.textContent.trim()));
      }).map(node => node.outerHTML);
      const images = [...document.querySelectorAll(".model-view img")].map(node => node.alt);
      return { duplicateIds: ids.filter((id, number) => ids.indexOf(id) !== number), unnamed, images };
    });
    assert.deepEqual(result.duplicateIds, []);
    assert.deepEqual(result.unnamed, []);
    assert.ok(result.images.every(description => description.length > 20));
    assert.deepEqual(errors, []);
  });
} catch (error) {
  failure = error;
  if (page) {
    await page.screenshot({ path: path.join(artifacts, "model-failure.png"), fullPage: true }).catch(() => {});
    await writeFile(path.join(artifacts, "model-failure.html"), await page.content()).catch(() => {});
  }
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
  await writeFile(path.join(artifacts, "model-view-results.json"), JSON.stringify({ checks, errors, failure: failure?.stack || null }, null, 2));
}
if (failure) { console.error(failure); process.exitCode = 1; }
else console.log(`${checks.length} diagram browser checks passed.`);
