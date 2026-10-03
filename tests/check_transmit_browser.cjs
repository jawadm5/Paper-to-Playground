/* Bounded offline checks for the compact context rail and stable concept canvas.
 * Usage: node tests/check_transmit_browser.cjs [lesson.html] [screenshots-dir]
 */
const {chromium} = require('playwright');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');

const file = path.resolve(process.argv[2] || 'out/attention-current/index.html');
const screenshotDir = process.argv[3] ? path.resolve(process.argv[3]) : null;
const widths = [1360, 1024, 736, 390, 320];
const failures = [], network = [], railChecks = [], selectionChecks = [];
const watchdog = setTimeout(() => { console.error('Transmit browser checks exceeded 90 seconds'); process.exit(1); }, 90000);
watchdog.unref();

const settle = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
const nodes = page => page.locator('.concept-world [data-concept]').evaluateAll(items =>
  items.map(node => ({id: node.dataset.concept, transform: node.getAttribute('transform')})));
const viewport = page => page.locator('.concept-world').evaluate(node => {
  const m = new DOMMatrix(getComputedStyle(node).transform);
  return [m.a, m.b, m.c, m.d, m.e, m.f].map(n => Math.round(n * 1e6) / 1e6);
});
const closeMatrix = (actual, expected, label) => actual.forEach((value, i) =>
  assert.ok(Math.abs(value - expected[i]) < .001, label + ': transform coordinate ' + i + ' changed'));

async function open(context) {
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  page.on('pageerror', error => failures.push(error.message));
  page.on('console', message => { if (message.type() === 'error') failures.push(message.text()); });
  page.on('request', request => { if (/^https?:/i.test(request.url())) network.push(request.url()); });
  await page.goto(pathToFileURL(file).href, {timeout: 12000});
  await page.waitForFunction(() => document.documentElement.dataset.researchLabReady === 'true');
  return page;
}

async function assertSelection(page, concept, handoff, baselineNodes, baselineViewport, label) {
  await settle(page);
  assert.deepEqual(await nodes(page), baselineNodes, label + ': selection changed the full graph or node positions');
  closeMatrix(await viewport(page), baselineViewport, label + ': selection moved the viewport');
  assert.equal(await page.locator('#concept-detail h2').textContent(), concept.name, label + ': wrong inspector');
  assert.deepEqual(await page.locator('.concept-world [data-concept][aria-pressed="true"]').evaluateAll(items =>
    items.map(item => item.dataset.concept)), [concept.id], label + ': selection state');
  const edges = await page.locator('.concept-world [data-edge]').evaluateAll(items => items.map(item => ({
    index: Number(item.dataset.edge), stroke: item.getAttribute('stroke'), width: Number(item.getAttribute('stroke-width'))
  })));
  assert.equal(edges.length, handoff.content.relationships.length, label + ': relationships disappeared');
  assert.deepEqual(edges.map(edge => edge.index).sort((a, b) => a - b),
    handoff.content.relationships.map((_, index) => index), label + ': relationship indices changed or duplicated');
  for (const edge of edges) {
    const relationship = handoff.content.relationships[edge.index];
    assert.ok(relationship, label + ': unknown relationship index');
    const incident = relationship.from === concept.id || relationship.to === concept.id;
    assert.equal(edge.stroke, incident ? 'var(--accent)' : 'var(--baseline)', label + ': incorrect incident-edge highlight');
    assert.ok(incident ? edge.width >= 2 : edge.width < 2, label + ': edge emphasis');
  }
  const incidentCount = handoff.content.relationships.filter(edge => edge.from === concept.id || edge.to === concept.id).length;
  assert.equal(await page.locator('#concept-detail .map-edge').count(), incidentCount, label + ': inspector relationships');
}

