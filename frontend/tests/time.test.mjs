import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isoToZonedInput, zonedInputToISO } from '../src/demo/lib/time.ts';

test('New York input uses profile timezone', () => {
  assert.equal(zonedInputToISO('2026-10-18T14:00', 'America/New_York'), '2026-10-18T18:00:00.000Z');
});
test('winter and fractional offsets', () => {
  assert.equal(zonedInputToISO('2026-01-18T14:00', 'America/New_York'), '2026-01-18T19:00:00.000Z');
  assert.equal(zonedInputToISO('2026-10-18T14:00', 'Asia/Kolkata'), '2026-10-18T08:30:00.000Z');
});
test('DST gap rejected', () => {
  assert.throws(() => zonedInputToISO('2026-03-08T02:30', 'America/New_York'), /does not exist/);
});
test('DST repeated time rejected', () => {
  assert.throws(() => zonedInputToISO('2026-11-01T01:30', 'America/New_York'), /occurs twice/);
});
test('invalid dates and incomplete inputs rejected', () => {
  for (const value of ['', '2026-02-30T14:00', '2026-10-18']) {
    assert.throws(() => zonedInputToISO(value, 'America/New_York'));
  }
});

test('edit form round-trips in the owner timezone', () => {
  const input = isoToZonedInput('2026-10-18T18:00:00Z', 'America/New_York');
  assert.equal(input, '2026-10-18T14:00');
  assert.equal(zonedInputToISO(input, 'America/New_York'), '2026-10-18T18:00:00.000Z');
});
