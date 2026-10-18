import test from 'node:test';
import assert from 'node:assert/strict';
import { visibleProposals } from '../src/lib/proposals.ts';

const plan = (id, status) => ({ id, status });
test('declined options disappear while active alternatives remain', () => {
  const plans = [plan('a', 'declined'), plan('b', 'pending')];
  assert.deepEqual(visibleProposals(plans), [plans[1]]);
  assert.equal(plans.length, 2);
  assert.deepEqual(visibleProposals([plans[0]]), []);
});
test('an agreed or scheduled plan hides all competing options regardless of order', () => {
  for (const status of ['approved', 'scheduled']) {
    const agreed = plan('chosen', status);
    assert.deepEqual(visibleProposals([plan('pending', 'pending'), plan('old', 'declined'), agreed]), [agreed]);
  }
  assert.deepEqual(visibleProposals([]), []);
});

test('cancelled options stay hidden and status follows the current user', async () => {
  const { planStatus } = await import('../src/lib/proposals.ts');
  assert.deepEqual(visibleProposals([plan('closed','cancelled')]), []);
  const response = {proposal:plan('pending','pending'),approvals:[{user_id:'a',decision:'approve'}]};
  assert.equal(planStatus([response], 'a'), 'Waiting for response');
  assert.equal(planStatus([response], 'b'), 'Your response needed');
  assert.equal(planStatus([{...response,proposal:plan('approved','approved')}], 'a'), 'Ready to schedule');
  assert.equal(planStatus([{...response,proposal:plan('done','scheduled')}], 'a'), 'Scheduled');
  assert.equal(planStatus([], 'a'), 'Choose a time');
});

test('legacy identical plans render once without combining decisions or mutating history', () => {
  const first = {...plan('a','pending'),activity:'walk',location:null,
    slot:{start:'2026-10-23T14:00:00Z',end:'2026-10-23T14:30:00Z'}};
  const duplicate = {...first,id:'b',slot:{start:'2026-10-23T10:00:00-04:00',end:'2026-10-23T10:30:00-04:00'}};
  const later = {...first,id:'c',slot:{start:'2026-10-23T14:30:00Z',end:'2026-10-23T15:00:00Z'}};
  assert.deepEqual(visibleProposals([first,duplicate,later]),[first,later]);
  assert.deepEqual(visibleProposals([first,{...duplicate,status:'approved'}]),[{...duplicate,status:'approved'}]);
  assert.equal(duplicate.id,'b');
});
