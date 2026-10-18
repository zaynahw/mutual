import type { Proposal } from './api';

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
