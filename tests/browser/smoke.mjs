#!/usr/bin/env node
/**
 * Exercise the deployed browser application and its real Pyodide worker.
 *
 * Build with `python tools/build_site.py --output dist/muql-explorer`, serve
 * `dist` on port 8765, then run `node tests/browser/smoke.mjs`.
 * Install Playwright 1.62.1 and Chromium first. No mock worker or solver is used.
 * Set MUQL_WEB_URL for another URL, MUQL_BROWSER_ARTIFACTS for saved evidence,
 * or MUQL_BROWSER_NATIVE=1 to also exercise Pyodide's python-sat package.
 */

import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { performance } from 'node:perf_hooks';

const require = createRequire(import.meta.url);
let playwright;
try {
  playwright = require('playwright');
} catch (error) {
  if (!process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES) throw error;
  playwright = require(path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, 'playwright'));
}

const entryURL = process.env.MUQL_WEB_URL || 'http://127.0.0.1:8765/muql-explorer/';
let url = entryURL;
const artifacts = path.resolve(process.env.MUQL_BROWSER_ARTIFACTS || 'tests/browser/artifacts');
const timeout = 90_000;
const checks = [];
const consoleMessages = [];
const browserErrors = [];
const unexpectedDialogs = [];
let browser;
let activePage;
let failure = null;
await mkdir(artifacts, { recursive: true });

async function test(name, action) {
  const started = performance.now();
  process.stdout.write(`${name} … `);
  try {
    await action();
    checks.push({ name, status: 'passed', seconds: Number(((performance.now() - started) / 1000).toFixed(2)) });
    console.log('passed');
  } catch (error) {
    checks.push({ name, status: 'failed', error: error.stack || String(error) });
    console.log('FAILED');
    throw error;
  }
}

function observe(page) {
  activePage = page;
  page.setDefaultTimeout(timeout);
  page.on('pageerror', error => browserErrors.push(error.stack || String(error)));
  page.on('console', message => {
    if (['error', 'warning'].includes(message.type())) consoleMessages.push(`${message.type()}: ${message.text()}`);
  });
  page.on('requestfailed', request => consoleMessages.push(`request failed: ${request.url()} (${request.failure()?.errorText})`));
  page.on('dialog', dialog => {
    if (dialog.type() !== 'confirm') unexpectedDialogs.push(`${dialog.type()}: ${dialog.message()}`);
    return dialog.accept();
  });
}

async function ready(page) {
  await page.waitForFunction(() => {
    const run = document.querySelector('#run-button');
    return run && !run.disabled && document.querySelector('#theory-options')?.hidden === false &&
      document.querySelector('#error-box')?.hidden === true;
  }, null, { timeout });
}

async function loadExample(page, id) {
  const picker = page.locator('#example-select');
  if (!await picker.isVisible()) { await page.locator('#return-examples').click(); await ready(page); }
  if (await picker.inputValue() === id) await page.locator('#load-example').click();
  else await picker.selectOption(id);
  await ready(page);
  assert.ok((await page.locator('#theory-editor').inputValue()).includes('```muql'), `Missing theory for ${id}`);
}

async function run(page, expected, { keyboard = false } = {}) {
  await ready(page);
  if (keyboard) {
    await page.locator('#run-button').focus();
    assert.equal(await page.locator('#run-button').evaluate(node => node === document.activeElement), true);
    await page.keyboard.press('Enter');
  } else {
    await page.locator('#run-button').click();
  }
  await page.waitForFunction(text => {
    const runButton = document.querySelector('#run-button');
    const stopButton = document.querySelector('#stop-button');
    return runButton && !runButton.disabled && (stopButton?.disabled || stopButton?.hidden) &&
      document.querySelector('#results')?.textContent.includes(text);
  }, expected, { timeout });
  assert.equal(await page.locator('#error-box').isVisible(), false, 'Successful operation left an error visible');
}

async function openDetails(details) {
  if (!await details.evaluate(node => node.open)) await details.locator('summary').first().click();
}

async function sourceEditor(page) {
  await openDetails(page.locator('#source-details'));
  return page.locator('#theory-editor');
}

async function highlightedSource(page, { active = true } = {}) {
  await page.waitForFunction(expected =>
    document.querySelector('#source-editor')?.classList.contains('syntax-highlighted') === expected, active);
  const editor = page.locator('#theory-editor');
  const layer = page.locator('#source-highlight');
  assert.equal(await layer.getAttribute('aria-hidden'), 'true',
    'The native textarea should be the sole source exposed to assistive technology');
  if (active) {
    await page.waitForFunction(() => {
      const source = document.querySelector('#theory-editor').value;
      const highlighted = document.querySelector('#source-highlight-code').textContent;
      return highlighted === source + '\n';
    });
    assert.equal(await layer.evaluate(node => getComputedStyle(node).pointerEvents), 'none',
      'The decorative layer must not intercept selection or editing');
    assert.ok(await page.locator('#source-highlight-code span[class]').count(),
      'Markdown and 3μQL source should receive syntax tokens');
  } else {
    const nativeColor = await editor.evaluate(node => getComputedStyle(node).color);
    assert.notEqual(nativeColor, 'transparent', 'Plain editing must retain readable native text');
    assert.notEqual(nativeColor, 'rgba(0, 0, 0, 0)', 'Plain editing must retain readable native text');
  }
}

async function alignedHighlight(page) {
  await highlightedSource(page);
  await page.waitForFunction(() => {
    const editor = document.querySelector('#theory-editor');
    const layer = document.querySelector('#source-highlight');
    return Math.abs(layer.getBoundingClientRect().width - editor.clientWidth) <= 1 &&
      Math.abs(layer.getBoundingClientRect().height - editor.clientHeight) <= 1 &&
      Math.abs(layer.scrollTop - editor.scrollTop) <= 1 &&
      Math.abs(layer.scrollLeft - editor.scrollLeft) <= 1;
  });
  const metrics = await page.evaluate(() => {
    const editor = document.querySelector('#theory-editor');
    const layer = document.querySelector('#source-highlight');
    const code = document.querySelector('#source-highlight-code');
    const properties = ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight',
      'letterSpacing', 'tabSize', 'whiteSpace', 'overflowWrap'];
    const measure = node => Object.fromEntries(properties.map(name => [name, getComputedStyle(node)[name]]));
    const editorStyle = getComputedStyle(editor), layerStyle = getComputedStyle(layer);
    const er = editor.getBoundingClientRect(), lr = layer.getBoundingClientRect();
    return {
      editor: measure(editor), code: measure(code),
      editorPadding: [editorStyle.paddingTop, editorStyle.paddingRight, editorStyle.paddingBottom, editorStyle.paddingLeft],
      layerPadding: [layerStyle.paddingTop, layerStyle.paddingRight, layerStyle.paddingBottom, layerStyle.paddingLeft],
      left: lr.left - er.left - editor.clientLeft, top: lr.top - er.top - editor.clientTop,
      heightDifference: Math.abs(layer.scrollHeight - editor.scrollHeight),
      lineHeight: parseFloat(editorStyle.lineHeight),
      alteredTokens: [...code.querySelectorAll('span')].filter(node => {
        const style = getComputedStyle(node);
        return ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight', 'letterSpacing']
          .some(name => style[name] !== editorStyle[name]);
      }).length,
    };
  });
  assert.deepEqual(metrics.code, metrics.editor, 'Coloring must preserve the textarea’s exact text metrics and wrapping');
  assert.deepEqual(metrics.layerPadding, metrics.editorPadding, 'Both layers need identical text padding');
  assert.ok(Math.abs(metrics.left) <= 1 && Math.abs(metrics.top) <= 1,
    `Highlight origin must match the textarea content viewport: ${JSON.stringify(metrics)}`);
  assert.ok(metrics.heightDifference <= metrics.lineHeight + 1,
    'Wrapped lines should agree apart from a possible final caret line');
  assert.equal(metrics.alteredTokens, 0, 'Token colors must not introduce different glyph widths or line heights');
}

