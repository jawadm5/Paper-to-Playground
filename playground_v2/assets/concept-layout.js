/* Deterministic directed concept layout. No DOM, remote assets, or paper-specific rules. */
(function (global) {
  'use strict';
  const NODE_W = 176, COLUMN_GAP = 72, ROW_GAP = 30, PAD = 30;
  function linesFor(text) {
    const words = String(text || '').split(/\s+/), lines = [];
    let line = '';
    words.forEach(word => {
      while (word.length > 23) {
        if (line) { lines.push(line); line = ''; }
        lines.push(word.slice(0, 23)); word = word.slice(23);
      }
      if (line && (line + ' ' + word).length > 23) { lines.push(line); line = ''; }
      line += (line ? ' ' : '') + word;
    });
    if (line) lines.push(line);
    return lines.length ? lines : ['Concept'];
  }
  function layout(concepts, relationships) {
    const nodes = concepts.map((c, order) => {
      const lines = linesFor(c.name);
      return { id: c.id, order, lines, width: NODE_W, height: Math.max(62, lines.length * 17 + 24) };
    });
    if (!nodes.length) return { nodes: [], edges: [], width: 600, height: 400 };
    const byId = new Map(nodes.map(n => [n.id, n]));
    const edges = relationships.map((e, index) => ({ index, from: e.from, to: e.to }))
      .filter(e => byId.has(e.from) && byId.has(e.to));
    const adjacent = new Map(nodes.map(n => [n.id, []]));
    edges.forEach(e => { adjacent.get(e.from).push(e.to); adjacent.get(e.to).push(e.from); });
    const seen = new Set(), components = [];
    nodes.forEach(n => {
      if (seen.has(n.id)) return;
      const queue = [n.id], group = []; seen.add(n.id);
      while (queue.length) {
        const id = queue.shift(); group.push(byId.get(id));
        adjacent.get(id).forEach(next => { if (!seen.has(next)) { seen.add(next); queue.push(next); } });
      }
      components.push(group.sort((a, b) => a.order - b.order));
    });
    // Keep the largest connected story first; disconnected ideas remain visible below it.
    components.sort((a, b) => b.length - a.length || a[0].order - b[0].order);
    let offsetY = PAD, maxX = 0;
    components.forEach(group => {
      const ids = new Set(group.map(n => n.id));
      const forward = new Map(group.map(n => [n.id, []]));
      const incoming = new Map(group.map(n => [n.id, []]));
      function reaches(start, target) {
        const pending = [start], visited = new Set();
        while (pending.length) {
          const id = pending.pop(); if (id === target) return true;
          if (visited.has(id)) continue; visited.add(id); pending.push(...forward.get(id));
        }
        return false;
      }
      // Preserve supplied direction; feedback edges are routed later, never silently reversed.
      edges.filter(e => ids.has(e.from)).forEach(e => {
        if (reaches(e.to, e.from)) return;
        forward.get(e.from).push(e.to); incoming.get(e.to).push(e.from);
      });
      const indegree = new Map(group.map(n => [n.id, incoming.get(n.id).length]));
      const ready = group.filter(n => !indegree.get(n.id)), ordered = [];
      group.forEach(n => { n.rank = 0; });
      while (ready.length) {
        ready.sort((a, b) => a.order - b.order);
        const node = ready.shift(); ordered.push(node);
        forward.get(node.id).forEach(id => {
          const next = byId.get(id); next.rank = Math.max(next.rank, node.rank + 1);
          indegree.set(id, indegree.get(id) - 1); if (!indegree.get(id)) ready.push(next);
        });
      }
      // Place side inputs immediately before the step they feed, shortening long skip wires.
      [...ordered].reverse().forEach(n => {
        const targets = forward.get(n.id);
        if (targets.length) n.rank = Math.max(n.rank, Math.min(...targets.map(id => byId.get(id).rank)) - 1);
      });
      const layers = Array.from({ length: Math.max(...group.map(n => n.rank)) + 1 }, () => []);
      group.forEach(n => layers[n.rank].push(n));
      const position = new Map();
      function refresh() { layers.forEach(layer => layer.forEach((n, i) => position.set(n.id, i))); }
      refresh();
      // Alternating barycentre sweeps put related branches next to one another.
      for (let sweep = 0; sweep < 8; sweep++) {
        const indices = layers.map((_, i) => i); if (sweep % 2) indices.reverse();
        indices.forEach(rank => {
          const neighbours = sweep % 2 ? forward : incoming;
          const score = n => {
            const list = neighbours.get(n.id);
            return list.length ? list.reduce((sum, id) => sum + position.get(id), 0) / list.length : position.get(n.id);
          };
          layers[rank].sort((a, b) => score(a) - score(b) || a.order - b.order); refresh();
        });
      }
      const heights = layers.map(layer => layer.reduce((h, n) => h + n.height, 0) + Math.max(0, layer.length - 1) * ROW_GAP);
      const groupHeight = Math.max(...heights);
      layers.forEach((layer, rank) => {
        let y = offsetY + (groupHeight - heights[rank]) / 2;
        layer.forEach(n => { n.x = PAD + rank * (NODE_W + COLUMN_GAP); n.y = y; y += n.height + ROW_GAP; maxX = Math.max(maxX, n.x + n.width); });
      });
      offsetY += groupHeight + 74;
    });

    const width = maxX + PAD, height = offsetY - 74 + PAD;
    // Visibility grid: every segment lies outside node rectangles, including skip/feedback edges.
    const xs = [...new Set([10, width - 10, ...nodes.flatMap(n => [n.x - 18, n.x + n.width + 18])])].sort((a, b) => a - b);
    const ys = [...new Set([10, height - 10, ...nodes.flatMap(n => [n.y - 15, n.y + n.height / 2, n.y + n.height + 15])])].sort((a, b) => a - b);
    const nx = xs.length, ny = ys.length, occupied = new Map(), clearance = 7;
    function blocked(x1, y1, x2, y2) {
      return nodes.some(n => {
        const l = n.x - clearance, r = n.x + n.width + clearance, t = n.y - clearance, b = n.y + n.height + clearance;
        return x1 === x2 ? x1 > l && x1 < r && Math.max(y1, y2) > t && Math.min(y1, y2) < b
          : y1 > t && y1 < b && Math.max(x1, x2) > l && Math.min(x1, x2) < r;
      });
    }
    const neighbours = Array.from({ length: nx * ny }, () => []);
    for (let yi = 0; yi < ny; yi++) for (let xi = 0; xi < nx; xi++) {
      const id = yi * nx + xi;
      [[xi + 1, yi, 1], [xi, yi + 1, 2]].forEach(([xx, yy, direction]) => {
        if (xx >= nx || yy >= ny || blocked(xs[xi], ys[yi], xs[xx], ys[yy])) return;
        const next = yy * nx + xx, length = Math.abs(xs[xx] - xs[xi]) + Math.abs(ys[yy] - ys[yi]);
        neighbours[id].push({ next, length, direction }); neighbours[next].push({ next: id, length, direction });
      });
    }
    const keyFor = (a, b) => Math.min(a, b) + ':' + Math.max(a, b);
    function route(source, target) {
      const sy = source.y + source.height / 2, ty = target.y + target.height / 2;
      const start = ys.indexOf(sy) * nx + xs.indexOf(source.x + source.width + 18);
      const finish = ys.indexOf(ty) * nx + xs.indexOf(target.x - 18);
      const costs = new Map([[start * 3, 0]]), previous = new Map(), open = [{ state: start * 3, cost: 0, total: 0 }];
      let last;
      while (open.length) {
        open.sort((a, b) => b.total - a.total || b.state - a.state);
        const item = open.pop(), point = Math.floor(item.state / 3), oldDirection = item.state % 3;
        if (item.cost !== costs.get(item.state)) continue;
        if (point === finish) { last = item.state; break; }
        neighbours[point].forEach(({ next, length, direction }) => {
          const state = next * 3 + direction;
          const cost = item.cost + length + (oldDirection && oldDirection !== direction ? 20 : 0) + (occupied.get(keyFor(point, next)) || 0) * length * .16;
          if (cost >= (costs.get(state) ?? Infinity)) return;
          costs.set(state, cost); previous.set(state, item.state);
          const heuristic = Math.abs(xs[next % nx] - xs[finish % nx]) + Math.abs(ys[Math.floor(next / nx)] - ys[Math.floor(finish / nx)]);
          open.push({ state, cost, total: cost + heuristic });
        });
      }
      const path = [];
      if (last !== undefined) {
        for (let state = last; state !== undefined; state = previous.get(state)) path.push(Math.floor(state / 3));
        path.reverse(); path.slice(1).forEach((id, i) => { const key = keyFor(path[i], id); occupied.set(key, (occupied.get(key) || 0) + 1); });
      }
      const raw = [[source.x + source.width, sy], ...path.map(id => [xs[id % nx], ys[Math.floor(id / nx)]]), [target.x, ty]];
      const points = [];
      raw.forEach(p => {
        const a = points.at(-2), b = points.at(-1);
        if (b && p[0] === b[0] && p[1] === b[1]) return;
        if (a && ((a[0] === b[0] && b[0] === p[0]) || (a[1] === b[1] && b[1] === p[1]))) points.pop();
        points.push(p);
      });
      return points;
    }
    // Short local wires establish the main flow; remaining edges use free nearby corridors.
    const routed = edges.slice().sort((a, b) => {
      const distance = e => Math.abs(byId.get(e.to).x - byId.get(e.from).x) + Math.abs(byId.get(e.to).y - byId.get(e.from).y);
      return distance(a) - distance(b) || a.index - b.index;
    }).map(e => ({ index: e.index, points: route(byId.get(e.from), byId.get(e.to)) })).sort((a, b) => a.index - b.index);
    return { nodes: nodes.map(({ id, x, y, width, height, lines }) => ({ id, x, y, width, height, lines })), edges: routed, width, height };
  }
  global.ConceptLayout = { layout };
})(typeof window !== 'undefined' ? window : globalThis);
