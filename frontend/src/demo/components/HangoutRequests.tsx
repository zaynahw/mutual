import React from 'react';
import { createHangout, createProposal, getCandidates, listHangouts } from '../lib/api';
import type { Activity, CandidateOption, Duration, HangoutRequest, Proposal, PublicUser, User } from '../lib/api';
import { isoToZonedInput, zonedInputToISO } from '../lib/time';

const activities: Activity[] = ['coffee', 'meal', 'walk', 'study', 'concert'];
const durations: Duration[] = [30, 60, 90, 120];

function CandidateChoice({ option, timezone, disabled, save }: {
  option: CandidateOption; timezone: string; disabled: boolean;
  save: (activity: Activity, start: string, duration: Duration) => void;
}) {
  const [activity, setActivity] = React.useState(option.eligible_activities[0]);
  const [duration, setDuration] = React.useState(option.eligible_durations[0]);
  const [start, setStart] = React.useState(isoToZonedInput(option.slot.start, timezone));
  return <form className="demo-choice demo-form" onSubmit={e => { e.preventDefault(); save(activity, start, duration); }}>
    <p className="w-full">Available {isoToZonedInput(option.slot.start, timezone)} – {isoToZonedInput(option.slot.end, timezone)}</p>
    <label>Activity<select value={activity} disabled={disabled} onChange={e => setActivity(e.target.value as Activity)}>{option.eligible_activities.map(a => <option key={a}>{a}</option>)}</select></label>
    <label>Exact start<input required type="datetime-local" value={start} disabled={disabled} onChange={e => setStart(e.target.value)} /></label>
    <label>Minutes<select value={duration} disabled={disabled} onChange={e => setDuration(Number(e.target.value) as Duration)}>{option.eligible_durations.map(d => <option key={d}>{d}</option>)}</select></label>
    <button disabled={disabled}>Save pending proposal</button>
  </form>;
}

