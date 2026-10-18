import { test } from 'node:test';
import assert from 'node:assert/strict';
import { activeRequestFor } from '../src/lib/friendships.ts';

const request = (status, sender_id = 'user-a', recipient_id = 'user-b') => ({
  id: 'request-1', sender_id, recipient_id, status,
  created_at: '2026-10-17T14:00:00Z', responded_at: null,
});

test('pending and accepted relationships block duplicate UI actions in either direction', () => {
  for (const status of ['pending', 'accepted']) {
    for (const [sender, recipient] of [['user-a', 'user-b'], ['user-b', 'user-a']]) {
      const active = request(status, sender, recipient);
      assert.equal(activeRequestFor([active], 'user-a', 'user-b'), active);
    }
  }
});
test('declined history permits a new request but does not hide a later active relationship', () => {
  const declined = request('declined');
  assert.equal(activeRequestFor([declined], 'user-a', 'user-b'), undefined);
  const active = request('pending', 'user-b', 'user-a');
  assert.equal(activeRequestFor([declined, active], 'user-a', 'user-b'), active);
});
test('unrelated pairs and empty history do not match', () => {
  assert.equal(activeRequestFor([], 'user-a', 'user-b'), undefined);
  assert.equal(activeRequestFor([request('accepted')], 'user-a', 'user-c'), undefined);
});

test('removed friendship permits a new request and never masks a newer accepted record', () => {
  const removed = request('removed');
  assert.equal(activeRequestFor([removed], 'user-a', 'user-b'), undefined);
  const newer = { ...request('accepted', 'user-b', 'user-a'), id: 'new-request' };
  assert.equal(activeRequestFor([removed, newer], 'user-a', 'user-b'), newer);
});
