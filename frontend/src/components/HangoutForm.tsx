import React from 'react';
import type { Activity, Duration, HangoutInput, PublicUser, User } from '../lib/api';
import { createHangout } from '../lib/api';
import { zonedInputToISO } from '../lib/time';

export interface HangoutDraft {
  invitee: string; start: string; end: string; activities: Activity[]; durations: Duration[]; location: string;
}
export function HangoutForm({ user, users, draft, setDraft, onSaved, onBack }: {
  user: User; users: PublicUser[]; draft: HangoutDraft;
  setDraft: React.Dispatch<React.SetStateAction<HangoutDraft>>;
  onSaved: (request: import('../lib/api').HangoutRequest) => void; onBack: () => void;
}) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const pending = React.useRef<AbortController | null>(null);
  React.useEffect(() => () => pending.current?.abort(), []);
  const patch = (value: Partial<HangoutDraft>) => setDraft(old => ({ ...old, ...value }));
  return <section className="demo-panel">
    <button className="demo-secondary" disabled={busy} onClick={onBack}>Back to my plans</button>
    <h2>Plan a hangout</h2>
    <p>Choose a person and a search range. Times use {user.timezone}. Sample availability is on October 18, 2026.</p>
    <form className="demo-form" onSubmit={e => {
      e.preventDefault(); if (busy) return;
      const controller = new AbortController(); pending.current = controller;
      setError(''); setBusy(true);
      void (async () => {
        try {
          const body: HangoutInput = {
            invitee_id: draft.invitee, start: zonedInputToISO(draft.start, user.timezone), end: zonedInputToISO(draft.end, user.timezone),
            allowed_activities: [...draft.activities].sort(), allowed_durations: [...draft.durations].sort((a,b) => a-b), location: draft.location.trim() || null,
          };
          if (Date.parse(body.end) <= Date.parse(body.start)) throw new Error('End must be after start.');
          if ((Date.parse(body.end) - Date.parse(body.start)) / 60_000 < Math.min(...draft.durations)) throw new Error('Choose a search range long enough for at least one selected duration.');
          const saved = await createHangout(user.id, body, controller.signal);
          if (!controller.signal.aborted) onSaved(saved);
        } catch (error) {
          if (!controller.signal.aborted) setError(error instanceof TypeError ? 'Connection lost. Refresh plans before retrying; the same input can be retried safely.' : error instanceof Error ? error.message : 'Could not create request.');
        } finally { if (!controller.signal.aborted) setBusy(false); }
      })();
    }}>
      <fieldset disabled={busy} className="demo-form w-full">
        <label>Invite<select value={draft.invitee} onChange={e => patch({invitee:e.target.value})}>{users.filter(person => person.id !== user.id).map(person => <option key={person.id} value={person.id}>{person.display_name}</option>)}</select></label>
        <label>From<input required type="datetime-local" value={draft.start} onChange={e => patch({start:e.target.value})} /></label>
        <label>Until<input required type="datetime-local" value={draft.end} onChange={e => patch({end:e.target.value})} /></label>
        <fieldset><legend>Possible activities</legend>{(['coffee','meal','walk','study','concert'] as Activity[]).map(activity => <label key={activity}><input type="checkbox" checked={draft.activities.includes(activity)} onChange={e => patch({activities: e.target.checked ? [...draft.activities,activity] : draft.activities.filter(a => a !== activity)})} />{activity}</label>)}</fieldset>
        <fieldset><legend>Possible durations (minutes)</legend>{([30,60,90,120] as Duration[]).map(duration => <label key={duration}><input type="checkbox" checked={draft.durations.includes(duration)} onChange={e => patch({durations:e.target.checked ? [...draft.durations,duration] : draft.durations.filter(d => d !== duration)})} />{duration}</label>)}</fieldset>
        <label>Location (optional)<input maxLength={200} value={draft.location} onChange={e => patch({location:e.target.value})} /></label>
        <button disabled={!draft.invitee || !draft.activities.length || !draft.durations.length}>Find times for this request</button>
      </fieldset>
    </form>
    {busy && <p role="status">Saving your request…</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