export function HangoutRequests({ user, users }: { user: User; users: PublicUser[] }) {
  const [invitee, setInvitee] = React.useState(users.find(p => p.id !== user.id)?.id || '');
  const [start, setStart] = React.useState('2026-10-18T14:00');
  const [end, setEnd] = React.useState('2026-10-18T20:00');
  const [chosen, setChosen] = React.useState<Activity[]>(['coffee']);
  const [minutes, setMinutes] = React.useState<Duration[]>([30, 60]);
  const [location, setLocation] = React.useState('');
  const [requests, setRequests] = React.useState<HangoutRequest[]>([]);
  const [options, setOptions] = React.useState<{ requestId: string; items: CandidateOption[] } | null>(null);
  const [proposal, setProposal] = React.useState<Proposal | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const pending = React.useRef<AbortController | null>(null);
  React.useEffect(() => {
    const controller = new AbortController(); pending.current = controller;
    listHangouts(user.id, controller.signal).then(data => {
      if (!controller.signal.aborted) setRequests(data);
    }).catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load requests.'); });
    return () => { controller.abort(); pending.current?.abort(); };
  }, [user.id]);

  async function run(action: (signal: AbortSignal) => Promise<void>) {
    pending.current?.abort();
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setError('');
    try { await action(controller.signal); }
    catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Request failed.'); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const name = (id: string) => users.find(person => person.id === id)?.display_name || id;
  return <section className="demo-panel">
    <h2>Hangout requests and candidates</h2>
    <p>Times use {user.timezone}. This is manual testing; no agent is invoked. Candidates require permitted social windows and compatible constraints.</p>
    <form className="demo-form" onSubmit={e => {
      e.preventDefault();
      void run(async signal => {
        const created = await createHangout(user.id, {
          invitee_id: invitee, start: zonedInputToISO(start, user.timezone), end: zonedInputToISO(end, user.timezone),
          allowed_activities: chosen, allowed_durations: minutes, location: location.trim() || null,
        }, signal);
        if (!signal.aborted) { setRequests(old => [...old, created]); setOptions(null); setProposal(null); }
      });
    }}>
      <label>Invite<select value={invitee} disabled={busy} onChange={e => setInvitee(e.target.value)}>{users.filter(p => p.id !== user.id).map(p => <option key={p.id} value={p.id}>{p.display_name}</option>)}</select></label>
      <label>From<input required type="datetime-local" value={start} disabled={busy} onChange={e => setStart(e.target.value)} /></label>
      <label>Until<input required type="datetime-local" value={end} disabled={busy} onChange={e => setEnd(e.target.value)} /></label>
      <fieldset disabled={busy}><legend>Activities</legend>{activities.map(a => <label key={a}><input type="checkbox" checked={chosen.includes(a)} onChange={e => setChosen(old => e.target.checked ? [...old, a] : old.filter(v => v !== a))} />{a}</label>)}</fieldset>
      <fieldset disabled={busy}><legend>Durations (minutes)</legend>{durations.map(d => <label key={d}><input type="checkbox" checked={minutes.includes(d)} onChange={e => setMinutes(old => e.target.checked ? [...old, d] : old.filter(v => v !== d))} />{d}</label>)}</fieldset>
      <label>Location (optional)<input maxLength={200} value={location} disabled={busy} onChange={e => setLocation(e.target.value)} /></label>
      <button disabled={busy || !invitee || !chosen.length || !minutes.length}>Create request</button>
    </form>
    <button disabled={busy} onClick={() => void run(async signal => {
      const data = await listHangouts(user.id, signal);
      if (!signal.aborted) { setRequests(data); setOptions(null); setProposal(null); }
    })}>Refresh my requests</button>
    {busy && <p role="status">Working…</p>}
    {error && <p role="alert">{error}</p>}
    {requests.length === 0 && <p>No requests yet.</p>}
    {requests.map(request => <div className="demo-choice" key={request.id}>
      <h3>{name(request.requester_id)} → {name(request.invitee_id)}</h3>
      <p>{isoToZonedInput(request.start, user.timezone)} – {isoToZonedInput(request.end, user.timezone)}</p>
      <p>{request.allowed_activities.join(', ')} · {request.allowed_durations.join(', ')} minutes · {request.location || 'Location to be arranged'}</p>
      <p className="break-all text-sm">{request.id}</p>
      <button disabled={busy} onClick={() => {
        setOptions(null); setProposal(null);
        void run(async signal => {
          const data = await getCandidates(user.id, request.id, signal);
          if (!signal.aborted) setOptions({ requestId: request.id, items: data });
        });
      }}>Find valid times</button>
    </div>)}
    {options && <div className="space-y-3">
      <h3>Candidates for {options.requestId}</h3>
      {options.items.length === 0 && <p>No compatible times. Check windows, audiences, accepted friendships, activities, and calendars.</p>}
      {options.items.map((option, i) => <CandidateChoice key={`${options.requestId}-${i}-${option.slot.start}`} option={option} timezone={user.timezone} disabled={busy} save={(activity, wallStart, duration) => {
        setProposal(null);
        void run(async signal => {
          const exactStart = zonedInputToISO(wallStart, user.timezone);
          const exactEnd = new Date(Date.parse(exactStart) + duration * 60_000).toISOString();
          if (Date.parse(exactStart) < Date.parse(option.slot.start) || Date.parse(exactEnd) > Date.parse(option.slot.end)) throw new Error('The entire plan must fit inside this candidate interval.');
          const saved = await createProposal(user.id, options.requestId, { activity, slot: { start: exactStart, end: exactEnd } }, signal);
          if (!signal.aborted) setProposal(saved);
        });
      }} />)}
    </div>}
    {proposal && <div role="status" className="demo-choice">
      <h3>Saved pending proposal</h3>
      <p>{proposal.activity} · {isoToZonedInput(proposal.slot.start, user.timezone)} – {isoToZonedInput(proposal.slot.end, user.timezone)}</p>
      <p>Location: {proposal.location || 'To be arranged'}</p>
      <label>Copy this ID to view as either participant<input readOnly value={proposal.id} onFocus={e => e.target.select()} /></label>
      <p>Availability was rechecked before saving. This does not reserve the time or create an event.</p>
    </div>}
  </section>;
}
