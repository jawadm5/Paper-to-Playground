/* Local, dependency-free regression checks for topology and obstacle routing. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
require('../playground_v2/assets/concept-layout.js');

function check(concepts, relationships) {
  const graph = ConceptLayout.layout(concepts, relationships);
  assert.deepEqual(graph, ConceptLayout.layout(concepts, relationships), 'layout must be stable');
  assert.equal(graph.nodes.length, concepts.length);
  assert.equal(graph.edges.length, relationships.length);
  const byId = new Map(graph.nodes.map(n => [n.id, n]));
  for (const n of graph.nodes) {
    assert.ok(n.x >= 0 && n.y >= 0 && n.x + n.width <= graph.width && n.y + n.height <= graph.height);
    assert.ok(n.lines.length && n.lines.every(Boolean), 'every node keeps its label');
    for (const other of graph.nodes) if (n.id !== other.id) {
      assert.ok(n.x + n.width <= other.x || other.x + other.width <= n.x || n.y + n.height <= other.y || other.y + other.height <= n.y, 'nodes must not overlap');
    }
  }
  for (const edge of graph.edges) {
    const relation = relationships[edge.index], source = byId.get(relation.from), target = byId.get(relation.to);
    assert.deepEqual(edge.points[0], [source.x + source.width, source.y + source.height / 2], 'start at source output');
    assert.deepEqual(edge.points.at(-1), [target.x, target.y + target.height / 2], 'end at target input');
    for (let i = 1; i < edge.points.length; i++) {
      const a = edge.points[i - 1], b = edge.points[i];
      assert.ok(a[0] === b[0] || a[1] === b[1], 'routes must be orthogonal');
      for (const node of graph.nodes) {
        if (node.id === relation.from || node.id === relation.to) continue;
        const crosses = a[0] === b[0]
          ? a[0] > node.x && a[0] < node.x + node.width && Math.max(a[1], b[1]) > node.y && Math.min(a[1], b[1]) < node.y + node.height
          : a[1] > node.y && a[1] < node.y + node.height && Math.max(a[0], b[0]) > node.x && Math.min(a[0], b[0]) < node.x + node.width;
        assert.ok(!crosses, `edge ${edge.index} must not cross ${node.id}`);
      }
    }
  }
  return graph;
}

assert.deepEqual(ConceptLayout.layout([], []), { nodes: [], edges: [], width: 600, height: 400 });
const concepts = ['start', 'branch-a', 'branch-b', 'merge', 'isolated'].map(id => ({ id, name: id }));
check(concepts, [
  { from: 'start', to: 'branch-a' }, { from: 'start', to: 'branch-b' },
  { from: 'branch-a', to: 'merge' }, { from: 'branch-b', to: 'merge' },
  { from: 'merge', to: 'start' }, { from: 'branch-b', to: 'branch-b' },
]);
for (const name of ['attention', 'entropy']) {
  const filename = path.join(__dirname, '..', 'out', `${name}-current`, 'paper_content.json');
  if (!fs.existsSync(filename)) continue;
  const { content } = JSON.parse(fs.readFileSync(filename, 'utf8'));
  const graph = check(content.concepts, content.relationships);
  assert.ok(graph.width <= 1500 && graph.height <= 650, 'sample map must remain compact');
  console.log(`${name}: ${graph.nodes.length} nodes, ${graph.edges.length} edges; ${graph.width} x ${graph.height}`);
}
console.log('Concept layout checks passed: determinism, bounds, labels, branches, cycles, self-links, disconnected nodes, directions, and obstacle avoidance.');