async function linearWorkflow(page) {
  const order = await page.locator('.workbench > section').evaluateAll(sections =>
    sections.map(section => ({ id: section.getAttribute('aria-labelledby'), top: section.getBoundingClientRect().top })));
  assert.deepEqual(order.map(section => section.id), ['example-heading', 'theory-heading', 'explore-heading', 'results-heading']);
  assert.ok(order.every((section, index) => index === 0 || section.top > order[index - 1].top),
    'Visual workflow must follow the document and keyboard order');
  assert.deepEqual(await page.locator('.step-index').allTextContents(), ['1', '2', '3', '4'],
    'Step headings and navigation should use the same unpadded numbering');
  assert.deepEqual(await page.locator('.workflow-nav a > span').allTextContents(), ['1', '2', '3', '4']);
  const numbers = await page.locator('.workbench > section').evaluateAll(sections => sections.map(section => {
    const heading = section.querySelector('.section-heading h2');
    const number = section.querySelector('.step-index');
    const headingStyle = getComputedStyle(heading), numberStyle = getComputedStyle(number);
    const properties = ['fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'lineHeight',
      'letterSpacing', 'fontVariantNumeric'];
    const measure = style => Object.fromEntries(properties.map(name => [name, style[name]]));
    const rect = node => {
      const { top, right, bottom, left } = node.getBoundingClientRect();
      return { top, right, bottom, left };
    };
    const text = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT, {
      acceptNode: node => node.textContent.trim() && !node.parentElement.closest('.step-index, .sr-only')
        ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
    }).nextNode();
    const headingRange = document.createRange(), numberRange = document.createRange();
    const firstLetter = text.textContent.search(/\S/);
    headingRange.setStart(text, firstLetter);
    headingRange.setEnd(text, firstLetter + 1);
    numberRange.selectNodeContents(number);
    return {
      index: number.textContent, contained: heading.contains(number),
      hidden: number.getAttribute('aria-hidden'), accessibleStep: heading.querySelector('.sr-only')?.textContent,
      headingStyle: measure(headingStyle), numberStyle: measure(numberStyle),
      heading: rect(heading), number: rect(number),
      headingGlyph: rect(headingRange), numberGlyph: rect(numberRange), viewport: window.innerWidth,
    };
  }));
  for (const item of numbers) {
    assert.equal(item.contained, true, `Step ${item.index} should be attached to its heading`);
    assert.equal(item.hidden, 'true', 'The visual number must not duplicate the accessible step label');
    assert.equal(item.accessibleStep?.trim(), `Step ${item.index}.`);
    assert.deepEqual(item.numberStyle, item.headingStyle,
      `Step ${item.index} must use its heading’s exact font, weight, and spacing`);
    assert.ok(Math.abs(item.number.top - item.heading.top) <= 1,
      `Step ${item.index} must sit beside the first heading line, including when the heading wraps`);
    assert.ok(Math.abs(item.numberGlyph.top - item.headingGlyph.top) <= 1 &&
      Math.abs(item.numberGlyph.bottom - item.headingGlyph.bottom) <= 1,
    `Step ${item.index} must share the heading’s first-line text alignment`);
    assert.ok(item.number.right < item.heading.left,
      `Step ${item.index} must remain outside the heading’s left margin`);
    assert.ok(item.number.left >= 0 && item.number.right <= item.viewport,
      `Step ${item.index} must remain fully visible at narrow widths`);
  }
}

async function symbolPalette(page) {
  const expected = ['¬', '∧', '∨', '⊕', '→', '⇀', '≡', '≤', '=', '≠', '∀', '∃', '∃¹', '∃⁰¹',
    '◇', '□', '∃ꟴ', '∀ꟴ', '∃ꟴ◇', '∀ꟴ□', '∃ꟴ□', '∀ꟴ◇', 'μ', 'ν'];
  const toolbar = page.getByRole('toolbar', { name: 'Insert a logic symbol' });
  const buttons = toolbar.locator('button');
  const coarsePointer = await page.evaluate(() => matchMedia('(any-pointer: coarse)').matches);
  const minimumTarget = coarsePointer ? 44 : 32;
  assert.deepEqual(await buttons.evaluateAll(nodes => nodes.map(node => node.dataset.symbol)), expected,
    'The palette should contain every canonical Unicode symbol exactly once');
  for (const button of await buttons.all()) {
    assert.equal(await button.isVisible(), true, 'Opening the editor must reveal every symbol without another disclosure');
    const box = await button.boundingBox();
    assert.ok(box && box.width >= minimumTarget && box.height >= minimumTarget,
      `Each symbol needs at least a ${minimumTarget}px target for this pointer`);
  }
  const toolbarBox = await toolbar.boundingBox();
  if (!coarsePointer && toolbarBox.width >= 900) {
    assert.ok(toolbarBox.height <= 80,
      'At desktop width all 24 symbols should fit within two compact rows');
  }
  assert.equal(await toolbar.locator('button[tabindex="0"]').count(), 1,
    'The symbol toolbar should require only one Tab stop');
  assert.equal(await toolbar.evaluate(node =>
    node.closest('.editor-frame') === document.querySelector('#theory-editor').closest('.editor-frame')), true,
    'Keep the palette attached to the Markdown editor frame');
}

async function typography(page, { guide = false } = {}) {
  const selectors = {
    body: 'body', title: 'h1', brand: '.brand', navigation: '.site-header nav',
    section: guide ? '.theory h2' : '.section-heading h2',
    control: guide ? '#search' : '#example-select',
    action: guide ? '.notation button' : '#run-button',
    formula: '.formula',
  };
  const styles = await page.evaluate(selectors => Object.fromEntries(Object.entries(selectors).map(([role, selector]) => {
    const node = document.querySelector(selector);
    const style = node && getComputedStyle(node);
    return [role, style ? { size: parseFloat(style.fontSize), family: style.fontFamily } : null];
  })), selectors);
  for (const [role, expected] of Object.entries({
    body: 16, brand: 18, navigation: 14, section: 24, control: 16, action: 16, formula: 18,
  })) {
    assert.equal(styles[role]?.size, expected,
      `${guide ? 'Theory reader' : 'Explorer'} ${role} text should keep its size at every viewport`);
  }
  assert.ok(styles.title?.size >= 32 && styles.title.size <= 40,
    'Page titles should stay within the shared 32–40px scale');
  const smallText = await page.evaluate(() => [...document.querySelectorAll(
    'p, label, summary, button, input, select, textarea, a, small, code, th, td, .formula-label, .scope-label',
  )].filter(node => node.getClientRects().length && !node.closest('.sr-only'))
    .filter(node => parseFloat(getComputedStyle(node).fontSize) < 14)
    .map(node => ({ text: node.textContent.trim().slice(0, 60), size: getComputedStyle(node).fontSize })));
  assert.deepEqual(smallText, [], 'Visible text, including supporting notes and inline code, must be at least 14px');
  if (!guide) {
    assert.equal(await page.locator('#theory-editor').evaluate(node => getComputedStyle(node).fontSize), '16px',
      'The Markdown editor should use the same readable body size on desktop and mobile');
  }
  return styles;
}

