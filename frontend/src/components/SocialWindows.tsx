import React from 'react';
import { createMyWindow, deleteMyWindow, listMyWindows, updateMyWindow, listFriendRequests } from '../lib/api';
import type { Activity, SocialWindow, SocialWindowInput, User, PublicUser } from '../lib/api';
import { isoToZonedInput, zonedInputToISO } from '../lib/time';

import { SocialWindowForm } from './SocialWindowForm';
import { SocialWindowList } from './SocialWindowList';

export function SocialWindows({ user, users, active }: { user: User; users: PublicUser[]; active: boolean }) {
  const [windows, setWindows] = React.useState<SocialWindow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [listError, setListError] = React.useState('');
  const [error, setError] = React.useState('');
  const [notice, setNotice] = React.useState('');
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [title,setTitle]=React.useState('');
  const [start, setStart] = React.useState('');
  const [end, setEnd] = React.useState('');
  const [selectedFriends, setSelectedFriends] = React.useState<string[]>([]);
  const [friends, setFriends] = React.useState<PublicUser[]>([]);
  const [chosen, setChosen] = React.useState<Activity[]>([]);
  const [audience, setAudience] = React.useState<SocialWindowInput['visibility']['audience']>('private');
  const [mode, setMode] = React.useState<SocialWindowInput['sharing_mode']>('visible');
  const [reload, setReload] = React.useState(0);
  const pendingSave = React.useRef<AbortController | null>(null);

  React.useEffect(() => () => pendingSave.current?.abort(), []);
  React.useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    setLoading(true);
    setListError('');
    Promise.all([listMyWindows(user.id, controller.signal), listFriendRequests(user.id, controller.signal)]).then(([data, relationships]) => {
      if (!controller.signal.aborted) {
        setWindows(data);
        const ids = relationships.filter(item => item.status === 'accepted').map(item => item.sender_id === user.id ? item.recipient_id : item.sender_id);
        setFriends(users.filter(person => ids.includes(person.id)));
      }
    }).catch(() => {
      if (!controller.signal.aborted) setListError('Could not load windows. Check the backend and retry.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [user.id, reload, active, users]);

  function resetForm() {
    setEditingId(null);
    setTitle('');
    setStart('');
    setEnd('');
    setChosen([]); setSelectedFriends([]);
    setAudience('private');
    setMode('visible');
  }

  function beginEdit(window: SocialWindow) {
    setEditingId(window.id);setTitle(window.title||'');
    setStart(isoToZonedInput(window.start, user.timezone));
    setEnd(isoToZonedInput(window.end, user.timezone));
    setChosen([...window.allowed_activities]);
    setAudience(window.visibility.audience); setSelectedFriends(window.visibility.selected_friend_ids);
    setMode(window.sharing_mode);
    setError('');
    setNotice('');
    setConfirmDeleteId(null);
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
      if (audience === 'selected_friends' && (loading || listError || selectedFriends.length === 0)) throw new Error('Choose at least one currently accepted friend.');
      const input: SocialWindowInput = {
        title:title.trim()||null, start: startISO, end: endISO, allowed_activities: chosen,
        visibility: { audience, selected_friend_ids: audience === 'selected_friends' ? selectedFriends : [] }, sharing_mode: mode,
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

  return <section className="space-y-6 rounded-xl border border-stone-200 bg-white p-6" aria-label="My social availability">
    <div><h2 className="text-2xl font-semibold">My social availability</h2>
      <p className="mt-2 text-sm text-stone-600">Your saved windows, including private ones. All times below use {user.timezone}. Calendar conflicts will be checked later during matching.</p></div>
    <div className="grid gap-8 md:grid-cols-2">
      <SocialWindowForm
        title={title} setTitle={setTitle}
        editingId={editingId} saving={saving} start={start} end={end}
        chosen={chosen} audience={audience} friends={friends} selectedFriends={selectedFriends} setSelectedFriends={setSelectedFriends} mode={mode} error={error} notice={notice}
        setStart={setStart} setEnd={setEnd} setChosen={setChosen}
        setAudience={setAudience} setMode={setMode} onSubmit={submit}
        onCancel={() => { resetForm(); setError(''); }}
      />
      <SocialWindowList
        windows={windows} loading={loading} listError={listError} saving={saving}
        confirmDeleteId={confirmDeleteId} timezone={user.timezone}
        onRetry={() => setReload(value => value + 1)} onEdit={beginEdit}
        onRequestDelete={id => { setConfirmDeleteId(id); setError(''); }}
        onConfirmDelete={removeWindow} onCancelDelete={() => setConfirmDeleteId(null)}
      />
    </div>
  </section>;
}
