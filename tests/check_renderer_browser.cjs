/* Local, network-blocked Chromium verification of a rendered lesson. */
const {chromium} = require('playwright');
const {pathToFileURL} = require('node:url');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
  const file = path.resolve(process.argv[2] || 'examples/attention-output.html');
  const screenshotDir = process.argv[3] ? path.resolve(process.argv[3]) : null;
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const context = await browser.newContext({offline: true, viewport: {width: 1360, height: 1000}});
  const page = await context.newPage(), errors = [], network = [], consoleErrors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
  await page.goto(pathToFileURL(file).href);
  await page.waitForFunction(() => document.documentElement.dataset.researchLabReady === 'true');
  const payload = await page.locator('#lesson-data').textContent();
  const {experience, handoff} = JSON.parse(payload);
  assert.equal(await page.locator('.simple-explanation').count(), handoff.content.sections.length);
  assert.equal(await page.locator('#source-evidence, .section-evidence').count(),0);
  assert.equal(await page.locator('#reading > details, .paper-section > details').count(),0);
  assert.equal(await page.locator('.question-number').count(),experience.questions.length);
  if (screenshotDir) { fs.mkdirSync(screenshotDir, {recursive: true}); await page.screenshot({path: path.join(screenshotDir, 'reading-desktop.png')}); }
  await page.locator('[data-mode=map]').click();
  const beforeMap=await page.locator('[data-concept]').evaluateAll(nodes=>nodes.map(n=>[n.dataset.concept,n.getAttribute('transform')]));
  await page.getByLabel('Choose a concept',{exact:true}).selectOption(handoff.content.concepts.at(-1).id);
  assert.deepEqual(await page.locator('[data-concept]').evaluateAll(nodes=>nodes.map(n=>[n.dataset.concept,n.getAttribute('transform')])),beforeMap);
  assert.equal(beforeMap.length,handoff.content.concepts.length);
  await page.getByRole('button',{name:'Zoom in',exact:true}).click();await page.getByRole('button',{name:'Fit map',exact:true}).click();
  assert.ok((await page.locator('#concept-detail h2').textContent()).length > 0);
  await page.getByRole('button', {name: 'Read this explanation →', exact: true}).click();
  assert.equal(await page.locator('#reading').isVisible(), true);
  if(screenshotDir) { await page.locator('[data-mode=map]').click(); await page.screenshot({path:path.join(screenshotDir,'map-desktop.png')}); await page.locator('[data-mode=reading]').click(); }
  let interactions = 0;
  if (experience.experiments.length) {
    assert.equal(await page.locator('#reading [data-experiment-panel]').count(), experience.experiments.length);
    await page.locator('[data-mode=experiment]').click();
    assert.equal(await page.locator('#experiment').isVisible(), true);
    const exp = experience.experiments[0], panel = page.locator(`[data-experiment-panel="${exp.id}"]`);
    const input = panel.locator('input[type=number]').first();
    const startValue = await input.inputValue();
    const textBefore = await panel.locator('.visuals').innerText();
    await input.fill('');
    assert.equal(await panel.getAttribute('data-valid'), 'false');
    assert.equal(await panel.locator('.visuals').innerText(), textBefore);
    assert.equal(await panel.getByRole('button', {name: 'Use current as baseline'}).isDisabled(), true);
    assert.match(await panel.locator('.invalid-message').textContent(), /last valid/);
    const variable = exp.variables[0];
    await input.fill(String(variable.domain.min));
    assert.equal(await panel.getAttribute('data-valid'), 'true');
    await panel.getByRole('button', {name: 'Use current as baseline'}).click();
    const baseline = await panel.locator('.baseline-label').textContent();
    await input.fill(String(variable.domain.max));
    assert.equal(await panel.getAttribute('data-valid'), 'true');
    assert.equal(await panel.locator('.baseline-label').textContent(), baseline);
    await page.locator('[data-mode=map]').click();
    await page.locator('[data-mode=experiment]').click();
    assert.equal(await input.inputValue(), String(variable.domain.max));
    await page.locator('[data-mode=reading]').click();
    assert.equal(await page.locator('#reading [data-experiment-panel]').count(),experience.experiments.length);
    assert.equal(await input.inputValue(),String(variable.domain.max));
    await page.locator('[data-mode=experiment]').click();
    await panel.getByRole('button', {name: 'Reset inputs'}).click();
    assert.equal(await input.inputValue(), startValue);
    assert.equal(await panel.locator('.baseline-label').textContent(), baseline);
    const cell = panel.locator('.view .table-wrap button').first();
    if (await cell.count()) { await cell.click(); assert.match(await panel.locator('.cell-info').first().textContent(), /baseline/); }
    for (const view of exp.views) assert.equal(await panel.locator(`[data-view="${view.id}"]`).count(), 1);
    const slider = panel.locator('input[type=range]').first();
    if (await slider.count()) { await slider.focus(); await slider.press('ArrowRight'); assert.equal(await panel.getAttribute('data-valid'), 'true'); }
    if (screenshotDir) { await page.evaluate(() => window.scrollTo(0,0)); await page.screenshot({path: path.join(screenshotDir, 'experiment-desktop.png')}); }
    const scientific=panel.locator('.science-view');
    if(await scientific.count()) {
      const vector=panel.locator('[data-kind=vector_compare]');
      if(await vector.count()) {
        const direction=vector.getByRole('slider',{name:'Query direction',exact:true});
        if(await direction.isEnabled()) { const before=await panel.locator('[data-kind=weight_distribution]').innerText(); await direction.fill('90'); await direction.dispatchEvent('input'); assert.equal(await panel.getAttribute('data-valid'),'true'); assert.notEqual(await panel.locator('[data-kind=weight_distribution]').innerText(),before); }
      }
      const process=panel.locator('[data-kind=process]');
      if(await process.count()) { await process.getByRole('button',{name:'Next step',exact:true}).click(); assert.equal(await process.getByRole('button',{name:'Previous step',exact:true}).isEnabled(),true); }
      for(const kind of ['vector_compare','weighted_blend','contribution_flow']){const view=panel.locator(`[data-kind="${kind}"]`);if(await view.count()&&screenshotDir)await view.screenshot({path:path.join(screenshotDir,kind+'.png')});}
      // Moving between placements retains the same mounted view and chosen process step.
      await page.locator('[data-mode=reading]').click();
      assert.equal(await page.locator('#reading .science-view').count(),await scientific.count());
      await page.locator('[data-mode=experiment]').click();
    }
    interactions++;
  }
  await page.locator('[data-mode=assessment]').click();
  if(screenshotDir)await page.screenshot({path:path.join(screenshotDir,'assessment-desktop.png')});
  await page.getByRole('button', {name: 'Submit assessment', exact: true}).click();
  assert.equal(await page.locator('#quiz-results').isHidden(), true);
  assert.equal(await page.locator('#quiz-error').isVisible(), true);
  for (const question of experience.questions) {
    const field = page.locator(`#question-${question.id}`);
    if (question.kind === 'choice') {
      const presentedIds = await field.locator('input[type=radio]').evaluateAll(nodes => nodes.map(node => node.value));
      assert.deepEqual([...presentedIds].sort(), question.options.map(option => option.id).sort());
      await field.locator(`input[value="${question.correct_option_id}"]`).check();
    }
    else await field.locator('input').fill(String(question.expected));
  }
  const predictionLink = page.locator('[data-question-experiment]').first();
  if (await predictionLink.count()) {
    await predictionLink.click();
    assert.equal(await page.locator('#experiment').isVisible(), true);
    await page.locator('[data-mode=assessment]').click();
    assert.equal(await page.locator('#quiz-results').isHidden(), true);
  }
  await page.locator('[data-mode=reading]').click();
  await page.locator('[data-mode=assessment]').click();
  assert.equal(await page.locator('#quiz-results').isHidden(), true);
  await page.getByRole('button', {name: 'Submit assessment', exact: true}).click();
  assert.equal(await page.locator('.results-heading').textContent(), `${experience.questions.length} / ${experience.questions.length} correct`);
  assert.equal(await page.locator('.outcome-result').count(), handoff.content.learning_outcomes.length);
  await page.getByRole('button', {name: 'Revisit the explanation →', exact: true}).first().click();
  assert.equal(await page.locator('#reading').isVisible(), true);
  const image = page.locator('.source-figure img').first();
  if (await image.count()) {
    await image.scrollIntoViewIfNeeded();
    assert.equal(await image.evaluate(img => img.complete && img.naturalWidth > 0), true);
    await page.getByRole('button', {name: 'Enlarge figure', exact: true}).first().click();
    assert.equal(await page.locator('.source-figure.expanded').count(), 1);
  }
  const overflow = [];
  for (const width of [1360, 390, 320]) {
    await page.setViewportSize({width, height: 900});
    for (const mode of ['reading', 'map', 'experiment', 'assessment']) {
      await page.locator(`[data-mode="${mode}"]`).click();
      if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)) overflow.push({width, mode});
    }
  }
  await page.emulateMedia({colorScheme: 'dark', reducedMotion: 'reduce'});
  await page.locator('[data-mode=reading]').click();
  if (screenshotDir) { await page.evaluate(() => window.scrollTo(0,0)); await page.screenshot({path: path.join(screenshotDir, 'reading-mobile-dark.png')}); }
  assert.deepEqual(errors, []);
  assert.deepEqual(consoleErrors, []);
  assert.deepEqual(network, []);
  assert.deepEqual(overflow, []);
  const report = {status: 'passed', file, browser: await browser.version(), network_requests: network.length, page_errors: errors.length, console_errors: consoleErrors.length, horizontal_overflow: overflow, viewports: [1360,390,320], assessment_questions: experience.questions.length, experiments_exercised: interactions, offline_context: true};
  console.log(JSON.stringify(report, null, 2));
  if (screenshotDir) fs.writeFileSync(path.join(screenshotDir, 'browser-check.json'), JSON.stringify(report, null, 2));
  await browser.close();
})().catch(error => { console.error(error.stack); process.exit(1); });
