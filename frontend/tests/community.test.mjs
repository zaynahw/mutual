import test from 'node:test';
import assert from 'node:assert/strict';
import {connectionKind,layoutCommunityDay} from '../src/lib/community.ts';

const card=(id,owner,start,end)=>({owner:{id:owner},window:{id,start,end,allowed_activities:['walk']},audience:'community'});
test('friend labels take precedence over community audience, while own windows remain separate',()=>{
  assert.equal(connectionKind(card('a','friend','',''),'me',new Set(['friend'])),'friend');
  assert.equal(connectionKind(card('a','member','',''),'me',new Set(['friend'])),'community');
  assert.equal(connectionKind(card('a','me','',''),'me',new Set()),'own');
});
test('overlapping community windows get separate lanes; adjacent windows reuse full width',()=>{
  const items=[card('a','one','2026-10-19T14:00:00Z','2026-10-19T15:00:00Z'),card('b','two','2026-10-19T14:30:00Z','2026-10-19T15:30:00Z'),card('c','three','2026-10-19T15:30:00Z','2026-10-19T16:00:00Z')];
  const layout=layoutCommunityDay(items,'2026-10-19','America/New_York');
  assert.equal(layout.length,3);
  assert.notEqual(layout[0].lane,layout[1].lane);
  assert.equal(layout[0].lanes,2);assert.equal(layout[1].lanes,2);
  assert.equal(layout[2].lanes,1);
  assert.deepEqual(layoutCommunityDay(items,'2026-10-20','America/New_York'),[]);
});