async function assumptions(page) {
  await openDetails(page.locator('#axiom-options').locator('xpath=ancestor::details[1]'));
}

async function download(page, locator, prefix) {
  const pending = page.waitForEvent('download');
  await locator.click();
  const item = await pending;
  assert.equal(await item.failure(), null);
  const filename = path.join(artifacts, `${prefix}-${path.basename(item.suggestedFilename())}`);
  await item.saveAs(filename);
  return readFile(filename, 'utf8');
}

async function report(page, prefix) {
  return JSON.parse(await download(page, page.locator('#download-report'), prefix));
}

function property(data, name, status) {
  const result = data.properties.find(item => item.name === name);
  assert.ok(result, `Report lacks property ${name}`);
  assert.equal(result.status, status, `${name} returned the wrong status`);
  return result;
}

async function noOverflow(page) {
  const sizes = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  assert.ok(sizes.content <= sizes.viewport + 1, `Page overflows: ${JSON.stringify(sizes)}`);
}

async function namedControls(page) {
  const unnamed = await page.evaluate(() => [...document.querySelectorAll('input, select, textarea, button')]
    .filter(node => node.type !== 'hidden' && !node.hidden)
    .filter(node => {
      const labelledBy = (node.getAttribute('aria-labelledby') || '').split(/\s+/)
        .map(id => document.getElementById(id)?.textContent || '').join(' ');
      const labels = [...(node.labels || [])].map(label => label.textContent).join(' ');
      return !(node.getAttribute('aria-label') || labelledBy || labels ||
        (node.tagName === 'BUTTON' ? node.textContent : '')).trim();
    }).map(node => node.id || node.outerHTML.slice(0, 100)));
  assert.deepEqual(unnamed, [], 'Every form control needs an accessible name');
  assert.equal(await page.locator('main').count(), 1, 'Use one main landmark');
  assert.equal(await page.locator('h1').count(), 1, 'Use one page heading');
}

