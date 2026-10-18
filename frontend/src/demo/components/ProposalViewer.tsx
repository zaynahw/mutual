import React from 'react';
import { getProposal } from '../lib/api';
import type { ProposalResponse, User } from '../lib/api';

export function ProposalViewer({ user }: { user: User }) {
  const [id, setId] = React.useState('');
  const [result, setResult] = React.useState<ProposalResponse | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const pending = React.useRef<AbortController | null>(null);
  React.useEffect(() => () => pending.current?.abort(), []);
  async function load(event: React.FormEvent) {
    event.preventDefault();
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setResult(null); setError('');
    try {
      const data = await getProposal(user.id, id.trim(), controller.signal);
      if (!controller.signal.aborted) setResult(data);
    } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load proposal.'); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className="demo-panel">
    <h2>View a saved proposal</h2>
    <p>Copy a saved proposal ID, switch demo users, then load it as the other participant.</p>
    <form className="demo-form" onSubmit={load}>
      <label>Proposal ID<input required value={id} disabled={busy} onChange={e => { setId(e.target.value); setResult(null); }} /></label>
      <button disabled={busy}>{busy ? 'Loading…' : 'Load proposal'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {result && <div>
      <p>{result.proposal.activity} · {result.proposal.status}</p>
      <p>{new Date(result.proposal.slot.start).toLocaleString(undefined, { timeZone: user.timezone })} – {new Date(result.proposal.slot.end).toLocaleString(undefined, { timeZone: user.timezone })} ({user.timezone})</p>
      <p>Location: {result.proposal.location || 'To be arranged'}</p>
      <p>Recorded decisions: {result.approvals.length}. Approval actions are not implemented yet.</p>
    </div>}
  </section>;
}
