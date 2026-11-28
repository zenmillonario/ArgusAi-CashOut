import test from 'node:test';
import assert from 'node:assert/strict';
import { targetDistance } from './targetDistance.mjs';
test('signed price-to-beat distance uses observed underlying minus target', () => {
  assert.deepEqual(targetDistance(63025.12,63000), {direction:'above',label:'+$25.12'});
  assert.deepEqual(targetDistance(62981.50,63000), {direction:'below',label:'−$18.50'});
  assert.deepEqual(targetDistance(63000,63000), {direction:'at',label:'$0.00'});
});
test('sub-dollar assets keep small distances visible', () => {
  assert.deepEqual(targetDistance(.12345,.123), {direction:'above',label:'+$0.000450'});
  assert.deepEqual(targetDistance(.123,.12345), {direction:'below',label:'−$0.000450'});
  assert.deepEqual(targetDistance(.12300001,.123), {direction:'above',label:'+<$0.000001'});
});
test('unknown or invalid price inputs do not invent a distance', () => {
  for (const values of [[null,1],[1,undefined],[NaN,1],[1,0],['1',1],[Infinity,1]])
    assert.deepEqual(targetDistance(...values), {direction:'unknown',label:'—'});
});
