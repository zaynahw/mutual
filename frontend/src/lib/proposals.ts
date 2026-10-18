import type { Proposal, HangoutOverview } from './api';

/** Keep stored history, but show only the unresolved options or agreed plan. */
export function visibleProposals(proposals: Proposal[]): Proposal[] {
  const agreed = proposals.find(plan => plan.status === 'approved' || plan.status === 'scheduled');
  if (agreed) return [agreed];
  const seen = new Set<string>();
  return proposals.filter(plan => {
    if (plan.status === 'declined' || plan.status === 'cancelled') return false;
    // Legacy duplicate records keep their own approvals; display one stable ID.
    const key = plan.slot ? JSON.stringify([plan.activity, Date.parse(plan.slot.start), Date.parse(plan.slot.end), plan.location || '']) : plan.id;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}


export function planStatus(responses: import('./api').ProposalResponse[], userId: string): string {
  const visible = visibleProposals(responses.map(item => item.proposal));
  if (visible.some(item => item.status === 'scheduled')) return 'Scheduled';
  if (visible.some(item => item.status === 'approved')) return 'Ready to schedule';
  if (!visible.length) return 'Choose a time';
  const waiting = visible.every(item => responses.find(response => response.proposal.id === item.id)?.approvals.some(approval => approval.user_id === userId));
  return waiting ? 'Waiting for response' : 'Your response needed';
}

export function planFingerprint(item:HangoutOverview):string {
  return JSON.stringify([item.request.id,item.proposals.map(r=>[r.proposal.id,r.proposal.status,
    r.approvals.map(a=>[a.user_id,a.decision,a.decided_at]).sort((a,b)=>String(a[0]).localeCompare(String(b[0])))])
    .sort((a,b)=>String(a[0]).localeCompare(String(b[0])))]);
}
export function planAttention(item:HangoutOverview,userId:string) {
  const plans=visibleProposals(item.proposals.map(r=>r.proposal));
  if(plans.some(p=>p.status==='scheduled'))return {kind:'closed',label:'Scheduled',priority:5,action:false};
  if(plans.some(p=>p.status==='approved'))return {kind:'schedule',label:'Both approved · add to calendar',priority:0,action:true};
  const pending=plans.filter(p=>p.status==='pending');
  if(pending.some(p=>!item.proposals.find(r=>r.proposal.id===p.id)?.approvals.some(a=>a.user_id===userId))){
    return {kind:'respond',label:item.request.invitee_id===userId&&item.request.join_window_id?'Join request · respond':'Your approval needed',priority:1,action:true};
  }
  if(pending.length)return {kind:'waiting',label:'Waiting for their response',priority:4,action:false};
  if(item.proposals.length)return {kind:'closed',label:'Closed options · review history',priority:6,action:false};
  return {kind:'find',label:item.request.invitee_id===userId?'Invitation received · find a plan':'Find a time for this request',priority:2,action:true};
}
export function readSeenPlans(userId:string):Record<string,string> {
  try {const data=JSON.parse(sessionStorage.getItem(`mutual:seen-plans:${userId}`)||'{}');
    return data&&typeof data==='object'&&!Array.isArray(data)?Object.fromEntries(Object.entries(data).filter(([,v])=>typeof v==='string')) as Record<string,string>:{};
  }catch{return {};}
}
