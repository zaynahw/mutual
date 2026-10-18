import React from 'react';
import ReactDOM from 'react-dom/client';
import { checkHealth, getMe, listUsers, getAuthStatus } from '../lib/api';
import type { PublicUser, User } from '../lib/api';
import './style.css';
import { MatchingPreferences } from '../components/MatchingPreferences';
import { SocialWindows } from '../components/SocialWindows';
import { Friendships } from '../components/Friendships';
import { ScheduleViewer } from '../components/ScheduleViewer';
import { HangoutRequests } from './components/HangoutRequests';
import { PrivatePreferences } from '../components/PrivatePreferences';

const demoUsers = [
  { id: 'demo-zaynah', name: 'Zaynah' },
  { id: 'demo-daniella', name: 'Daniella' },
  { id: 'demo-kusum', name: 'Kusum' },
  { id: 'demo-mariann', name: 'Mariann' },
];

type PanelState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; selectedId: string; users: PublicUser[]; me: User };

function App() {
  const [selectedId, setSelectedId] = React.useState(demoUsers[0].id);
  const [reload, setReload] = React.useState(0);
  const [panel, setPanel] = React.useState<PanelState>({ status: 'loading' });
  const [tab, setTab] = React.useState<'plans' | 'people' | 'availability' | 'schedules' | 'profile'>('plans');
  const [profileError, setProfileError] = React.useState('');
  const [health, setHealth] = React.useState('Not checked');

  React.useEffect(() => {
    const controller = new AbortController();
    setProfileError('');
    setPanel(previous => previous.status === 'ready' && previous.selectedId === selectedId ? previous : { status: 'loading' });
    getAuthStatus(controller.signal).then(auth => {
      if (auth.mode !== 'demo') throw new Error('The backend testing panel requires demo mode. Use the main app for Google accounts.');
      return Promise.all([listUsers(selectedId,controller.signal),getMe(selectedId,controller.signal)]);
    }).then(([users, me]) => {
      if (!controller.signal.aborted) setPanel({ status: 'ready', selectedId, users, me });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) {
        const message = error instanceof TypeError
          ? 'Cannot reach the backend. Start it on port 8000 and check the API URL.'
          : error instanceof Error ? error.message : 'Could not load demo data.';
        setProfileError(message);
        setPanel(previous => previous.status === 'ready' && previous.selectedId === selectedId ? previous : { status: 'error', message });
      }
    });
    return () => controller.abort();
  }, [selectedId, reload]);

  async function handleHealth() {
    setHealth('Checking…');
    try { setHealth(await checkHealth()); }
    catch { setHealth('Backend unavailable'); }
  }

  return <main className="min-h-screen bg-stone-50 px-5 py-10 text-stone-900 sm:px-10">
    <div className="mx-auto max-w-5xl space-y-8">
      <header className="space-y-3">
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-700">Mutual · Backend demo</p>
        <h1 className="text-5xl font-bold">Mutual</h1>
        <p>Make a plan, choose a time, and get both people’s approval.</p>
        <p className="max-w-2xl text-sm text-stone-600">Switch demo users to try both sides of a hangout. Use People and My availability to set up who can match with you.</p>
      </header>

      <section aria-label="Demo controls" className="flex flex-wrap items-end gap-4 rounded-xl border border-stone-200 bg-white p-5">
        <div className="space-y-2">
          <label htmlFor="demo-user" className="block text-sm font-medium">Acting as</label>
          <select id="demo-user" value={selectedId} onChange={event => setSelectedId(event.target.value)} className="rounded-lg border border-stone-300 bg-white p-3">
            {demoUsers.map(user => <option key={user.id} value={user.id}>{user.name} (demo)</option>)}
          </select>
        </div>
        <button onClick={() => setReload(value => value + 1)} className="rounded-lg bg-teal-800 px-4 py-3 text-white">Reload data</button>
        <button onClick={handleHealth} className="rounded-lg border border-stone-300 px-4 py-3">Check backend health</button>
        <p role="status" className="py-3 text-sm">Backend: {health}</p>
      </section>

      <nav aria-label="Demo sections" className="flex flex-wrap gap-2 border-b border-stone-200 pb-4">
        {([['plans', 'My plans'], ['people', 'People'], ['availability', 'My availability'], ['schedules', 'Browse schedules'], ['profile', 'My profile']] as const).map(([value, label]) =>
          <button key={value} aria-current={tab === value ? 'page' : undefined} onClick={() => setTab(value)} className={`rounded-lg px-4 py-3 font-medium ${tab === value ? 'bg-teal-800 text-white' : 'bg-white text-stone-700'}`}>{label}</button>)}
      </nav>
      {(panel.status === 'loading' || (panel.status === 'ready' && panel.selectedId !== selectedId)) && <p role="status">Loading profiles…</p>}
      {profileError && panel.status === 'ready' && <p role="alert" className="text-red-800">{profileError} Your current draft is preserved.</p>}
      {panel.status === 'error' && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-800">{panel.message}</p>}
      {panel.status === 'ready' && panel.selectedId === selectedId && <div hidden={tab !== 'profile'}><div className="grid gap-6 md:grid-cols-2">
        <section className="space-y-4 rounded-xl border border-stone-200 bg-white p-6">
          <h2 className="text-2xl font-semibold">People</h2>
          <p className="text-sm text-stone-600">Public profiles only. Private preferences and settings are excluded.</p>
          <ul className="divide-y divide-stone-100">
            {panel.users.map(user => <li key={user.id} className="space-y-1 py-4">
              <p className="font-medium">{user.display_name}{user.id === selectedId ? ' · You' : ''}</p>
              <p className="text-sm text-stone-600">Georgia Tech · Demo profile</p>
            </li>)}
          </ul>
          {panel.users.length === 0 && <p>No demo profiles found.</p>}
        </section>
        <section className="space-y-5 rounded-xl border border-stone-200 bg-white p-6">
          <h2 className="text-2xl font-semibold">My profile</h2>
          <p className="text-sm text-stone-600">Private preferences for {panel.me.display_name}. Other profile settings are read-only.</p>
          <dl className="space-y-4">
            <div><dt className="text-sm text-stone-500">Timezone</dt><dd>{panel.me.timezone}</dd></div>
            <div><dt className="text-sm text-stone-500">Calendar sharing</dt><dd>{panel.me.calendar_sharing.audience.replaceAll('_', ' ')}</dd></div>
            <div><dt className="text-sm text-stone-500">Preferred activities</dt><dd>{panel.me.preferences.preferred_activities.join(', ') || 'None selected'}</dd></div>
            <div><dt className="text-sm text-stone-500">Allowed activities · hard constraint</dt><dd>{panel.me.hard_constraints.allowed_activities.join(', ')}</dd></div>
            <div><dt className="text-sm text-stone-500">Maximum duration · hard constraint</dt><dd>{panel.me.hard_constraints.max_duration_minutes} minutes</dd></div>
          </dl>
          <PrivatePreferences key={`preferences-${selectedId}`} user={panel.me} onSaved={updated => setPanel(previous => previous.status === 'ready' && previous.selectedId === updated.id ? {...previous,me:updated} : previous)} />
        </section>
      </div></div>}
      {panel.status === 'ready' && panel.selectedId === selectedId && <div hidden={tab !== 'people'}><Friendships key={`friendships-${selectedId}`} currentUser={panel.me} users={panel.users} active={tab === 'people'} /></div>}
      {panel.status === 'ready' && panel.selectedId === selectedId && <div hidden={tab !== 'availability'}><MatchingPreferences key={`matching-${selectedId}`} user={panel.me} onSaved={updated => setPanel(previous => previous.status === 'ready' && previous.selectedId === updated.id ? {...previous,me:updated} : previous)} /><SocialWindows key={`windows-${selectedId}`} user={panel.me} users={panel.users} active={tab === 'availability'} /></div>}
      {panel.status === 'ready' && panel.selectedId === selectedId && <div hidden={tab !== 'schedules'}><ScheduleViewer key={`schedule-${selectedId}`} user={panel.me} users={panel.users} /></div>}
      {panel.status === 'ready' && panel.selectedId === selectedId && <div hidden={tab !== 'plans'}><HangoutRequests key={`plans-${selectedId}`} user={panel.me} users={panel.users} active={tab === 'plans'} onNavigate={setTab} /></div>}
    </div>
  </main>;
}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
