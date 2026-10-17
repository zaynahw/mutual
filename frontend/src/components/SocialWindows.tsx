import React from 'react';
import { createMyWindow, deleteMyWindow, listMyWindows, updateMyWindow } from '../lib/api';
import type { Activity, SocialWindow, SocialWindowInput, User } from '../lib/api';
import { isoToZonedInput, zonedInputToISO } from '../lib/time';

const activities: Activity[] = ['coffee', 'meal', 'walk', 'study', 'concert'];

export function SocialWindows({ user }: { user: User }) {
  const [windows, setWindows] = React.useState<SocialWindow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [listError, setListError] = React.useState('');
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [start, setStart] = React.useState('');
  const [end, setEnd] = React.useState('');
  const [chosen, setChosen] = React.useState<Activity[]>([]);
  const [audience, setAudience] = React.useState<SocialWindowInput['visibility']['audience']>('private');
  const [mode, setMode] = React.useState<SocialWindowInput['sharing_mode']>('visible');
  const [reload, setReload] = React.useState(0);
  const pendingSave = React.useRef<AbortController | null>(null);

  React.useEffect(() => () => pendingSave.current?.abort(), []);
  React.useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setListError('');
    listMyWindows(user.id, controller.signal).then(data => {
      if (!controller.signal.aborted) setWindows(data);
    }).catch(() => {
      if (!controller.signal.aborted) setListError('Could not load windows. Check the backend and retry.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [user.id, reload]);

  function resetForm() {
    setEditingId(null); setStart(''); setEnd(''); setChosen([]); setAudience('private'); setMode('visible');
  }

  function beginEdit(window: SocialWindow) {
    setEditingId(window.id); setStart(isoToZonedInput(window.start, user.timezone));
    setEnd(isoToZonedInput(window.end, user.timezone)); setChosen([...window.allowed_activities]);
    setAudience(window.visibility.audience); setMode(window.sharing_mode);
    setError(''); setNotice(''); setConfirmDeleteId(null);
  }

  async function removeWindow(windowId: string) {
    if (saving) return;
    const controller = new AbortController(); pendingSave.current = controller;
    setSaving(true); setError(''); setNotice('');
    try {
      await deleteMyWindow(user.id, windowId, controller.signal);
      if (!controller.signal.aborted) {
        if (editingId === windowId) resetForm();
        setConfirmDeleteId(null); setNotice('Social window deleted.'); setReload(value => value + 1);
      }
    } catch (caught) {
      if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Could not delete window.');
    } finally { if (!controller.signal.aborted) setSaving(false); }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (saving) return;
    setError(''); setNotice('');
    const controller = new AbortController();
    pendingSave.current = controller;
    try {
      if (chosen.length === 0) throw new Error('Choose at least one activity.');
      const startISO = zonedInputToISO(start, user.timezone);
      const endISO = zonedInputToISO(end, user.timezone);
      if (Date.parse(endISO) <= Date.parse(startISO)) throw new Error('End must be after start.');
      setSaving(true);
      const input: SocialWindowInput = {
        start: startISO, end: endISO, allowed_activities: chosen,
        visibility: { audience, selected_friend_ids: [] }, sharing_mode: mode,
      };
      if (editingId) await updateMyWindow(user.id, editingId, input, controller.signal);
      else await createMyWindow(user.id, input, controller.signal);
      if (!controller.signal.aborted) {
        resetForm();
        setNotice(editingId ? 'Social window updated.' : 'Social window saved.'); setReload(value => value + 1);
      }
    } catch (caught) {
      if (!controller.signal.aborted) setError(caught instanceof TypeError ? 'Could not reach the backend. Check the saved list before retrying.' : caught instanceof Error ? caught.message : 'Could not save window.');
    } finally { if (!controller.signal.aborted) setSaving(false); }
  }

  const displayTime = (value: string) => new Intl.DateTimeFormat(undefined, {
    timeZone: user.timezone, dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(value));

  return <section className="space-y-6 rounded-xl border border-stone-200 bg-white p-6" aria-label="My social availability">
    <div><h2 className="text-2xl font-semibold">My social availability</h2>
      <p className="mt-2 text-sm text-stone-600">Your saved windows, including private ones. All times below use {user.timezone}. Calendar conflicts will be checked later during matching.</p></div>
    <div className="grid gap-8 md:grid-cols-2">
      <form onSubmit={submit} className="space-y-4">
        <h3 className="text-lg font-medium">{editingId ? 'Edit window' : 'Add a window'}</h3>
        <fieldset disabled={saving} className="space-y-4">
          <label className="block">Start<input type="datetime-local" required value={start} onChange={event => setStart(event.target.value)} className="mt-1 block w-full rounded border border-stone-300 p-2" /></label>
          <label className="block">End<input type="datetime-local" required value={end} onChange={event => setEnd(event.target.value)} className="mt-1 block w-full rounded border border-stone-300 p-2" /></label>
          <fieldset><legend className="mb-2">Activities</legend><div className="flex flex-wrap gap-4">{activities.map(activity => <label key={activity} className="flex items-center gap-2"><input type="checkbox" checked={chosen.includes(activity)} onChange={event => setChosen(values => event.target.checked ? [...values, activity] : values.filter(value => value !== activity))} />{activity}</label>)}</div></fieldset>
          <label className="block">Audience<select value={audience} onChange={event => setAudience(event.target.value as typeof audience)} className="mt-1 block w-full rounded border border-stone-300 p-2">
            <option value="private">Private</option><option value="community">Georgia Tech community</option><option value="friends">Accepted friends</option><option value="selected_friends" disabled>Selected friends · coming after friendship setup</option>
          </select></label>
          <p className="text-sm text-stone-500">Audience is saved now. Other-user schedule browsing and friendship checks are not connected yet.</p>
          <label className="block">Sharing mode<select value={mode} onChange={event => setMode(event.target.value as typeof mode)} className="mt-1 block w-full rounded border border-stone-300 p-2"><option value="visible">Visible on shared schedule</option><option value="matching_only">Agent matching only</option></select></label>
          <button type="submit" className="rounded-lg bg-teal-800 px-4 py-3 text-white disabled:opacity-60">{saving ? 'Working…' : editingId ? 'Save changes' : 'Save social window'}</button>
          {editingId && <button type="button" onClick={() => { resetForm(); setError(''); }} className="ml-3 underline">Cancel editing</button>}
        </fieldset>
        {error && <p role="alert" className="text-red-700">{error}</p>}
        {notice && <p role="status" className="text-teal-800">{notice}</p>}
      </form>
      <div className="space-y-4"><h3 className="text-lg font-medium">Saved windows</h3>
        {loading ? <p role="status">Loading windows…</p> : listError ? <div role="alert"><p className="text-red-700">{listError}</p><button onClick={() => setReload(value => value + 1)} className="mt-2 underline">Retry loading windows</button></div> : windows.length === 0 ? <p>No social windows yet.</p> : <ul className="space-y-3">{windows.map(window => <li key={window.id} className="space-y-2 rounded-lg border border-stone-200 p-4">
          <p className="font-medium">{window.allowed_activities.join(', ')}</p><p className="text-sm">{displayTime(window.start)} → {displayTime(window.end)}</p>
          <p className="text-sm text-stone-600">{window.visibility.audience.replaceAll('_', ' ')} · {window.sharing_mode === 'matching_only' ? 'Matching only' : 'Visible'}</p>
          <div className="flex gap-4">
            <button disabled={saving || window.visibility.audience === 'selected_friends'} onClick={() => beginEdit(window)} className="text-teal-800 underline disabled:opacity-50">Edit</button>
            <button disabled={saving} onClick={() => { setConfirmDeleteId(window.id); setError(''); }} className="text-red-700 underline disabled:opacity-50">Delete</button>
          </div>
          {window.visibility.audience === 'selected_friends' && <p className="text-xs text-stone-500">Editing requires friendship setup.</p>}
          {confirmDeleteId === window.id && <div className="rounded border border-red-200 bg-red-50 p-3">
            <p>Delete this social window? This cannot be undone.</p>
            <button disabled={saving} onClick={() => removeWindow(window.id)} className="mt-2 mr-4 font-medium text-red-800 underline">Confirm delete</button>
            <button disabled={saving} onClick={() => setConfirmDeleteId(null)} className="underline">Keep window</button>
          </div>}
        </li>)}</ul>}
      </div>
    </div>
  </section>;
}
