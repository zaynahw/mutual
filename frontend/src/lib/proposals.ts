import type { Proposal } from './api';

/** Keep stored history, but show only the unresolved options or agreed plan. */
export function visibleProposals(proposals: Proposal[]): Proposal[] {
  const agreed = proposals.find(plan => plan.status === 'approved' || plan.status === 'scheduled');
  return agreed ? [agreed] : proposals.filter(plan => plan.status !== 'declined' && plan.status !== 'cancelled');
}


export function planStatus(responses: import('./api').ProposalResponse[], userId: string): string {
  const visible = visibleProposals(responses.map(item => item.proposal));
  if (visible.some(item => item.status === 'scheduled')) return 'Scheduled';
  if (visible.some(item => item.status === 'approved')) return 'Ready to schedule';
  if (!visible.length) return 'Choose a time';
  const waiting = visible.every(item => responses.find(response => response.proposal.id === item.id)?.approvals.some(approval => approval.user_id === userId));
  return waiting ? 'Waiting for response' : 'Your response needed';
}