try {
  browser = await playwright.chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage();
  observe(page);
  let replayTheory;

  await test('Load the real engine at a GitHub Pages project path', async () => {
    const response = await page.goto(url, { waitUntil: 'domcontentloaded' });
    assert.equal(response.status(), 200);
    await ready(page);
    // Branch-based Pages enters through the repository's root redirect. All
    // following asset and guide checks must use the final application URL.
    url = page.url();
    assert.equal(await page.locator('#example-select').inputValue(), 'choices');
    const titles = await page.locator('#example-select option').allTextContents();
    assert.match(titles[0], /^First steps/);
    assert.equal(titles.at(-1), 'Crusader agreement');
    assert.ok(titles.every(title => !title.includes('Custom experiment')));
    assert.equal(await page.locator('#custom-heading').innerText(), 'Custom experiment — create your own theory');
    assert.equal(await page.locator('#custom-experiment').evaluate(node => !!(document.querySelector('#evidence').compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING)), true);
    const configResponse = await page.request.get(new URL('config.json', url).href);
    assert.ok(configResponse.ok());
    const config = await configResponse.json();
    assert.match(await page.locator('#version').innerText(), new RegExp(config.version.replaceAll('.', '\\.')));
    await namedControls(page);
    await noOverflow(page);
    await linearWorkflow(page);
    await typography(page);
    assert.equal(await page.locator('#source-details').evaluate(node => node.open), false,
      'The first example should be usable without opening the source editor');
    assert.equal(await page.locator('#search-bounds').isVisible(), true);
    for (const id of ['max-points', 'max-values', 'max-stages']) {
      assert.equal(await page.locator('#' + id).isEnabled(), true, 'Search uses its size limits');
    }
    assert.ok((await page.locator('#loaded-theory').innerText()).trim(), 'Identify the loaded theory');
    await page.locator('#continue-theory').focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#theory-heading').evaluate(node => node === document.activeElement), true,
      'Continue should move keyboard focus to the next step');
  });

  await test('Choosing Simpler Paxos immediately replaces the tutorial and its assumptions', async () => {
    const picker = page.locator('#example-select');
    assert.equal(await picker.inputValue(), 'choices');
    await picker.focus();
    await picker.selectOption('paxos');
    await ready(page);
    assert.equal(await picker.evaluate(node => node === document.activeElement), true,
      'Immediate loading must preserve keyboard focus on the example picker');
    const source = await page.locator('#theory-editor').inputValue();
    assert.match(source, /theory "Simpler Declarative Paxos \(Figure 12\)"/);
    assert.doesNotMatch(source, /^predicate chosen\//m);
    assert.match(source, /^predicate decide\/1/m);
    assert.equal(await page.locator('#axiom-options input').count(), 12);
    assert.equal(await page.locator('#axiom-options input:checked').count(), 12);
    const quorumMark = page.locator('#axiom-options .quorum-quantifier').first();
    assert.match(await quorumMark.innerText(), /^[∃∀]ꟴ$/);
    assert.equal(await quorumMark.locator('sup').count(), 0, 'A native superscript should not be raised a second time');
    assert.match(source, /[∃∀]ꟴ/);
    assert.equal(await page.evaluate(async () => (await document.fonts.load('16px "MuQL Quorum"', 'ꟴ')).length), 1);
    assert.equal(await page.evaluate(() => document.fonts.check('16px "MuQL Quorum"', 'ꟴ')), true,
      'The bundled superscript glyph should render even without a matching system font');
    assert.equal(await page.locator('#symbol-buttons [data-symbol*="ꟴ"]').count(), 6);
    assert.equal(await page.locator('#loaded-theory').innerText(), 'Simpler Declarative Paxos (Figure 12)');
    for (const id of ['claims-theory', 'run-theory']) {
      assert.match(await page.locator('#' + id).innerText(), /Simpler Declarative Paxos/,
        'Claims and Run should identify the same loaded theory');
    }
    assert.match(await page.locator('#load-example').innerText(), /Reset example/);
    await loadExample(page, 'paxos-without-write');
    assert.equal(await page.locator('#assumptions-details').evaluate(node => node.open), true,
      'A preset that removes an axiom should expose its assumptions');
    assert.match(await page.locator('#run-omissions').innerText(), /SPaxWrite01/);
    assert.equal(await page.locator('#axiom-options input:checked').count(), 11);
    await loadExample(page, 'choices');
  });

  await test('Search for a counterexample and download independently replayed evidence', async () => {
    await run(page, 'Counterexample found');
    const data = await report(page, 'choices');
    assert.equal(data.schema, 'muql-search-report-v1');
    assert.equal(data.stats.solver, 'builtin');
    const result = property(data, 'AtMostOne', 'counterexample');
    assert.equal(result.countermodel.replayed, true);
    assert.equal(result.countermodel.scope.values.length, 2);
    assert.equal(result.countermodel.valuation.filter(cell => cell.value === 't').length, 2);
    const view = page.locator('#results .model-view').first();
    assert.equal(await view.isVisible(), true);
    await page.waitForFunction(() => document.querySelector('#results .model-map')?.naturalWidth > 0);
    const atoms = view.getByLabel('Atoms shown', { exact: true });
    assert.equal(await atoms.inputValue(), '', 'Start with both choices visible together');
    assert.equal(await atoms.locator('option').count(), 3);
    const visibleAtoms = await view.locator('.model-map').evaluate(image => {
      const svg = decodeURIComponent(image.src.slice(image.src.indexOf(',') + 1));
      const document = new DOMParser().parseFromString(svg, 'image/svg+xml');
      return [...document.querySelectorAll('[data-point-index] text')].map(node => node.textContent).join('\n');
    });
    for (const row of result.countermodel.valuation) {
      assert.ok(visibleAtoms.includes(`chosen(${row.args.join(', ')})`), 'Each chosen value must be named inside the participant card');
    }
    await atoms.selectOption({ index: 2 });
    assert.match(await view.locator('.model-map').getAttribute('alt'), /Selected atom: chosen/);
    const svg = await download(page, view.getByRole('button', { name: 'Download this view (SVG)', exact: true }), 'choices-diagram');
    assert.match(svg, /<svg\b/);
    assert.match(svg, /recorded property failure here/);
    const fullModel = page.locator('#results .model-exact').first();
    assert.equal(await fullModel.evaluate(node => node.open), false);
    const selectedAtom = await atoms.inputValue();
    await view.getByRole('button', { name: 'Full model data', exact: true }).focus();
    await page.keyboard.press('Enter');
    assert.equal(await fullModel.evaluate(node => node.open), true);
    assert.equal(await fullModel.locator('summary').evaluate(node => node === document.activeElement), true,
      'Opening the complete model should focus its data disclosure');
    assert.equal(await atoms.inputValue(), selectedAtom, 'Opening complete data must preserve the diagram selection');
    assert.equal(await page.locator('#results .valuation tbody tr').count(), result.countermodel.valuation.length);
    const witness = JSON.parse(await download(page,
      page.locator('#results').getByRole('button', { name: /countermodel.*json/i }).first(), 'choices-witness'));
    assert.equal(witness.schema, 'muql-countermodel-v1');
    assert.equal(witness.replayed, true);
    replayTheory = await download(page,
      page.locator('#results').getByRole('button', { name: /replay theory|counterexample theory/i }).first(), 'choices-replay');
    assert.match(replayTheory, /points /);
    assert.match(replayTheory, /property AtMostOne:/);
    await page.screenshot({ path: path.join(artifacts, 'desktop-counterexample.png'), fullPage: true });
  });

  await test('Changing a bound hides the preceding model until its previous run is opened', async () => {
    assert.equal(await page.locator('#results .model-view').first().isVisible(), true);
    await page.locator('#max-points').fill('2');
    const previous = page.locator('#results details.previous-results');
    assert.equal(await previous.count(), 1);
    assert.equal(await previous.evaluate(node => node.open), false);
    assert.equal(await previous.locator('.model-view').first().isVisible(), false,
      'A model from the previous bounds must not appear to be the current result');
    assert.equal(await previous.locator('#download-report').isVisible(), false);
    assert.equal(await page.locator('#results > .property-card').count(), 0);
    await openDetails(previous);
    assert.match(await previous.locator('.stale-note').innerText(), /previous run/i);
    assert.equal(await previous.locator('.model-view').first().isVisible(), true);
    assert.equal(await previous.locator('#download-report').isVisible(), true);
    await page.locator('#max-points').fill('1');
    assert.equal(await previous.evaluate(node => node.open), false,
      'Further setting changes should close the old evidence again');
  });

  await test('Check the downloaded counterexample scope again', async () => {
    await (await sourceEditor(page)).fill(replayTheory);
    await page.locator('#mode-check').check();
    await page.locator('#inspect-button').click();
    await ready(page);
    const bounds = ['max-points', 'max-values', 'max-stages', 'max-quorums', 'max-frames'];
    const retained = await Promise.all(bounds.map(id => page.locator('#' + id).inputValue()));
    assert.equal(await page.locator('#search-bounds').isVisible(), true, 'Keep inactive bounds visible to explain their role');
    for (const id of bounds) assert.equal(await page.locator('#' + id).isDisabled(), true);
    assert.equal(await page.locator('#timeout').isEnabled(), true, 'Time limits apply to both modes');
    assert.match(await page.locator('#scope-note').innerText(), /declared frame/i);
    const disabledBackground = await page.locator('#max-points').evaluate(node => getComputedStyle(node).backgroundColor);
    await page.locator('#mode-search').check();
    for (const id of bounds) assert.equal(await page.locator('#' + id).isEnabled(), true);
    const enabledBackground = await page.locator('#max-points').evaluate(node => getComputedStyle(node).backgroundColor);
    assert.notEqual(disabledBackground, enabledBackground, 'Inactive numeric fields must look inactive');
    assert.deepEqual(await Promise.all(bounds.map(id => page.locator('#' + id).inputValue())), retained);
    await page.locator('#mode-check').check();
    await run(page, 'Counterexample found');
    property(await report(page, 'replay'), 'AtMostOne', 'counterexample');
  });

  await test('Voting holds within the stated search bounds', async () => {
    await loadExample(page, 'voting');
    await run(page, 'Holds within bounds');
    const data = await report(page, 'voting');
    assert.equal(data.complete, true);
    property(data, 'Agreement', 'holds');
    assert.ok(data.stats.frames > 1, 'Voting should cover more than one frame');
    assert.match(await page.locator('#results .result-summary').innerText(), /not an unbounded proof/i);
  });

  await test('Removing the correct quorum produces a Voting counterexample', async () => {
    await loadExample(page, 'voting-without-correct');
    await assumptions(page);
    assert.equal(await page.locator('#axiom-options').getByRole('checkbox', { name: /^Correct\b/ }).isChecked(), false);
    await run(page, 'Counterexample found');
    property(await report(page, 'voting-without-correct'), 'Agreement', 'counterexample');
    const retained = await download(page, page.locator('#download-retained-theory'), 'without-correct-retained');
    assert.doesNotMatch(retained, /^axiom Correct:/m);
    assert.match(await page.locator('#theory-editor').inputValue(), /^axiom Correct:/m);

    await page.locator('#axiom-options').getByRole('checkbox', { name: /^Correct\b/ }).check();
    const previous = page.locator('#results details.previous-results');
    assert.equal(await previous.evaluate(node => node.open), false);
    assert.equal(await previous.locator('#download-retained-theory').isVisible(), false);
    await openDetails(previous);
    assert.match(await previous.locator('.stale-note').innerText(), /previous run/i);
    assert.equal(await download(page, page.locator('#download-retained-theory'), 'stale-retained'), retained,
      'Changing a checkbox must not silently change the preceding result’s downloads');
    property(await report(page, 'stale-report'), 'Agreement', 'counterexample');
    await run(page, 'Holds within bounds');
    property(await report(page, 'correct-restored'), 'Agreement', 'holds');
    assert.match(await download(page, page.locator('#download-retained-theory'), 'correct-restored-retained'), /^axiom Correct:/m);
  });

  await test('Simpler Paxos exposes the missing write uniqueness axiom', async () => {
    await loadExample(page, 'paxos-without-write');
    await assumptions(page);
    assert.equal(await page.locator('#axiom-options').getByRole('checkbox', { name: /^SPaxWrite01\b/ }).isChecked(), false);
    await run(page, 'Counterexample found');
    const result = property(await report(page, 'paxos-without-write'), 'Agreement', 'counterexample');
    assert.equal(result.countermodel.replayed, true);
  });

  await test('The three-valued tutorial checks its declared scope', async () => {
    await loadExample(page, 'basics');
    assert.equal(await page.locator('#mode-check').isChecked(), true);
    await run(page, 'Counterexample found');
    const data = await report(page, 'basics');
    property(data, 'BrokenIsDesignated', 'holds');
    property(data, 'BrokenIsTrue', 'counterexample');
    property(data, 'StrongCurrying', 'counterexample');
    assert.match(await page.locator('#results .result-summary').innerText(), /Each property has its own counterexample model/);
  });

  await test('A frame limit reports an incomplete search rather than a proof', async () => {
    await loadExample(page, 'voting');
    await openDetails(page.locator('.advanced'));
    await page.locator('#max-frames').fill('1');
    await run(page, 'Incomplete');
    const data = await report(page, 'frame-limit');
    assert.equal(data.complete, false);
    assert.equal(data.stats.frames, 1);
    property(data, 'Agreement', 'unknown');
    await page.locator('#max-frames').fill('500');
  });

  await test('Selecting no properties finds and displays an axiom model', async () => {
    await loadExample(page, 'choices');
    await page.locator('#properties-none').click();
    assert.match(await page.locator('#run-button').innerText(), /axiom model/i);
    await run(page, 'A model of the axioms');
    const data = await report(page, 'axiom-model');
    assert.deepEqual(data.properties, []);
    assert.ok(data.consistency_model.length > 0);
    const view = page.locator('#results .model-view');
    assert.equal(await view.isVisible(), true);
    assert.equal(await view.locator('.model-failure').count(), 0);
    assert.match(await view.locator('.model-context').innerText(), /satisfies all retained axioms/i);
    await view.getByRole('button', { name: 'Full model data', exact: true }).click();
    const fullModel = page.locator('#results .model-exact');
    assert.equal(await fullModel.evaluate(node => node.open), true);
    assert.equal(await fullModel.locator('.valuation tbody tr').count(), data.consistency_model.length);
  });

  await test('Theory names and Markdown containing HTML stay literal text', async () => {
    const title = '<img src=x onerror=alert(123)>';
    const source = `# <script>alert(124)</script>\n\n\`\`\`muql\ntheory "${title}"\npoints alice\nvalues red\nstages 1\ntime finite\nquorums {alice}\nproperty Literal: t\n\`\`\`\n`;
    await (await sourceEditor(page)).fill(source);
    await highlightedSource(page);
    assert.equal(await page.locator('#source-highlight img, #source-highlight script').count(), 0,
      'Highlighting must escape source text before inserting decorative markup');
    await page.locator('#mode-check').check();
    await page.locator('#inspect-button').click();
    await ready(page);
    await run(page, 'Holds in this frame');
    assert.ok((await page.locator('#results').innerText()).includes(title));
    assert.equal(await page.locator('#results img, #results script, #theory-options img, #theory-options script').count(), 0);
    property(await report(page, 'literal-html'), 'Literal', 'holds');
    assert.deepEqual(unexpectedDialogs, []);
  });

  await test('Syntax highlighting preserves native typing, undo, selections, and source downloads', async () => {
    await loadExample(page, 'choices');
    const editor = await sourceEditor(page);
    await highlightedSource(page);
    const original = await editor.inputValue();
    await editor.focus();
    await editor.evaluate(node => node.setSelectionRange(node.value.length, node.value.length));
    await page.keyboard.type('x');
    assert.equal(await editor.inputValue(), original + 'x');
    assert.equal(await page.locator('#curated-picker').isVisible(), false);
    await highlightedSource(page);
    await page.keyboard.press('ControlOrMeta+z');
    assert.equal(await editor.inputValue(), original, 'Color updates must preserve the native undo history');
    assert.equal(await page.locator('#example-select').inputValue(), 'choices', 'Native undo restores the example identity');
    assert.equal(await page.locator('#curated-picker').isVisible(), true);
    assert.equal(await page.locator('#custom-context').isVisible(), false);
    assert.equal(await page.locator('#theory-options').isVisible(), true, 'Previously read curated declarations are immediately reusable');
    assert.equal(await page.locator('#run-button').getAttribute('type'), 'submit');
    await highlightedSource(page);
    await page.keyboard.press('ControlOrMeta+Shift+z');
    assert.equal(await editor.inputValue(), original + 'x');
    assert.equal(await page.locator('#curated-picker').isVisible(), false, 'Redo re-enters edited-source mode');
    await highlightedSource(page);

    await editor.evaluate(node => { node.setSelectionRange(2, 12); node.scrollTop = 50; });
    const snapshot = () => editor.evaluate(node => ({
      source: node.value, start: node.selectionStart, end: node.selectionEnd, scrollTop: node.scrollTop,
    }));
    const before = await snapshot();
    await page.getByRole('checkbox', { name: 'Highlight syntax', exact: true }).uncheck();
    await highlightedSource(page, { active: false });
    assert.deepEqual(await snapshot(), before, 'Switching colors off must not alter the source or selection');
    await page.getByRole('checkbox', { name: 'Highlight syntax', exact: true }).check();
    await highlightedSource(page);
    assert.deepEqual(await snapshot(), before, 'Switching colors on must not alter the source or selection');
    assert.equal(await download(page, page.locator('#save-source'), 'highlight-source'), original + 'x',
      'Downloads must contain the exact Markdown source, without decoration or sentinel');
    await alignedHighlight(page);
    await page.locator('.editor-frame').screenshot({ path: path.join(artifacts, 'desktop-source-highlighting.png') });
  });

  await test('Imported and restored source is highlighted, with readable composition and high-contrast fallbacks', async () => {
    await loadExample(page, 'choices');
    const source = `${await page.locator('#theory-editor').inputValue()}\nImported draft with **Markdown** and \`inline code\`.\n`;
    await page.locator('#import-file').setInputFiles({ name: 'highlight-import.md', mimeType: 'text/markdown', buffer: Buffer.from(source) });
    await ready(page);
    let editor = await sourceEditor(page);
    assert.equal(await editor.inputValue(), source);
    assert.equal(await page.locator('#example-select').inputValue(), '',
      'An opened file must not retain the preceding preset identity');
    assert.doesNotMatch(await page.locator('#example-description').innerText(), /Does a two-valued choice have to be unique/);
    await highlightedSource(page);
    await page.waitForFunction(source => {
      const draft = JSON.parse(localStorage.getItem(`muql-explorer-draft-v1:${new URL('.', location.href).pathname}`));
      return draft?.source === source;
    }, source);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await ready(page);
    assert.equal(await page.locator('#example-select').inputValue(), 'choices', 'Each visit starts at First steps');
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem(`muql-explorer-draft-v1:${new URL('.', location.href).pathname}`)).source), source,
      'Starting the curated tour must preserve the saved custom draft');
    await page.locator('#restore-draft').click();
    await ready(page);
    editor = await sourceEditor(page);
    assert.equal(await editor.inputValue(), source, 'Explicitly restoring a draft must retain its exact source');
    assert.equal(await page.locator('#example-select').inputValue(), '',
      'A restored draft must not masquerade as an unmodified bundled preset');
    await highlightedSource(page);

    await editor.dispatchEvent('compositionstart', { data: '' });
    await highlightedSource(page, { active: false });
    await editor.evaluate(node => {
      node.value += '日本語';
      node.dispatchEvent(new InputEvent('input', { bubbles: true, data: '日本語', inputType: 'insertCompositionText', isComposing: true }));
    });
    await highlightedSource(page, { active: false });
    await editor.dispatchEvent('compositionend', { data: '日本語' });
    assert.equal(await editor.inputValue(), source + '日本語', 'Composition must retain the text supplied by the input method');
    await highlightedSource(page);

    await page.emulateMedia({ forcedColors: 'active' });
    await highlightedSource(page, { active: false });
    assert.equal(await page.locator('#highlight-syntax').isChecked(), true,
      'A temporary accessibility fallback must retain the user’s color preference');
    await page.emulateMedia({ forcedColors: 'none' });
    await highlightedSource(page);
    assert.equal(await editor.inputValue(), source + '日本語');
  });

  await test('Highlighted text follows long wrapped lines, scrolling, and editor resizing', async () => {
    await loadExample(page, 'choices');
    const editor = await sourceEditor(page);
    const original = await editor.inputValue();
    const paragraph = 'Unicode ∃¹ ∃⁰¹ ∃ꟴ◇ ∀ꟴ□ ⇀ and ASCII unique affine -\\ remain editable. ';
    const source = `${original}\n${Array.from({ length: 30 }, (_, i) => `Line ${i + 1}:\t${paragraph.repeat(5)}`).join('\n')}\n`;
    await editor.fill(source);
    await alignedHighlight(page);
    for (const fraction of [0.5, 1, 0]) {
      await editor.evaluate((node, fraction) => { node.scrollTop = (node.scrollHeight - node.clientHeight) * fraction; }, fraction);
      await alignedHighlight(page);
    }
    await editor.evaluate(node => { node.style.height = '510px'; });
    await alignedHighlight(page);
    await page.setViewportSize({ width: 800, height: 1000 });
    await alignedHighlight(page);
    await noOverflow(page);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await editor.evaluate(node => { node.style.height = ''; });
    await alignedHighlight(page);
  });

  await test('Stale run and continuation actions guide the reader to Update choices before running', async () => {
    await loadExample(page, 'choices');
    await page.locator('#properties-none').click();
    const source = await page.locator('#theory-editor').inputValue();
    await (await sourceEditor(page)).fill(source + '\n<!-- Edited locally -->\n');
    assert.equal(await page.locator('#example-select').inputValue(), '',
      'Editing the source must immediately detach its preset identity');
    assert.doesNotMatch(await page.locator('#example-description').innerText(), /Does a two-valued choice have to be unique/);
    assert.equal(await page.locator('#run-button').isDisabled(), false,
      'Stale choices need an actionable route back to the refresh button');
    assert.match(await page.locator('#run-button').innerText(), /^Update choices before finding an axiom model/);
    assert.equal(await page.locator('#run-button').getAttribute('type'), 'button');
    assert.match(await page.locator('#continue-settings').innerText(), /^Update choices/);
    assert.doesNotMatch(await page.locator('#status-text').innerText(), /^Ready\./);
    assert.equal(await page.locator('#theory-options').isVisible(), false);
    assert.equal(await page.locator('#refresh-choices').isVisible(), true);
    await page.locator('#max-points').fill('-1');
    await page.locator('#max-points').press('Enter');
    assert.equal(await page.locator('#theory-options').isVisible(), false, 'Enter must not run or silently reread an edited theory');
    assert.notEqual(await page.locator('#result-label').innerText(), 'Running');
    for (const action of ['run-button', 'continue-settings']) {
      await page.locator('#' + action).click();
      assert.equal(await page.locator('#refresh-choices').evaluate(node => node === document.activeElement), true,
        `${action} must direct keyboard focus to the exact action required`);
      await page.waitForFunction(() => {
        const rect = document.querySelector('#refresh-choices').getBoundingClientRect();
        return rect.top >= 0 && rect.bottom <= window.innerHeight;
      });
      assert.equal(await page.locator('#theory-options').isVisible(), false, 'Navigation alone does not inspect or run source');
    }
    await page.locator('#max-points').fill('1');
    await page.locator('#refresh-choices').click();
    await ready(page);
    assert.equal(await page.locator('#property-options').isVisible(), true,
      'A successful reread should expose the current selections before running');
    assert.equal(await page.locator('#run-button').isDisabled(), false);
    assert.equal(await page.locator('#example-select').inputValue(), '',
      'Reading an edited theory must preserve its custom identity');
    assert.match(await page.locator('#continue-settings').innerText(), /^Continue to run/);
    assert.equal(await page.locator('#run-button').getAttribute('type'), 'submit');
  });

  await test('Custom Save and Reset preserve work and return to the exact last curated preset', async () => {
    await loadExample(page, 'paxos-without-write');
    const editor = await sourceEditor(page);
    const original = await editor.inputValue();
    const edited = original + '\n<!-- My custom experiment -->\n';
    await editor.fill(edited);
    assert.equal(await page.locator('#custom-save-source').isVisible(), true);
    assert.equal(await download(page, page.locator('#custom-save-source'), 'custom-section-source'), edited);
    await page.locator('#reset-custom').click();
    await ready(page);
    assert.equal(await page.locator('#example-select').inputValue(), 'paxos-without-write');
    assert.equal(await page.locator('#theory-editor').inputValue(), original);
    assert.match(await page.locator('#run-omissions').innerText(), /SPaxWrite01/);
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem(`muql-explorer-draft-v1:${new URL('.', location.href).pathname}`)).source), edited,
      'Reset flushes custom work before opening the curated example');
    assert.equal(await page.locator('#restore-draft').isVisible(), true);
    await (await sourceEditor(page)).fill(original + '\n<!-- Another temporary edit -->\n');
    await page.locator('#refresh-choices').click(); await ready(page);
    await (await sourceEditor(page)).fill(original);
    assert.equal(await page.locator('#example-select').inputValue(), 'paxos-without-write',
      'Undoing a successfully read edit must recover this preset rather than its other shared-source preset');
    assert.match(await page.locator('#run-omissions').innerText(), /SPaxWrite01/);
    assert.equal(await page.locator('#theory-options').isVisible(), true);
  });

  await test('The complete symbol toolbar preserves selections and supports keyboard navigation', async () => {
    await loadExample(page, 'choices');
    const editor = await sourceEditor(page);
    await symbolPalette(page);
    await typography(page);
    await noOverflow(page);
    await page.locator('.editor-frame').screenshot({ path: path.join(artifacts, 'desktop-symbol-toolbar.png') });
    const source = `${await editor.inputValue()}\n<!-- Toolbar: replace-me ; insert-here -->\n`;
    await editor.fill(source);
    await page.locator('#inspect-button').click();
    await ready(page);

    const replaceStart = source.indexOf('replace-me');
    await editor.focus();
    await editor.evaluate((node, start) => node.setSelectionRange(start, start + 'replace-me'.length), replaceStart);
    const unique = page.getByRole('button', { name: 'Insert unique existence, ∃¹', exact: true });
    await unique.click();
    const afterUnique = source.slice(0, replaceStart) + '∃¹' + source.slice(replaceStart + 'replace-me'.length);
    assert.equal(await editor.inputValue(), afterUnique, 'Pointer insertion should replace only the selected text');
    await highlightedSource(page);
    assert.deepEqual(await editor.evaluate(node => ({
      focused: node === document.activeElement, start: node.selectionStart, end: node.selectionEnd,
    })), { focused: true, start: replaceStart + '∃¹'.length, end: replaceStart + '∃¹'.length });
    assert.equal(await page.locator('#run-button').isDisabled(), false,
      'Symbol insertion must offer the same update action as typing');
    assert.match(await page.locator('#run-button').innerText(), /^Update choices before/);

    const focusedSymbol = () => page.evaluate(() => document.activeElement?.dataset.symbol);
    await page.keyboard.press('Shift+Tab');
    assert.equal(await focusedSymbol(), '∃¹', 'Shift+Tab should return to the most recently used symbol');
    await page.keyboard.press('Home');
    assert.equal(await focusedSymbol(), '¬');
    await page.keyboard.press('ArrowLeft');
    assert.equal(await focusedSymbol(), 'ν', 'Left should wrap from the first symbol to the last');
    await page.keyboard.press('ArrowRight');
    assert.equal(await focusedSymbol(), '¬', 'Right should wrap from the last symbol to the first');
    await page.keyboard.press('End');
    assert.equal(await focusedSymbol(), 'ν');
    await page.keyboard.press('ArrowLeft');
    assert.equal(await focusedSymbol(), 'μ');
    await page.keyboard.press('Tab');
    assert.equal(await editor.evaluate(node => node === document.activeElement), true,
      'Tab should leave the toolbar and enter the source editor');

    const insertStart = afterUnique.indexOf('insert-here');
    await editor.evaluate((node, start) => node.setSelectionRange(start, start), insertStart);
    const affine = page.getByRole('button', { name: 'Insert affine existence, ∃⁰¹', exact: true });
    await affine.focus();
    await page.keyboard.press('Enter');
    const afterAffine = afterUnique.slice(0, insertStart) + '∃⁰¹' + afterUnique.slice(insertStart);
    assert.equal(await editor.inputValue(), afterAffine, 'Keyboard insertion should retain the editor cursor');
    await highlightedSource(page);
    assert.deepEqual(await editor.evaluate(node => ({
      focused: node === document.activeElement, start: node.selectionStart, end: node.selectionEnd,
    })), { focused: true, start: insertStart + '∃⁰¹'.length, end: insertStart + '∃⁰¹'.length });
    await page.keyboard.press('Shift+Tab');
    assert.equal(await focusedSymbol(), '∃⁰¹');
    await page.keyboard.press('Space');
    assert.equal(await editor.inputValue(), afterUnique.slice(0, insertStart) + '∃⁰¹∃⁰¹' + afterUnique.slice(insertStart),
      'Space should activate a symbol button as well as Enter');
    await highlightedSource(page);
    assert.equal(await editor.evaluate(node => node === document.activeElement), true);
    await symbolPalette(page);
    await namedControls(page);
    await page.locator('#inspect-button').click();
    await ready(page);
    assert.equal(await page.locator('#run-button').isDisabled(), false);
  });

  await test('Malformed formulas give an accessible error at the exact Unicode source position', async () => {
    for (const separator of ['\n', '\u2028']) {
      const source = ['```muql', 'theory "Bad input"', 'values "😀"', 'predicate P/1',
        'property Invalid: P("😀") => P("😀")', '```', ''].join(separator);
      const editor = await sourceEditor(page);
      await editor.fill(source);
      await page.locator('#source-details > summary').click();
      assert.equal(await page.locator('#source-details').evaluate(node => node.open), false);
      await page.locator('#continue-theory').click();
      await page.locator('#error-box').waitFor({ state: 'visible' });
      assert.equal(await page.locator('#source-details').evaluate(node => node.open), true,
        'A source error should open the editor for correction');
      assert.match(await page.locator('#error-box').innerText(), /line|column|=>|formula|unexpected|implication|token/i);
      assert.equal(await editor.inputValue(), source);
      assert.equal(await page.locator('#error-box').getAttribute('role'), 'alert');
      await page.locator('#error-box').getByRole('button', { name: /^Go to line / }).click();
      assert.equal(await editor.evaluate(node => node === document.activeElement), true);
      assert.deepEqual(await editor.evaluate(node => [node.selectionStart, node.selectionEnd]),
        [source.indexOf('=>'), source.indexOf('=>') + 1], 'Error navigation must count Unicode code points and loader line endings');
      await alignedHighlight(page);
    }
    await loadExample(page, 'choices');
    assert.equal(await page.locator('#error-box').isVisible(), false);
  });

  await test('A startup download failure never overwrites a saved draft on close', async () => {
    const failureContext = await browser.newContext();
    const saved = '# My unpublished theory\n\n```muql\nproperty P: t\n```\n';
    await failureContext.addInitScript(source => {
      localStorage.setItem('muql-explorer-draft-v1', JSON.stringify({ source, highlight: false }));
    }, saved);
    const failedPage = await failureContext.newPage();
    observe(failedPage);
    await failedPage.route('**/config.json', route => route.fulfill({ status: 503, body: 'Unavailable' }));
    await failedPage.goto(url, { waitUntil: 'domcontentloaded' });
    await failedPage.locator('#boot-error').waitFor({ state: 'visible' });
    await failedPage.evaluate(() => window.dispatchEvent(new Event('beforeunload')));
    assert.equal(await failedPage.evaluate(() => JSON.parse(localStorage.getItem('muql-explorer-draft-v1')).source), saved);
    await failureContext.close();
    activePage = page;
  });

  await test('Stop cancels work and a fresh worker can run again', async () => {
    await loadExample(page, 'paxos');
    await page.locator('#max-points').fill('6');
    await page.locator('#max-values').fill('4');
    await page.locator('#max-stages').fill('6');
    await page.locator('#timeout').fill('30');
    await page.locator('#run-button').click();
    await page.locator('#stop-button').click();
    await page.waitForFunction(() => document.querySelector('#results')?.textContent.includes('Stopped'));
    assert.equal(await page.locator('#stop-button').evaluate(node => node.disabled || node.hidden), true);
    await loadExample(page, 'choices');
    await run(page, 'Counterexample found');
    property(await report(page, 'after-stop'), 'AtMostOne', 'counterexample');
  });

  await test('The primary workflow is usable with a keyboard', async () => {
    await loadExample(page, 'choices');
    await assumptions(page);
    await page.locator('#axiom-options').getByRole('checkbox', { name: /^Correct\b/ }).focus();
    await page.keyboard.press('Space');
    assert.equal(await page.locator('#axiom-options').getByRole('checkbox', { name: /^Correct\b/ }).isChecked(), false);
    await page.keyboard.press('Space');
    await run(page, 'Counterexample found', { keyboard: true });
    await namedControls(page);
  });

  await test('The theory guide shares the Explorer style and keeps navigation, search, and notation working', async () => {
    const guide = await context.newPage();
    observe(guide);
    const response = await guide.goto(new URL('theories.html', url).href, { waitUntil: 'domcontentloaded' });
    assert.equal(response.status(), 200);
    await namedControls(guide);
    await noOverflow(guide);
    assert.equal(await page.title(), '3μQL Explorer');
    assert.equal(await guide.title(), 'Theory guide · 3μQL Explorer');
    assert.equal(await page.locator('.brand-mark').innerText(), '3μ');
    assert.equal(await guide.locator('.brand-mark').innerText(), '3μ');
    assert.equal(await guide.locator('.brand-mark').evaluate(node => getComputedStyle(node).backgroundColor),
      await page.locator('.brand-mark').evaluate(node => getComputedStyle(node).backgroundColor),
      'The companion guide should retain the Explorer’s blue 3μ logo');
    assert.equal(await guide.locator('body').evaluate(node => getComputedStyle(node).backgroundColor),
      await page.locator('body').evaluate(node => getComputedStyle(node).backgroundColor));
    assert.deepEqual(await typography(guide, { guide: true }), await typography(page),
      'The Explorer and theory reader should share the same type scale and font families');

    await guide.locator('[data-theory="paxos_simpler"]').focus();
    await guide.keyboard.press('Enter');
    assert.equal(await guide.locator('#paxos_simpler').isVisible(), true);
    assert.equal(await guide.locator('#main').evaluate(node => node === document.activeElement), true);
    assert.equal(new URL(guide.url()).hash, '#paxos_simpler');
    await guide.locator('#search').fill('SPaxWrite01');
    assert.equal(await guide.locator('.theory-link:visible').count(), 1);
    assert.equal(await guide.locator('.theory-link:visible').getAttribute('data-theory'), 'paxos_simpler');
    await guide.locator('#search').fill('no-such-theory-9b84');
    assert.equal(await guide.locator('#no-results').isVisible(), true);
    assert.equal(await guide.locator('.theory:visible').count(), 0);
    await guide.locator('#search').fill('');
    assert.equal(await guide.locator('#no-results').isVisible(), false);
    assert.equal(await guide.locator('#paxos_simpler').isVisible(), true);

    const unicode = await guide.locator('#paxos_simpler .formula').allTextContents();
    const quorumMarks = await guide.locator('#paxos_simpler .formula .quorum-quantifier').count();
    assert.ok(quorumMarks > 0, 'The reader should include native superscript quorum markers');
    assert.ok((await guide.locator('#paxos_simpler .formula .quorum-quantifier').allTextContents())
      .every(text => /^[∃∀]ꟴ$/.test(text)), 'Copied Unicode formulas should retain the actual superscript Q');
    assert.equal(await guide.locator('#paxos_simpler .formula sup.quorum-mark').count(), 0,
      'The native superscript should not be raised a second time');
    await guide.getByRole('button', { name: 'ASCII', exact: true }).click();
    const ascii = (await guide.locator('#paxos_simpler .formula').allTextContents()).join('\n');
    assert.match(ascii, /affine/);
    assert.ok(ascii.includes('-\\'), 'ASCII strong implication must retain the paper’s spelling');
    assert.doesNotMatch(ascii, /[∀∃⇀]/);
    assert.equal(await guide.locator('#paxos_simpler .formula .quorum-quantifier').count(), 0);
    assert.deepEqual(await guide.locator('#paxos_simpler .formula').evaluateAll(nodes =>
      [...new Set(nodes.map(node => getComputedStyle(node).fontSize))]), ['16px'],
      'ASCII formulas, including named definitions, should keep the readable body size');
    assert.equal(await guide.getByRole('button', { name: 'ASCII', exact: true }).getAttribute('aria-pressed'), 'true');
    await guide.getByRole('button', { name: 'Unicode', exact: true }).click();
    assert.deepEqual(await guide.locator('#paxos_simpler .formula').allTextContents(), unicode);
    assert.equal(await guide.locator('#paxos_simpler .formula .quorum-quantifier').count(), quorumMarks);
    await guide.screenshot({ path: path.join(artifacts, 'desktop-theory-guide.png'), fullPage: true });
    for (const width of [390, 320]) {
      await guide.setViewportSize({ width, height: 844 });
      await noOverflow(guide);
      await typography(guide, { guide: true });
    }
    await guide.screenshot({ path: path.join(artifacts, 'narrow-theory-guide.png'), fullPage: true });
    await guide.close();
    activePage = page;
  });

  if (process.env.MUQL_BROWSER_NATIVE === '1') {
    await test('The optional PySAT solver runs a real browser search', async () => {
      await loadExample(page, 'choices');
      await openDetails(page.locator('.advanced'));
      await page.locator('#solver').selectOption('pysat');
      await run(page, 'Counterexample found');
      const data = await report(page, 'pysat');
      assert.equal(data.stats.solver, 'pysat');
      property(data, 'AtMostOne', 'counterexample');
      await page.locator('#solver').selectOption('builtin');
    });
  }

  await test('The mobile interface loads, runs, and fits narrow viewports', async () => {
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true,
      deviceScaleFactor: 1, acceptDownloads: true,
    });
    const mobile = await mobileContext.newPage();
    observe(mobile);
    await mobile.goto(url, { waitUntil: 'domcontentloaded' });
    await ready(mobile);
    await namedControls(mobile);
    await noOverflow(mobile);
    await linearWorkflow(mobile);
    await typography(mobile);
    await run(mobile, 'Counterexample found');
    await noOverflow(mobile);
    await mobile.screenshot({ path: path.join(artifacts, 'mobile-counterexample.png'), fullPage: true });
    const mobileEditor = await sourceEditor(mobile);
    await symbolPalette(mobile);
    await typography(mobile);
    await noOverflow(mobile);
    await alignedHighlight(mobile);
    const mobileSource = await mobileEditor.inputValue();
    await mobileEditor.fill(`${mobileSource}\n${('Long mobile text ∃¹ ∃⁰¹ ⇀ with a tab:\tand more source. '.repeat(5) + '\n').repeat(12)}`);
    await mobileEditor.evaluate(node => { node.scrollTop = node.scrollHeight; });
    await alignedHighlight(mobile);
    await mobile.setViewportSize({ width: 320, height: 740 });
    await linearWorkflow(mobile);
    await symbolPalette(mobile);
    await typography(mobile);
    await noOverflow(mobile);
    await alignedHighlight(mobile);
    await mobile.screenshot({ path: path.join(artifacts, 'narrow-counterexample.png'), fullPage: true });
    await loadExample(mobile, 'paxos');
    await mobile.locator('#max-points').fill('6');
    await mobile.locator('#max-values').fill('4');
    await mobile.locator('#max-stages').fill('6');
    await mobile.locator('#timeout').fill('30');
    await mobile.locator('#run-button').click();
    await mobile.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    const stop = await mobile.locator('#floating-stop').boundingBox();
    assert.ok(stop && stop.x >= 0 && stop.y >= 0 && stop.x + stop.width <= 321 && stop.y + stop.height <= 741,
      'The mobile Stop button must stay in the viewport while scrolling');
    await mobile.screenshot({ path: path.join(artifacts, 'mobile-stop-control.png') });
    await mobile.locator('#floating-stop').click();
    await mobile.waitForFunction(() => document.querySelector('#results')?.textContent.includes('Stopped'));
    await mobileContext.close();
    activePage = page;
  });

  assert.deepEqual(browserErrors, [], 'Unexpected browser JavaScript errors');
  assert.deepEqual(unexpectedDialogs, [], 'Unexpected browser dialogs');
  console.log(`\n${checks.length} real-browser checks passed.`);
} catch (error) {
  process.exitCode = 1;
  failure = error.stack || String(error);
  console.error(error.stack || error);
  if (activePage && !activePage.isClosed()) {
    await activePage.screenshot({ path: path.join(artifacts, 'failure.png'), fullPage: true }).catch(() => {});
    await writeFile(path.join(artifacts, 'failure.html'), await activePage.content().catch(() => ''), 'utf8');
  }
} finally {
  await writeFile(path.join(artifacts, 'summary.json'), JSON.stringify({
    entryURL, url, success: failure === null, failure, checks, browserErrors, unexpectedDialogs, consoleMessages,
    nativeRequested: process.env.MUQL_BROWSER_NATIVE === '1',
  }, null, 2) + '\n');
  if (browser) await browser.close();
}