async function checkSelection(page, handoff, width) {
  await page.setViewportSize({width, height: 950});
  await page.locator('[data-mode=map]').click();
  await settle(page);
  await page.getByRole('button', {name: 'Fit map', exact: true}).click();
  await settle(page);
  const baselineNodes = await nodes(page);
  assert.deepEqual(baselineNodes.map(node => node.id).sort(), handoff.content.concepts.map(node => node.id).sort());
  assert.equal(await page.locator('.concept-world').isVisible(), true, width + ': real graph replaced by cards');
  assert.equal(await page.locator('.concept-symbol').count(), 0, width + ': map reintroduced unwanted node icons');
  const geometry = await page.locator('.concept-canvas').evaluate(canvas => {
    const bounds = canvas.getBoundingClientRect();
    const boxes = [...canvas.querySelectorAll('[data-concept]')].map(node => {
      const rect = node.querySelector('rect').getBoundingClientRect();
      return {id: node.dataset.concept, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom};
    });
    return {bounds: {left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom}, boxes};
  });
  for (let i = 0; i < geometry.boxes.length; i++) {
    const box = geometry.boxes[i], bounds = geometry.bounds;
    assert.ok(box.left >= bounds.left - 1 && box.right <= bounds.right + 1 &&
      box.top >= bounds.top - 1 && box.bottom <= bounds.bottom + 1,
      width + ': Fit clips node ' + box.id);
    for (const other of geometry.boxes.slice(i + 1)) {
      const overlapX = Math.min(box.right, other.right) - Math.max(box.left, other.left);
      const overlapY = Math.min(box.bottom, other.bottom) - Math.max(box.top, other.top);
      assert.ok(overlapX <= .1 || overlapY <= .1, width + ': overlapping nodes ' + box.id + ' and ' + other.id);
    }
  }
  const fitted = await viewport(page);
  for (const concept of handoff.content.concepts) {
    // Exercise actual node activation, not just the selector's change handler.
    const node = page.locator('.concept-world [data-concept="' + concept.id + '"]');
    await node.click();
    await assertSelection(page, concept, handoff, baselineNodes, fitted, width + '/click/' + concept.id);
    await node.focus();
    await node.press('Enter');
    await assertSelection(page, concept, handoff, baselineNodes, fitted, width + '/keyboard/' + concept.id);
  }
  await page.getByRole('button', {name: 'Zoom in', exact: true}).click();
  const enlarged = await viewport(page);
  assert.ok(enlarged[0] > fitted[0], width + ': zoom in did not increase scale');
  await page.getByLabel('Choose a concept', {exact: true}).selectOption(handoff.content.concepts[0].id);
  await assertSelection(page, handoff.content.concepts[0], handoff, baselineNodes, enlarged, width + '/zoomed-selection');
  await page.getByRole('button', {name: 'Zoom out', exact: true}).click();
  const reduced = await viewport(page);
  assert.ok(reduced[0] < enlarged[0], width + ': zoom out did not reduce scale');
  await page.locator('.concept-canvas').focus();
  const beforePan = await viewport(page);
  await page.locator('.concept-canvas').press('ArrowRight');
  const panned = await viewport(page);
  assert.ok(Math.abs(panned[4] - beforePan[4]) >= 10, width + ': keyboard pan had no effect');
  const last = handoff.content.concepts.at(-1);
  await page.getByLabel('Choose a concept', {exact: true}).selectOption(last.id);
  await assertSelection(page, last, handoff, baselineNodes, panned, width + '/panned-selection');
  await page.getByRole('button', {name: 'Fit map', exact: true}).click();
  closeMatrix(await viewport(page), fitted, width + ': Fit did not restore overview');
  selectionChecks.push({width, concepts: baselineNodes.length, click_and_keyboard: true, zoom_and_pan: true});
}

