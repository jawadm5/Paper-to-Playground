/* Renderer-owned UI. Model text enters the DOM only through textContent. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('lesson-data').textContent);
  const {handoff, experience, plans} = data, content = handoff.content;
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const copy = value => JSON.parse(JSON.stringify(value));
  function presentedOptions(question) {
    const options = question.options.slice();
    let seed = 2166136261;
    for (const char of question.id) seed = Math.imul(seed ^ char.charCodeAt(0), 16777619) >>> 0;
    for (let index = options.length - 1; index > 0; index--) {
      seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5;
      const target = (seed >>> 0) % (index + 1);
      [options[index], options[target]] = [options[target], options[index]];
    }
    return options;
  }
  const fmt = n => typeof n === 'number' ? Number(n.toPrecision(4)).toString() : String(n);
  const exact = n => typeof n === 'number' ? String(n) : JSON.stringify(n);
  function element(tag, attrs = {}, text) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function svgElement(tag, attrs = {}, text) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function paragraph(text, className) { return element('p', className ? {class: className} : {}, text); }
  function button(text, callback, attrs = {}) {
    const node = element('button', {type: 'button', ...attrs}, text);
    node.addEventListener('click', callback); return node;
  }
  function svgText(svg, x, y, text, attrs = {}) { svg.append(svgElement('text', {x, y, ...attrs}, text)); }
  const state = {mode: 'reading', scroll: {reading: 0, map: 0, experiment: 0, assessment: 0}, concept: content.concepts[0]?.id, experiment: experience.experiments[0]?.id, submitted: false};
  function mode(name, target) {
    if (!['reading', 'map', 'experiment', 'assessment'].includes(name)) return;
    state.scroll[state.mode] = window.scrollY;
    state.mode = name;
    mountExperiments();
    $$('.mode-panel').forEach(node => { node.hidden = node.id !== name; });
    $$('[data-mode]').forEach(node => node.setAttribute('aria-pressed', String(node.dataset.mode === name)));
    $('.outline').hidden = name !== 'reading';
    $('.layout').classList.toggle('wide-mode', name !== 'reading');
    if (target) {
      const node = document.getElementById(target);
      if (node) { node.scrollIntoView({block: 'start'}); node.focus({preventScroll: true}); }
    } else { window.scrollTo(0, state.scroll[name]); $('#main').focus({preventScroll: true}); }
  }
  function read(section) {
    mode('reading');
    const node = document.getElementById(section);
    if (node) { node.scrollIntoView({block: 'start'}); node.focus({preventScroll: true}); }
  }
  $$('[data-mode]').forEach(node => node.addEventListener('click', () => mode(node.dataset.mode)));
  $$('[data-read]').forEach(node => node.addEventListener('click', event => { event.preventDefault(); read(node.hash.slice(1)); }));
  $$('[data-source]').forEach(node => node.addEventListener('click', event => {
    event.preventDefault(); const target = document.getElementById('source-' + node.dataset.source);
    if (target) { target.open = true; read(target.id); target.querySelector('summary').focus({preventScroll: true}); }
  }));
  $$('.enlarge').forEach(node => node.addEventListener('click', () => {
    const figure = node.closest('figure'), expanded = figure.classList.toggle('expanded');
    node.setAttribute('aria-expanded', String(expanded)); node.textContent = expanded ? 'Reduce figure' : 'Enlarge figure';
  }));
  $('.outline-toggle').addEventListener('click', event => {
    const opened = $('.outline').classList.toggle('mobile-open');
    event.currentTarget.setAttribute('aria-expanded', String(opened));
    event.currentTarget.textContent = opened ? 'In this guide −' : 'In this guide +';
  });
  $('#theme').addEventListener('click', () => {
    const dark = document.body.dataset.theme ? document.body.dataset.theme === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.body.dataset.theme = dark ? 'light' : 'dark';
  });
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      if (state.mode !== 'reading') return;
      const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible.length) $$('.outline a').forEach(node => {
        if (node.hash === '#' + visible[0].target.id) node.setAttribute('aria-current', 'location'); else node.removeAttribute('aria-current');
      });
    }, {rootMargin: '-130px 0px -55% 0px'});
    $$('.paper-section').forEach(section => observer.observe(section));
  }

  // Full-map coordinates depend on the dataset, never on selection.
  const conceptById = Object.fromEntries(content.concepts.map(c => [c.id, c]));
  const picker = element('select', {'aria-label': 'Choose a concept'});
  content.concepts.forEach(c => picker.append(element('option', {value: c.id}, c.name)));
  const toolbar = element('div', {class: 'map-toolbar'});
  const canvas = element('div', {class: 'concept-canvas', tabindex: '0', 'aria-label': 'Concept canvas. Drag background to pan; use zoom or fit controls.'});
  const layout = ConceptLayout.layout(content.concepts, content.relationships);
  const {width, height} = layout;
  const svg = svgElement('svg', {width, height, viewBox: `0 0 ${width} ${height}`, class: 'concept-world'});
  svg.style.width = width + 'px'; svg.style.height = height + 'px';
  const defs = svgElement('defs');
  for (const [id, color] of [['map-arrow', 'var(--baseline)'], ['map-arrow-active', 'var(--accent)']]) {
    const marker = svgElement('marker', {id, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 5, markerHeight: 5, orient: 'auto'});
    marker.append(svgElement('path', {d: 'M0 0 L10 5 L0 10 Z', fill: color})); defs.append(marker);
  }
  svg.append(defs);
  let zoom = 1, panX = 0, panY = 0, lastWidth = 0, lastHeight = 0;
  const zoomLabel = element('output', {'aria-label': 'Map zoom', class: 'map-zoom'});
  const apply = () => { svg.style.transform = `translate(${panX}px,${panY}px) scale(${zoom})`; zoomLabel.textContent = Math.round(zoom * 100) + '%'; };
  const fit = () => {
    zoom = Math.min((canvas.clientWidth - 24) / width, (canvas.clientHeight - 24) / height, 1);
    panX = (canvas.clientWidth - width * zoom) / 2; panY = (canvas.clientHeight - height * zoom) / 2; apply();
  };
  const scale = factor => {
    const next = Math.max(.05, Math.min(3, zoom * factor)), x = canvas.clientWidth / 2, y = canvas.clientHeight / 2;
    panX = x - (x - panX) * next / zoom; panY = y - (y - panY) * next / zoom; zoom = next; apply();
  };
  const zoomTools = element('div', {class: 'map-zoom-tools'});
  zoomTools.append(button('Zoom in', () => scale(1.25)), button('Zoom out', () => scale(.8)), button('Fit map', fit), zoomLabel);
  toolbar.append(element('label', {}, 'Find a concept'), picker, zoomTools);
  $('#concept-buttons').append(toolbar); $('#concept-map').before($('#concept-buttons')); $('#concept-map').append(canvas); canvas.append(svg);
  const edgeNodes = [];
  function connectorPath(points) {
    // Round each orthogonal bend, preserving the layout's obstacle-free routes.
    let d = `M${points[0][0]} ${points[0][1]}`;
    for (let i = 1; i < points.length - 1; i++) {
      const a = points[i - 1], b = points[i], c = points[i + 1];
      const before = Math.hypot(b[0] - a[0], b[1] - a[1]), after = Math.hypot(c[0] - b[0], c[1] - b[1]);
      const r = Math.min(10, before / 2, after / 2);
      if (!before || !after) continue;
      const p = [b[0] + (a[0] - b[0]) * r / before, b[1] + (a[1] - b[1]) * r / before];
      const q = [b[0] + (c[0] - b[0]) * r / after, b[1] + (c[1] - b[1]) * r / after];
      d += ` L${p[0]} ${p[1]} Q${b[0]} ${b[1]} ${q[0]} ${q[1]}`;
    }
    return d + ` L${points.at(-1)[0]} ${points.at(-1)[1]}`;
  }
  layout.edges.forEach(({index, points}) => {
    const edge = content.relationships[index];
    const path = svgElement('path', {d: connectorPath(points), fill: 'none', stroke: 'var(--baseline)', 'stroke-width': 1.6, 'marker-end': 'url(#map-arrow)', 'data-edge': index});
    path.append(svgElement('title', {}, conceptById[edge.from].name + ' → ' + edge.label + ' → ' + conceptById[edge.to].name));
    svg.append(path); edgeNodes.push({edge, path});
  });
  layout.nodes.forEach(node => {
    const c = conceptById[node.id], {x, y, width: w, height: h, lines} = node;
    const g = svgElement('g', {'data-concept': c.id, tabindex: '0', role: 'button', 'aria-label': c.name, transform: `translate(${x} ${y})`});
    g.append(svgElement('rect', {width: w, height: h, rx: 8, fill: 'var(--surface)', stroke: 'var(--line)', 'stroke-width': 1.5}));
    for (const cx of [0, w]) g.append(svgElement('circle', {cx, cy: h / 2, r: 4, fill: 'var(--surface)', stroke: 'var(--baseline)', 'stroke-width': 1.5}));
    const textTop = h / 2 - (lines.length - 1) * 9 + 5;
    lines.forEach((line, index) => g.append(svgElement('text', {x: w / 2, y: textTop + index * 18, 'text-anchor': 'middle', 'font-size': 14, 'font-weight': 500}, line)));
    g.append(svgElement('title', {}, c.name));
    g.onclick = () => selectConcept(c.id);
    g.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectConcept(c.id); } };
    svg.append(g);
  });
  function selectConcept(id) {
    if (!conceptById[id]) return;
    state.concept = id; picker.value = id; const c = conceptById[id];
    $$('[data-concept]').forEach(node => { const active = node.dataset.concept === id; node.setAttribute('aria-pressed', String(active)); node.querySelector('rect').setAttribute('stroke', active ? 'var(--accent)' : 'var(--line)'); });
    edgeNodes.forEach(({edge, path}) => {
      const active = edge.from === id || edge.to === id;
      path.setAttribute('stroke', active ? 'var(--accent)' : 'var(--baseline)'); path.setAttribute('stroke-width', active ? 2.6 : 1.6);
      path.setAttribute('marker-end', active ? 'url(#map-arrow-active)' : 'url(#map-arrow)');
    });
    const detail = $('#concept-detail');
    detail.replaceChildren(element('h2', {}, c.name), paragraph(c.summary), button('Read this explanation →', () => read(c.section_id)));
    content.relationships.filter(edge => edge.from === id || edge.to === id).forEach(edge => detail.append(paragraph(conceptById[edge.from].name + ' → ' + edge.label + ' → ' + conceptById[edge.to].name, 'map-edge')));
  }
  picker.onchange = () => selectConcept(picker.value);
  let drag = null;
  canvas.onpointerdown = event => { if (event.target.closest('[data-concept]') || event.button > 0) return; drag = [event.clientX - panX, event.clientY - panY]; canvas.setPointerCapture(event.pointerId); };
  canvas.onpointermove = event => { if (drag) { panX = event.clientX - drag[0]; panY = event.clientY - drag[1]; apply(); } };
  canvas.onpointerup = canvas.onpointercancel = () => { drag = null; };
  canvas.onkeydown = event => {
    if (event.target !== canvas) return;
    const shifts = {ArrowLeft: [30, 0], ArrowRight: [-30, 0], ArrowUp: [0, 30], ArrowDown: [0, -30]};
    if (shifts[event.key]) { event.preventDefault(); panX += shifts[event.key][0]; panY += shifts[event.key][1]; apply(); }
  };
  new ResizeObserver(() => {
    if (canvas.clientWidth && (canvas.clientWidth !== lastWidth || canvas.clientHeight !== lastHeight)) {
      lastWidth = canvas.clientWidth; lastHeight = canvas.clientHeight; fit();
    }
  }).observe(canvas);
  if (state.concept) selectConcept(state.concept);
  const railInner = $('.outline-inner');
  const fitRail = () => railInner.classList.toggle('rail-fits', railInner.scrollHeight < window.innerHeight - 155);
  new ResizeObserver(fitRail).observe(railInner); window.addEventListener('resize', fitRail); fitRail();

  // Experiments: one trusted calculation state drives every representation.
  const experiments = {}, experimentNodes = {};
  function mountExperiments(){
    for(const [id,node] of Object.entries(experimentNodes)){
      const target=state.mode==='experiment'?$('#experiment-panels'):document.getElementById('inline-'+id);
      if(target&&node.parentElement!==target)target.append(node);
      node.hidden=state.mode==='experiment'&&id!==state.experiment;
    }
  }
  function chooseExperiment(id) {
    if (!experiments[id]) return;
    state.experiment = id;
    mountExperiments();
    $$('[data-exp-tab]').forEach(node => node.setAttribute('aria-pressed', String(node.dataset.expTab === id)));
  }
  $$('[data-experiment]').forEach(node => node.addEventListener('click', () => { chooseExperiment(node.dataset.experiment); mode('experiment', 'experiment'); }));
  function defaultInputs(exp) { return Object.fromEntries(exp.variables.map(v => [v.id, copy(v.default)])); }
  function flatten(value) { return Array.isArray(value) ? value.flat(Infinity) : [value]; }
  function table(headers, rows, caption) {
    const wrap = element('div', {class: 'table-wrap'}), node = element('table'), head = element('thead'), tr = element('tr');
    node.append(element('caption', {}, caption)); headers.forEach(text => tr.append(element('th', {scope: 'col'}, text))); head.append(tr); node.append(head);
    const body = element('tbody'); rows.forEach(values => { const row = element('tr'); values.forEach((value, index) => { const cell = element(index ? 'td' : 'th', index ? {} : {scope: 'row'}); if (value instanceof Node) cell.append(value); else cell.textContent = value; row.append(cell); }); body.append(row); });
    node.append(body); wrap.append(node); return wrap;
  }
  function chart(view, values, baseline) {
    const width = 650, height = 310, left = 66, top = 30, bottom = 255, right = 25;
    const svg = svgElement('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': view.title + '. Exact values are in the table below.'});
    const scatter = view.kind === 'scatter';
    const ys = scatter ? values[1] : values[0], bys = scatter ? baseline[1] : baseline[0];
    const low = Math.min(0, ...ys, ...bys), highRaw = Math.max(0, ...ys, ...bys), high = highRaw === low ? low + 1 : highRaw;
    const y = n => bottom - (n - low) / (high - low) * (bottom - top), count = ys.length;
    const xs = scatter ? values[0] : ys.map((_, index) => index + 1), bxs = scatter ? baseline[0] : xs;
    let xlow = Math.min(...xs, ...bxs), xhigh = Math.max(...xs, ...bxs); if (xhigh === xlow) { xlow -= .5; xhigh += .5; }
    const x = n => left + (n - xlow) / (xhigh - xlow) * (width - left - right);
    for (let i = 0; i <= 4; i++) {
      const val = low + (high - low) * i / 4, py = y(val);
      svg.append(svgElement('line', {x1: left, y1: py, x2: width - right, y2: py, stroke: 'var(--line)'}));
      svgText(svg, left - 8, py + 4, fmt(val), {'text-anchor': 'end'});
    }
    svgText(svg, left, 15, view.y_label || 'Value');
    svgText(svg, (left + width - right) / 2, height - 9, view.x_label || (scatter ? 'X' : 'Element'), {'text-anchor': 'middle'});
    [bys, ys].forEach((series, si) => {
      const color = si ? 'var(--accent)' : 'var(--baseline)';
      if (view.kind === 'bars') {
        const step = (width - left - right) / count, bw = Math.min(35, step * .3);
        series.forEach((value, i) => {
          const px = left + step * (i + .5) + (si ? 2 : -bw - 2), py = Math.min(y(value), y(0)), h = Math.abs(y(value) - y(0));
          const rect = svgElement('rect', {x: px, y: py, width: bw, height: Math.max(.7, h), fill: color});
          rect.append(svgElement('title', {}, (view.labels[i] || String(i + 1)) + ' ' + (si ? 'Current ' : 'Baseline ') + exact(value))); svg.append(rect);
          if (si && count <= 12) svgText(svg, px + bw / 2, value >= 0 ? py - 7 : py + h + 14, fmt(value), {'text-anchor': 'middle'});
        });
      } else {
        const xseries = si ? xs : bxs;
        if (!scatter) svg.append(svgElement('polyline', {points: series.map((value, i) => x(xseries[i]) + ',' + y(value)).join(' '), fill: 'none', stroke: color, 'stroke-width': 2}));
        series.forEach((value, i) => { const dot = svgElement('circle', {cx: x(xseries[i]), cy: y(value), r: si ? 4 : 5, fill: color}); dot.append(svgElement('title', {}, (si ? 'Current' : 'Baseline') + ' (' + exact(xseries[i]) + ', ' + exact(value) + ')')); svg.append(dot); });
      }
    });
    const stride = Math.max(1, Math.ceil(count / 10));
    ys.forEach((_, i) => { if (i % stride) return; const px = view.kind === 'bars' ? left + (width - left - right) * (i + .5) / count : x(xs[i]); svgText(svg, px, bottom + 21, view.labels[i] || fmt(xs[i]), {'text-anchor': 'middle'}); });
    return svg;
  }
  function viewNode(exp, view, run, base, fixedRange) {
    const node = element('section', {class: 'view', 'data-view': view.id}); node.append(element('h3', {}, view.title));
    if (view.explanation) node.append(paragraph(view.explanation));
    const values = view.output_ids.map(id => run.outputs[id]), baseline = view.output_ids.map(id => base.outputs[id]);
    const output = exp.computation.outputs.find(o => o.id === view.output_ids[0]);
    if (view.kind === 'scalar') {
      const value = element('div', {class: 'scalar', 'data-value': exact(values[0])}, fmt(values[0])); value.append(element('small', {}, output?.unit || '')); node.append(value);
      node.append(paragraph('Baseline: ' + fmt(baseline[0]) + (output?.unit ? ' ' + output.unit : ''), 'muted small'));
      node.append(table(['Quantity', 'Baseline', 'Current'], [[output?.label || output?.id || 'Value', exact(baseline[0]), exact(values[0])]], 'Exact stored values'));
    } else if (view.kind === 'matrix') {
      const matrix = values[0], bmatrix = baseline[0], rows = view.row_labels?.length ? view.row_labels : matrix.map((_, i) => 'Row ' + (i + 1)), cols = view.column_labels?.length ? view.column_labels : matrix[0].map((_, i) => 'Col ' + (i + 1));
      const low = fixedRange[0], high = fixedRange[1], width = 650, left = 100, top = 35, cellH = Math.max(32, Math.min(65, 330 / matrix.length)), cellW = (width - left - 15) / matrix[0].length, height = top + cellH * matrix.length + 40;
      const svg = svgElement('svg', {viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': view.title + '. Use the table buttons to inspect each cell.'});
      const info = paragraph('Select a cell in the table to compare current and baseline values.', 'cell-info'); info.setAttribute('aria-live', 'polite');
      function inspect(r, c) { info.textContent = rows[r] + ' → ' + cols[c] + ': ' + exact(matrix[r][c]) + ' ' + (output?.unit || '') + ' (baseline ' + exact(bmatrix[r][c]) + ')'; }
      matrix.forEach((row, r) => { svgText(svg, left - 8, top + r * cellH + cellH / 2 + 4, rows[r], {'text-anchor': 'end'}); row.forEach((value, c) => {
        const x = left + c * cellW, y = top + r * cellH, opacity = Math.max(0,Math.min(1,low<0?Math.abs(value)/Math.max(Math.abs(low),Math.abs(high)):(value-low)/(high-low)))*.6;
        const g = svgElement('g', {cursor: 'pointer'}); g.append(svgElement('rect', {x: x + 2, y: y + 2, width: cellW - 4, height: cellH - 4, fill: 'var(--soft)'})); g.append(svgElement('rect', {x: x + 2, y: y + 2, width: cellW - 4, height: cellH - 4, fill: value<0?'var(--query)':'var(--accent)', opacity}));
        if (cellW > 40) svgText(g, x + cellW / 2, y + cellH / 2 + 4, fmt(value), {'text-anchor': 'middle', fill: 'var(--text)'});
        g.append(svgElement('title', {}, rows[r] + ', ' + cols[c] + ': ' + exact(value))); g.addEventListener('click', () => inspect(r, c)); svg.append(g);
      }); }); cols.forEach((name, i) => svgText(svg, left + (i + .5) * cellW, height - 10, name, {'text-anchor': 'middle'})); node.append(svg);
      node.append(paragraph('Fixed color scale: ' + fmt(low) + ' to ' + fmt(high) + '. Values outside this range use the nearest end color; exact values remain visible.', 'legend'), info);
      const matrixRows = matrix.map((row, r) => [rows[r], ...row.map((value, c) => button(fmt(value), () => inspect(r, c), {'aria-label': rows[r] + ', ' + cols[c] + ', ' + exact(value)}))]);
      node.append(table(['Current', ...cols], matrixRows, 'Current matrix: select a value to inspect it'));
      const details = element('details'); details.append(element('summary', {}, 'Exact current and baseline values'));
      details.append(table(['Cell', 'Baseline', 'Current'], matrix.flatMap((row, r) => row.map((value, c) => [rows[r] + ' / ' + cols[c], exact(bmatrix[r][c]), exact(value)])), 'All matrix values')); node.append(details);
    } else if (view.kind === 'steps') {
      const list = element('ol', {class: 'steps'}); exp.computation.steps.forEach(step => {
        const li = element('li'); li.append(element('strong', {}, step.label), paragraph(step.explanation));
        const rows = step.output_ids.filter(id => view.output_ids.includes(id)).map(id => [id, exact(base.outputs[id]), exact(run.outputs[id])]);
        if (rows.length) li.append(table(['Output', 'Baseline', 'Current'], rows, 'Worked numerical result'));
        list.append(li);
      }); node.append(list);
    } else {
      const legend = paragraph('Current: blue · Baseline: gray. Both use the same axis scale.', 'legend'); node.append(legend, chart(view, values, baseline));
      const rows = values[0].map((value, i) => view.kind === 'scatter' ? [view.labels[i] || String(i + 1), exact(baseline[0][i]), exact(baseline[1][i]), exact(value), exact(values[1][i])] : [view.labels[i] || String(i + 1), exact(baseline[0][i]), exact(value)]);
      const details = element('details'); details.append(element('summary', {}, 'View exact data table'), table(view.kind === 'scatter' ? ['Point', 'Baseline X', 'Baseline Y', 'Current X', 'Current Y'] : [view.x_label || 'Element', 'Baseline', 'Current'], rows, view.title + (output?.unit ? ' (' + output.unit + ')' : ''))); node.append(details);
    }
    return node;
  }
  experience.experiments.forEach(exp => {
    const model = createDeclarativeModel(plans[exp.id]), inputs = defaultInputs(exp), initial = model.compute(inputs);
    const item = {exp, model, inputs, result: initial, baseline: {inputs: copy(inputs), result: copy(initial)}, invalid: false, selectedQuery:0}; experiments[exp.id] = item;
    const host = element('div', {'data-experiment-panel': exp.id}); experimentNodes[exp.id] = host;
    const heading = element('header', {class: 'experiment-header'}); heading.append(element('h2', {}, exp.title), paragraph(exp.goal), button('Return to the explanation →', () => read(exp.section_id))); host.append(heading);
    const grid = element('div', {class: 'experiment-grid'}), controls = element('div', {class: 'panel controls'}), visuals = element('div', {class: 'visuals'}), fields = [];
    exp.variables.forEach(variable => {
      const fieldset = element('fieldset', {class: 'variable'}); fieldset.append(element('legend', {title:variable.explanation}, variable.label + (variable.unit ? ' (' + variable.unit + ')' : '')));
      const domain = variable.domain;
      function inputAt(path, value, label) {
        const id = exp.id + '-' + variable.id + '-' + (path.length ? path.join('-') : 'value'), input = element('input', {id, type: 'number', min: domain.min, max: domain.max, step: domain.step, value, 'aria-label': variable.label + (label ? ' ' + label : ''), 'data-input-variable': variable.id, 'aria-describedby': exp.id + '-error'});
        const entry = {variable, path, input, slider: null}; fields.push(entry); input.addEventListener('input', recompute); return entry;
      }
      if (['number', 'integer'].includes(variable.type)) {
        const entry = inputAt([], variable.default, ''), row = element('div', {class: 'number-control'}), left = element('div');
        const range = element('input', {type: 'range', min: domain.min, max: domain.max, step: domain.step, value: variable.default, 'aria-label': variable.label + ' slider'}); entry.slider = range;
        range.addEventListener('input', () => { entry.input.value = range.value; recompute(); });
        const labels = element('div', {class: 'domain-labels'}); labels.append(element('span', {}, fmt(domain.min)), element('span', {}, fmt(domain.max))); left.append(range, labels); row.append(left, entry.input); fieldset.append(row);
      } else {
        const entries = variable.type === 'matrix' ? variable.default : [variable.default];
        entries.forEach((values, r) => { const row = element('div', {class: variable.type === 'matrix' ? 'matrix-input-row' : 'array-inputs'}); values.forEach((value, c) => {
          const label = variable.type === 'matrix' ? `${r + 1},${c + 1}` : String(c + 1), entry = inputAt(variable.type === 'matrix' ? [r, c] : [c], value, label), wrap = element('label', {for: entry.input.id}, label); wrap.append(entry.input); row.append(wrap);
        }); fieldset.append(row); });
        fieldset.append(paragraph('Each value: ' + fmt(domain.min) + ' to ' + fmt(domain.max), 'small muted'));
      }
      controls.append(fieldset);
    });
    const error = paragraph('', 'invalid-message'); error.id = exp.id + '-error'; error.hidden = true; error.setAttribute('role', 'alert'); controls.append(error);
    const actions = element('div', {class: 'actions'}), save = button('Use current as baseline', () => { if (item.invalid) return; item.baseline = {inputs: copy(item.inputs), result: copy(item.result)}; update(); }), reset = button('Reset inputs', () => {
      const defaults = defaultInputs(exp); fields.forEach(f => { let value = defaults[f.variable.id]; f.path.forEach(index => { value = value[index]; }); f.input.value = value; if (f.slider) f.slider.value = value; }); recompute();
    }); actions.append(save, reset); controls.append(actions);
    const baselineCaption = paragraph('', 'baseline-label'); controls.append(baselineCaption);
    const assumptions = element('div',{class:'teaching-limits'}); assumptions.append(element('h4', {}, 'Teaching assumptions and limits')); exp.assumptions.forEach(text => assumptions.append(paragraph(text))); host.append(assumptions);
    grid.append(controls, visuals); host.append(grid);
    const fitControls = () => controls.classList.toggle('tall-controls', controls.scrollHeight > window.innerHeight - 170);
    if ('ResizeObserver' in window) new ResizeObserver(fitControls).observe(controls);
    window.addEventListener('resize', fitControls);
    const guided = element('section', {class: 'panel guided'}), list = element('ol'); guided.append(element('h3', {}, 'Two minutes of discovery'));
    exp.challenges.forEach(challenge => list.append(element('li', {}, challenge.instructions))); guided.append(list); host.append(guided);
    const ranges = Object.fromEntries(exp.views.filter(v => v.kind === 'matrix').map(v => { const vals = flatten(initial.outputs[v.output_ids[0]]); const low = Math.min(0, ...vals), high = Math.max(1, ...vals); return [v.id, v.color_domain || [low, high]]; }));
    const science = new Map();
    const presentation={selectedQuery:0};
    const change={input(id,value){fields.filter(f=>f.variable.id===id).forEach(f=>{let v=value;f.path.forEach(i=>v=v[i]);f.input.value=v;});recompute();},select(index){presentation.selectedQuery=index;update();}};
    exp.views.forEach(view=>{if(ResearchDiagrams.kinds.has(view.kind))science.set(view.id,ResearchDiagrams.create(view,exp,change));});
    function update() {
      baselineCaption.textContent = 'Baseline saved · Reset restores starting inputs.';
      exp.views.forEach(view=>{
        const special=science.get(view.id);
        if(special){if(!special.element.parentElement)visuals.append(special.element);special.update(item.inputs,item.result,item.baseline.result,presentation);}
        else {const fresh=viewNode(exp,view,item.result,item.baseline.result,ranges[view.id]),old=visuals.querySelector('[data-view="'+view.id+'"]');if(old)old.replaceWith(fresh);else visuals.append(fresh);}
      });
      host.dataset.valid = String(!item.invalid);
    }
    function recompute() {
      const candidate = copy(item.inputs); let bad = false;
      fields.forEach(f => {
        const raw = f.input.value.trim(), value = Number(raw), domain = f.variable.domain;
        const invalid = raw === '' || !Number.isFinite(value) || value < domain.min || value > domain.max || f.variable.type === 'integer' && !Number.isInteger(value);
        f.input.setAttribute('aria-invalid', String(invalid)); bad ||= invalid;
        if (!f.path.length) candidate[f.variable.id] = value;
        else { let target = candidate[f.variable.id]; f.path.slice(0, -1).forEach(index => { target = target[index]; }); target[f.path[f.path.length - 1]] = value; }
      });
      try {
        if (bad) throw new Error('Enter a finite value inside each input’s stated bounds.');
        const validation = model.validateInputs(candidate); if (!validation.valid) throw new Error(validation.errors.map(e => e.message).join(' '));
        const result = model.compute(candidate); item.inputs = candidate; item.result = result; item.invalid = false;
        error.hidden = true; save.disabled = false;
        fields.forEach(f => { if (f.slider) f.slider.value = candidate[f.variable.id]; }); update();
      } catch (failure) {
        item.invalid = true; error.hidden = false; error.textContent = failure.message + ' All views still show the last valid result. Correct the input or reset it.'; save.disabled = true; host.dataset.valid = 'false';
      }
    }
    if(experience.experiments.length>1)$('#experiment-tabs').append(button(exp.title, () => chooseExperiment(exp.id), {'data-exp-tab': exp.id, 'aria-pressed': 'false'}));
    $('#experiment-panels').append(host); update();
  });
  if (state.experiment) chooseExperiment(state.experiment);
  else $('#experiment-panels').append(paragraph(experience.no_experiments_reason || 'This scope is best explored through the reading guide and concept map.', 'panel'));

  // Assessment: complete submission is the only path that reveals feedback.
  const answers = {};
  experience.questions.forEach((question, index) => {
    const box = element('section', {class: 'question', id: 'question-' + question.id, role:'group','aria-labelledby':'prompt-'+question.id}); const header=element('div',{class:'question-header'});header.append(element('span',{class:'question-number'},String(index+1)),element('span',{class:'question-meta'},`Question ${index+1} of ${experience.questions.length} · ${question.level}`));box.append(header,element('h3',{id:'prompt-'+question.id},question.prompt));
    if (question.scenario_inputs) {
      const exp = experience.experiments.find(item => item.id === question.experiment_id);
      box.append(table(['Input', 'Scenario value'], Object.entries(question.scenario_inputs).map(([id, value]) => [exp?.variables.find(v => v.id === id)?.label || id, exact(value)]), 'Fixed scenario for this question'));
    }
    if (question.experiment_id) box.append(button('Explore this experiment →', () => {
      chooseExperiment(question.experiment_id); mode('experiment', 'experiment');
    }, {'data-question-experiment': question.experiment_id}));
    if (question.kind === 'choice') presentedOptions(question).forEach(option => {
      const label = element('label', {class: 'option'}), input = element('input', {type: 'radio', name: question.id, value: option.id});
      input.addEventListener('change', () => { answers[question.id] = option.id; }); label.append(input, element('span', {}, option.text)); box.append(label);
    });
    else {
      const input = element('input', {type: 'number', step: 'any', 'aria-label': 'Your answer to question ' + (index + 1), name: question.id});
      input.addEventListener('input', () => { answers[question.id] = input.value.trim() === '' ? null : Number(input.value); }); box.append(input, paragraph('Enter a number. Feedback and any accepted tolerance appear after final submission.', 'small muted'));
    }
    $('#questions').append(box);
  });
  $('#quiz').addEventListener('submit', event => {
    event.preventDefault();
    const incomplete = experience.questions.find(q => q.kind === 'choice' ? !q.options.some(option => option.id === answers[q.id]) : typeof answers[q.id] !== 'number' || !Number.isFinite(answers[q.id]));
    if (incomplete) { $('#quiz-error').hidden = false; $('#quiz-error').textContent = 'Complete every question before submitting. Your existing answers are saved.'; document.getElementById('question-' + incomplete.id).querySelector('input').focus(); return; }
    $('#quiz-error').hidden = true; state.submitted = true;
    const marks = experience.questions.map(q => ({question: q, correct: q.kind === 'choice' ? answers[q.id] === q.correct_option_id : Math.abs(answers[q.id] - q.expected) <= q.tolerance}));
    const score = marks.filter(mark => mark.correct).length, result = $('#quiz-results');
    result.replaceChildren(element('h2', {class: 'results-heading'}, score + ' / ' + marks.length + ' correct'), paragraph('A snapshot of this attempt. Use the explanations below to decide what to revisit.'));
    content.learning_outcomes.forEach(outcome => {
      const related = marks.filter(mark => mark.question.outcome_id === outcome.id), correct = related.filter(mark => mark.correct).length;
      const row = element('div', {class: 'outcome-result'}); row.append(element('strong', {}, outcome.description), paragraph(correct + ' / ' + related.length + ' questions correct · ' + (correct === related.length ? 'Demonstrated in this attempt' : 'Worth revisiting'), 'muted')); result.append(row);
    });
    marks.forEach(({question: q, correct}, index) => {
      const row = element('section', {class: 'result-item'}); row.append(element('h3', {class: correct ? 'correct' : 'incorrect'}, `${index + 1}. ${correct ? 'Correct' : 'Revisit this idea'}`), paragraph(q.prompt));
      const expected = q.kind === 'choice' ? q.options.find(option => option.id === q.correct_option_id).text : exact(q.expected) + ' (absolute tolerance ' + exact(q.tolerance) + ')';
      const chosen = q.kind === 'choice' ? q.options.find(option => option.id === answers[q.id]).text : exact(answers[q.id]);
      row.append(paragraph('Your answer: ' + chosen), paragraph('Expected: ' + expected), paragraph(q.explanation), button('Revisit the explanation →', () => read(q.section_id))); result.append(row);
    });
    result.append(button('Try the assessment again', () => { state.submitted = false; result.hidden = true; $('#quiz').hidden = false; $('#quiz').querySelector('input')?.focus(); }));
    $('#quiz').hidden = true; result.hidden = false; result.scrollIntoView({block: 'start'}); result.focus({preventScroll: true});
  });
  document.documentElement.dataset.researchLabReady = 'true';
})();
