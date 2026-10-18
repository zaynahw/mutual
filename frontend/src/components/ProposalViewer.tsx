import React from 'react';
import { decideProposal, replanProposal, scheduleProposal, getProposal } from '../lib/api';
import type { ProposalResponse, PublicUser, User } from '../lib/api';
import { dateTime } from '../lib/display';

export function ProposalViewer({ user, users, value, onChange, onRefresh, calendarMode='mock', calendarConnected=true }: {
  calendarMode?:'mock'|'google'; calendarConnected?:boolean;
  user: User; users: PublicUser[]; value: ProposalResponse;
  onChange: (result: ProposalResponse) => void; onRefresh: () => void;
}) {
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [confirmReplan, setConfirmReplan] = React.useState(false);
  const eventKey = React.useRef(crypto.randomUUID());
  const pending = React.useRef<AbortController | null>(null);
  React.useEffect(() => () => pending.current?.abort(), []);
  const result = value;
  async function act(action: (signal: AbortSignal) => Promise<ProposalResponse>) {
    if (pending.current) return;
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setError('');
    try {
      const data = await action(controller.signal);
      if (!controller.signal.aborted) onChange(data);
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof TypeError ? 'Connection lost. Refresh this plan to check whether your action completed before trying again.' : e instanceof Error ? e.message : 'Could not update plan. Refresh and retry.');
    } finally { if (!controller.signal.aborted) { pending.current = null; setBusy(false); } }
  }
  const mine = result.approvals.find(item => item.user_id === user.id);
  const canDecide = result.proposal.status === 'pending' && !mine;
  const name = (id: string) => users.find(person => person.id === id)?.display_name || id;
  return <section className="space-y-4 rounded-xl border border-teal-200 bg-teal-50 p-5" aria-label="Review proposal">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3>Review this plan</h3>
      <button className="demo-secondary" disabled={busy} onClick={onRefresh}>Refresh this plan</button>
    </div>
    {busy && <p role="status">Saving…</p>}
    {error && <p role="alert">{error}</p>}
    <p className="text-sm font-medium">Source: {{manual:'Manually proposed',local_agent:'Local AI negotiation',demo_fallback:'Deterministic fallback',mock:'Mock negotiation — no AI inference'}[result.proposal.source]}</p>
    <p className="text-xl font-semibold capitalize">{result.proposal.activity}</p>
    <p>{dateTime(result.proposal.slot.start, user.timezone)} – {dateTime(result.proposal.slot.end, user.timezone)}</p>
    <p>Location: {result.proposal.location || 'To be arranged'}</p>
    <p className="font-medium">{result.proposal.status === 'approved' ? `Both approved — ready to add to ${calendarMode==='google'?'Google Calendar':'the demo calendar'}.` : result.proposal.status === 'scheduled' ? `Scheduled in ${calendarMode==='google'?'Google Calendar':'the demo calendar'}.` : result.proposal.status === 'cancelled' ? 'Closed for replanning.' : result.proposal.status === 'declined' ? 'Declined.' : mine ? 'You approved. Waiting for the other person.' : 'Your response is needed.'}</p>
    <ul>{result.approvals.map(item => <li key={item.user_id}>{name(item.user_id)}: {item.decision === 'approve' ? 'Approved' : 'Declined'}</li>)}</ul>
    {canDecide && <div className="flex gap-3">
      <button disabled={busy} onClick={() => void act(signal => decideProposal(user.id, result.proposal.id, 'approve', signal))}>Approve this plan</button>
      <button className="demo-secondary" disabled={busy} onClick={() => void act(signal => decideProposal(user.id, result.proposal.id, 'decline', signal))}>Decline</button>
    </div>}
    {result.proposal.status === 'approved' && <div className="space-y-3">
      <button disabled={busy || !calendarConnected} onClick={() => void act(async signal => {
        await scheduleProposal(user.id, result.proposal.id, eventKey.current, signal);
        return getProposal(user.id, result.proposal.id, signal);
      })}>{calendarMode==='google'?'Add to Google Calendar':'Add to demo calendar'}</button>{!calendarConnected && <p>Connect your Google Calendar before scheduling.</p>}
      <p className="text-sm">If availability changed, replan to choose a new time with fresh approvals.</p>
      <button className="demo-secondary" disabled={busy} onClick={() => setConfirmReplan(true)}>Replan this hangout</button>
      {confirmReplan && <div className="demo-choice space-y-3">
        <p>Close this proposal and its alternatives? Past decisions are kept. A new proposal will need fresh approval.</p>
        <button disabled={busy} onClick={() => void act(signal => replanProposal(user.id, result.proposal.id, signal))}>Close options and replan</button>
        <button className="demo-secondary ml-2" disabled={busy} onClick={() => setConfirmReplan(false)}>Keep this plan</button>
      </div>}
    </div>}
    <p className="text-sm text-stone-600">Decisions are final for each proposal. {calendarMode==='google'?'Scheduling sends a Google Calendar invitation to the other participant.':'Calendar creation is simulated; Google is not connected here.'}</p>
  </section>;
}