async function checkRail(page, handoff, width) {
  await page.setViewportSize({width, height: 950});
  await page.locator('[data-mode=reading]').click();
  await settle(page);
  assert.equal(await page.locator('#section-outline').count(), 1, width + ': duplicate section outline');
  const toggle = page.locator('.outline-toggle');
  if (width <= 860 && await toggle.count() && await toggle.isVisible() && await toggle.getAttribute('aria-expanded') !== 'true') {
    await toggle.click();
  }
  assert.equal(await page.locator('.hero h1').isVisible(), true, width + ': missing main title');
  assert.equal(await page.locator('.request-context').isVisible(), true, width + ': focus hidden');
  assert.ok((await page.locator('.request-context').textContent()).includes(handoff.input.focus), width + ': requested focus changed');
  assert.equal(await page.locator('.hero .request-context').evaluate(node => Boolean(node.closest('details'))), false);
  const metrics = await page.evaluate(() => {
    const rail = document.querySelector('.outline'), layout = document.querySelector('.layout');
    const nav = document.querySelector('#section-outline'), main = document.querySelector('#main');
    const r = rail.getBoundingClientRect(), l = layout.getBoundingClientRect(), m = main.getBoundingClientRect();
    const style = getComputedStyle(layout), navStyle = getComputedStyle(nav);
    const scrollContainers = [rail, ...rail.querySelectorAll('*')].filter(node => {
      const css = getComputedStyle(node);
      return /auto|scroll/.test(css.overflowY) && node.scrollHeight > node.clientHeight + 1;
    }).length;
    return {railWidth: r.width, available: l.width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
      railBottom: r.bottom, mainTop: m.top, navDisplay: navStyle.display, navWrap: navStyle.flexWrap,
      innerScrollbars: scrollContainers, overflow: document.documentElement.scrollWidth > innerWidth + 1,
      outlineOverflows: nav.scrollWidth > nav.clientWidth + 1};
  });
  assert.equal(metrics.innerScrollbars, 0, width + ': context rail gained an inner scrollbar');
  assert.equal(metrics.overflow, false, width + ': document horizontal overflow');
  assert.equal(metrics.outlineOverflows, false, width + ': outline clips horizontally');
  if (width > 860) {
    assert.ok(metrics.railWidth <= metrics.available * .22 + 1, width + ': context rail exceeds 22%');
    assert.ok(metrics.railWidth >= 150, width + ': desktop rail collapsed unexpectedly');
    const railText = await page.locator('.outline').textContent();
    assert.ok(railText.includes(handoff.source.title || handoff.content.title) || railText.includes(handoff.content.title),
      width + ': desktop rail lacks paper title');
    assert.ok(railText.includes(handoff.input.focus), width + ': desktop rail lacks focus');
  } else {
    assert.ok(metrics.mainTop >= metrics.railBottom - 2, width + ': mobile rail remains a miniature side column');
    assert.ok(metrics.navDisplay === 'grid' || (metrics.navDisplay === 'flex' && metrics.navWrap === 'wrap'),
      width + ': mobile outline does not wrap');
    assert.equal(await page.locator('#section-outline a').count(), handoff.content.sections.length);
  }
  railChecks.push({width, ...metrics});
}

