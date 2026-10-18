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

test('plan attention distinguishes incoming joins, waiting, scheduling and closed plans', async () => {
  const {planAttention}=await import('../src/lib/proposals.ts');
  const item={request:{id:'request',requester_id:'a',invitee_id:'b',join_window_id:'window'},proposals:[{
    proposal:{...plan('p','pending'),activity:'coffee',slot:{start:'2026-10-23T14:00:00Z',end:'2026-10-23T14:30:00Z'}},approvals:[],
  }]};
  assert.equal(planAttention(item,'b').label,'Join request · respond');
  item.proposals[0].approvals.push({user_id:'a',decision:'approve'});
  assert.equal(planAttention(item,'a').kind,'waiting');
  assert.equal(planAttention(item,'b').action,true);
  item.proposals[0].proposal.status='approved';
  assert.equal(planAttention(item,'a').kind,'schedule');
  item.proposals[0].proposal.status='scheduled';
  assert.equal(planAttention(item,'a').action,false);
  item.proposals[0].proposal.status='declined';
  assert.equal(planAttention(item,'b').kind,'closed');
  item.proposals=[];
  assert.equal(planAttention(item,'b').kind,'find');
});

test('activity fingerprints detect decisions and new options, but ignore response ordering', async () => {
  const {planFingerprint}=await import('../src/lib/proposals.ts');
  const item={request:{id:'r'},proposals:[{proposal:plan('a','pending'),approvals:[]},{proposal:plan('b','pending'),approvals:[]}]};
  const initial=planFingerprint(item);
  assert.equal(planFingerprint({...item,proposals:[...item.proposals].reverse()}),initial);
  item.proposals[0].approvals.push({user_id:'friend',decision:'approve',decided_at:'now'});
  assert.notEqual(planFingerprint(item),initial);
  const decided=planFingerprint(item);
  item.proposals[0].proposal.status='approved';
  assert.notEqual(planFingerprint(item),decided);
});
