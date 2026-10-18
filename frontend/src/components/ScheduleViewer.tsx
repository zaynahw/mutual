import React from 'react';
import { getSchedule } from '../lib/api';
import type { PublicUser, ScheduleResponse, User } from '../lib/api';
import { zonedInputToISO } from '../lib/time';

export function ScheduleViewer({ user, users }: { user: User; users: PublicUser[] }) {
  const [owner, setOwner] = React.useState(user.id);
  const [start, setStart] = React.useState('2026-10-18T09:00');
  const [end, setEnd] = React.useState('2026-10-18T23:00');
  const [result, setResult] = React.useState<ScheduleResponse | null>(null);
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const pending = React.useRef<AbortController | null>(null);
  React.useEffect(() => () => pending.current?.abort(), []);
  const format = (value: string) => new Date(value).toLocaleString(undefined, { timeZone: user.timezone });
  async function load(event: React.FormEvent) {
    event.preventDefault();
    const controller = new AbortController();
    pending.current?.abort(); pending.current = controller;
    setBusy(true); setError(''); setResult(null);
    try {
      const data = await getSchedule(user.id, owner, {
        start: zonedInputToISO(start, user.timezone), end: zonedInputToISO(end, user.timezone),
      }, controller.signal);
      if (!controller.signal.aborted) setResult(data);
    } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load schedule.'); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className="demo-panel">
    <h2>View a schedule</h2>
    <p>Acting as {user.display_name}. Times use {user.timezone}. Calendar blocks are simulated.</p>
    <form onSubmit={load} className="demo-form">
      <label>Whose schedule?<select value={owner} onChange={e => { setOwner(e.target.value); setResult(null); }} disabled={busy}>
        {users.map(person => <option key={person.id} value={person.id}>{person.display_name}</option>)}
      </select></label>
      <label>From<input required type="datetime-local" value={start} onChange={e => { setStart(e.target.value); setResult(null); }} disabled={busy} /></label>
      <label>Until<input required type="datetime-local" value={end} onChange={e => { setEnd(e.target.value); setResult(null); }} disabled={busy} /></label>
      <button disabled={busy}>{busy ? 'Loading…' : 'Load permitted schedule'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {result && <div className="space-y-3">
      <h3>{result.user.display_name}: visible social windows</h3>
      {result.social_windows.length === 0 && <p>No visible windows in this range. Hidden windows are not disclosed.</p>}
      {result.social_windows.map(window => <p key={window.id}>{format(window.start)} – {format(window.end)} · {window.allowed_activities.join(', ')}</p>)}
      <h3>Calendar busy blocks</h3>
      {result.calendar_busy === null ? <p>Calendar is not shared with you.</p> : result.calendar_busy.length === 0 ? <p>Calendar is shared; no busy blocks in this range.</p> : result.calendar_busy.map((interval, i) => <p key={i}>{format(interval.start)} – {format(interval.end)}</p>)}
    </div>}
  </section>;
}
