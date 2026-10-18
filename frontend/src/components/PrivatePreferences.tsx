import React from 'react';
import { updatePreferenceNote } from '../lib/api';
import type { User } from '../lib/api';

export function PrivatePreferences({ user, onSaved }: { user: User; onSaved: (updated: User) => void }) {
  const [note, setNote] = React.useState(user.preferences.soft_preference_note);
  const [savedNote, setSavedNote] = React.useState(user.preferences.soft_preference_note);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const pending = React.useRef<AbortController | null>(null);
  React.useEffect(() => () => pending.current?.abort(), []);
  return <form className="space-y-3" onSubmit={event => {
    event.preventDefault(); if (pending.current) return;
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setError(''); setNotice('');
    updatePreferenceNote(user.id,note,controller.signal).then(updated => {
      if (!controller.signal.aborted) {
        setNote(updated.preferences.soft_preference_note);
        setSavedNote(updated.preferences.soft_preference_note);
        setNotice('Private note saved. Run a new agent suggestion to use it; existing proposals stay unchanged.');
        onSaved(updated);
      }
    }).catch(error => {
      if (!controller.signal.aborted) setError(error instanceof TypeError ? 'Could not reach the backend. Retrying this save is safe.' : error instanceof Error ? error.message : 'Could not save preferences.');
    }).finally(() => { if (!controller.signal.aborted) {pending.current=null;setBusy(false);} });
  }}>
    <label htmlFor="private-note" className="block font-medium">Private preferences for my agent</label>
    <p id="private-note-help" className="text-sm text-stone-600">Describe preferred activities, duration, or time of day. Your note goes only to your own agent. It guides choices among valid options; it does not override availability, boundaries, or permissions.</p>
    <textarea id="private-note" aria-describedby="private-note-help" rows={5} maxLength={1000} disabled={busy} value={note} onChange={event => {setNote(event.target.value);setNotice('');setError('');}}
      placeholder="For example: Prefer a short coffee catch-up earlier in the day; a walk is my second choice."
      className="w-full rounded-lg border border-stone-300 bg-white p-3" />
    <p className="text-sm text-stone-500">{note.length}/1000 characters. Leave blank and save to clear.</p>
    <button disabled={busy || note === savedNote} className="rounded-lg bg-teal-800 px-4 py-2 text-white disabled:opacity-50">{busy ? 'Saving…' : 'Save private preferences'}</button>
    {error && <p role="alert" className="text-red-800">{error}</p>}
    {notice && <p role="status" className="text-teal-800">{notice}</p>}
  </form>;
}
