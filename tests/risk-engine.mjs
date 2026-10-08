import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const scope = { window: {} };
vm.createContext(scope);
vm.runInContext(readFileSync('js/risk-engine.js', 'utf8'), scope);
const engine = scope.window.RiskEngine;
const cases = JSON.parse(readFileSync('tests/risk-cases.json', 'utf8'));
for (const test of cases) {
  const result = engine.assess(test.detections, { frame_width: test.width });
  assert.equal(result.level, test.level, test.name);
  assert.equal(result.pairs.length, test.pairs, test.name);
  if (test.reference_gap != null)
    assert.equal(result.pairs[0].gap_reference_pixels, test.reference_gap, test.name);
}
for (const width of [0, -1, NaN, Infinity, '640'])
  assert.throws(() => engine.assess([], { frame_width: width }));
console.log(`PASS: ${cases.length} risk cases; invalid dimensions rejected`);