async function checkTouch(browser) {
  const context = await browser.newContext({offline: true, viewport: {width: 390, height: 900}, hasTouch: true, isMobile: true});
  try {
    const page = await open(context);
    await page.locator('[data-mode=map]').tap();
    await settle(page);
    await page.locator('.concept-canvas').evaluate(node => node.scrollIntoView({block: 'center'}));
    await settle(page);
    const baselineNodes = await nodes(page), before = await viewport(page);
    const selected = await page.getByLabel('Choose a concept', {exact: true}).inputValue();
    const scrollBefore = await page.evaluate(() => scrollY);
    const point = await page.locator('.concept-canvas').evaluate(canvas => {
      const r = canvas.getBoundingClientRect();
      const nodeRects = [...canvas.querySelectorAll('[data-concept]')].map(node => node.getBoundingClientRect());
      for (const fy of [.15, .85, .35, .55, .75]) for (const fx of [.25, .45, .6]) {
        const x = r.left + r.width * fx, y = r.top + r.height * fy, target = document.elementFromPoint(x, y);
        // Chrome's touch adjustment may target a nearby button even when the
        // precise pixel is empty. Keep the entire gesture away from nodes.
        const clearOfNodes = nodeRects.every(n => x + 40 < n.left - 30 || x > n.right + 30 || y + 28 < n.top - 30 || y > n.bottom + 30);
        if (x > 0 && y > 130 && y + 35 < innerHeight && target && canvas.contains(target) && !target.closest('[data-concept]') && clearOfNodes) return {x, y};
      }
      return null;
    });
    assert.ok(point, 'No visible canvas background available for a real touch gesture');
    const cdp = await context.newCDPSession(page);
    const finger = (x, y) => ({x, y, id: 1, radiusX: 5, radiusY: 5, force: 1});
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [finger(point.x, point.y)]});
    for (let step = 1; step <= 4; step++) {
      await cdp.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [finger(point.x + step * 10, point.y + step * 7)]});
      await settle(page);
    }
    await cdp.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
    await settle(page);
    const after = await viewport(page);
    assert.ok(Math.abs(after[4] - before[4]) >= 20 && Math.abs(after[5] - before[5]) >= 10,
      'Touch drag did not pan canvas: ' + JSON.stringify({before, after, point}));
    assert.equal(after[0], before[0], 'One-finger touch pan changed scale');
    assert.ok(Math.abs(await page.evaluate(() => scrollY) - scrollBefore) <= 1, 'Canvas touch drag scrolled the document');
    assert.deepEqual(await nodes(page), baselineNodes, 'Touch pan altered graph layout');
    assert.equal(await page.getByLabel('Choose a concept', {exact: true}).inputValue(), selected, 'Touch background drag activated a node');
    await page.getByRole('button', {name: 'Zoom in', exact: true}).tap();
    await settle(page);
    assert.ok((await viewport(page))[0] > after[0], 'Touch-accessible zoom button had no effect: ' + JSON.stringify({after, zoomed: await viewport(page)}));
    await cdp.detach();
    return {viewport: 390, touch_pan: true, touch_zoom_control: true, page_scroll_preserved: true};
  } finally {
    await context.close();
  }
}

(async () => {
  let browser;
  try {
    if (screenshotDir) fs.mkdirSync(screenshotDir, {recursive: true});
    browser = await chromium.launch({channel: 'msedge', headless: true});
    const context = await browser.newContext({offline: true, viewport: {width: 1360, height: 950}});
    const page = await open(context);
    const {handoff} = JSON.parse(await page.locator('#lesson-data').textContent());
    assert.ok(handoff.content.concepts.length > 0, 'Lesson needs concepts for canvas checks');
    for (const width of widths) await checkRail(page, handoff, width);
    for (const width of [1360, 320]) await checkSelection(page, handoff, width);
    if (screenshotDir) {
      await page.setViewportSize({width: 1360, height: 950});
      await page.locator('[data-mode=map]').click(); await settle(page);
      await page.screenshot({path: path.join(screenshotDir, 'transmit-map-desktop.png')});
      await page.locator('[data-mode=reading]').click();
      await page.evaluate(() => scrollTo(0, 0));
      await page.screenshot({path: path.join(screenshotDir, 'transmit-reading-desktop.png')});
    }
    const touch = await checkTouch(browser);
    assert.deepEqual(failures, [], 'Browser runtime/console errors');
    assert.deepEqual(network, [], 'Unexpected remote dependency');
    const report = {status: 'passed', file, browser: await browser.version(), railChecks, selectionChecks, touch,
      offline_context: true, network_requests: network.length, runtime_errors: failures.length};
    if (screenshotDir) fs.writeFileSync(path.join(screenshotDir, 'transmit-browser-check.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally {
    clearTimeout(watchdog);
    if (browser) await browser.close();
  }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
