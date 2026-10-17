import React from 'react';
import ReactDOM from 'react-dom/client';
<<<<<<< HEAD
import { BrowserRouter, Link, NavLink, Outlet, Route, Routes, useParams } from 'react-router-dom';
import { api, type DashboardData, type DashboardProposal, type Friend, USE_MOCKS } from './api.js';
import logoUrl from '../images/logo.jpg';
import ScheduleView from './components/ScheduleView.jsx';
import FriendPicker from './components/FriendPicker.jsx';
import SocialWindowForm from './components/SocialWindowForm.jsx';
=======
import { checkHealth, getMe, listUsers } from './lib/api';
import type { PublicUser, User } from './lib/api';
>>>>>>> origin/main
import './style.css';
import { SocialWindows } from './components/SocialWindows';
import { Friendships } from './components/Friendships';

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

<<<<<<< HEAD
const navigation = [
  { label: 'Overview', to: '/', end: true },
  { label: 'Requests', to: '/requests' },
  { label: 'Proposals', to: '/proposals' },
  { label: 'Availability', to: '/availability' },
  { label: 'Profile settings', to: '/settings' },
];

function AppShell() {
  return <div className="app-shell">
    <header className="site-header">
      <div className="header-inner">
        <Link className="brand" to="/" aria-label="Mutual overview"><img className="brand-mark" src={logoUrl} alt="" /><span>mutual</span></Link>
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map((item) => <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            {item.label}
          </NavLink>)}
        </nav>
        <span className="mode-indicator"><span />{USE_MOCKS ? 'Demo' : 'Live'}</span>
      </div>
    </header>
    <Outlet />
  </div>;
}

function DashboardPage() {
  const [dashboard, setDashboard] = React.useState<DashboardData | null>(null);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    api.getDashboard().then(setDashboard).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : 'Dashboard could not be loaded.');
    });
  }, []);

  if (error) return <main className="page-content"><section className="load-state" role="alert"><p className="eyebrow">DASHBOARD UNAVAILABLE</p><h1>Your space is waiting.</h1><p>{error}</p><p>Set <code>VITE_USE_MOCKS=true</code> to preview this dashboard.</p></section></main>;
  if (!dashboard) return <main className="page-content"><p className="load-state" role="status">Loading your space...</p></main>;

  const firstName = dashboard.user.display_name.split(' ')[0];
  const today = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', timeZone: dashboard.user.timezone }).format(new Date());
  return <main className="page-content dashboard-page">
    <section className="page-intro">
      <h1>Welcome, {firstName}</h1>
      <p className="intro-date">{today}</p>
    </section>

    <div className="dashboard-grid">
      <section className="plans-panel" aria-labelledby="upcoming-heading">
        <div className="panel-heading"><h2 id="upcoming-heading">Upcoming plans</h2><Link to="/proposals" aria-label="View all plans">↗</Link></div>
        {dashboard.upcoming_proposals.length ? <div className="plan-list">{dashboard.upcoming_proposals.map((proposal) => <ProposalRow key={proposal.id} proposal={proposal} timezone={dashboard.user.timezone} />)}</div> : <div className="empty-state"><p>No plans yet.</p><Link className="text-link" to="/requests/new">Start a plan <span aria-hidden="true">→</span></Link></div>}
      </section>

      <ScheduleView userId={dashboard.user.id} timezone={dashboard.user.timezone} />
=======
function App() {
  const [selectedId, setSelectedId] = React.useState(demoUsers[0].id);
  const [reload, setReload] = React.useState(0);
  const [panel, setPanel] = React.useState<PanelState>({ status: 'loading' });
  const [health, setHealth] = React.useState('Not checked');

  React.useEffect(() => {
    const controller = new AbortController();
    setPanel({ status: 'loading' });
    Promise.all([
      listUsers(selectedId, controller.signal),
      getMe(selectedId, controller.signal),
    ]).then(([users, me]) => {
      if (!controller.signal.aborted) setPanel({ status: 'ready', selectedId, users, me });
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) {
        setPanel({ status: 'error', message: error instanceof TypeError
          ? 'Cannot reach the backend. Start it on port 8000 and check the API URL.'
          : error instanceof Error ? error.message : 'Could not load demo data.' });
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
        <p className="text-sm font-semibold uppercase tracking-widest text-teal-700">Demo integration panel</p>
        <h1 className="text-5xl font-bold">Mutual</h1>
        <p>Two personal agents. A plan that feels comfortable for both people.</p>
        <p className="max-w-2xl text-sm text-stone-600">Switch between fictional demo profiles to explore saved settings. This switcher is for testing and does not sign you into a real account.</p>
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

      {(panel.status === 'loading' || (panel.status === 'ready' && panel.selectedId !== selectedId)) && <p role="status">Loading profiles…</p>}
      {panel.status === 'error' && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-800">{panel.message}</p>}
      {panel.status === 'ready' && panel.selectedId === selectedId && <div className="grid gap-6 md:grid-cols-2">
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
          <p className="text-sm text-stone-600">Owner-only settings for {panel.me.display_name}. Read-only for now.</p>
          <dl className="space-y-4">
            <div><dt className="text-sm text-stone-500">Timezone</dt><dd>{panel.me.timezone}</dd></div>
            <div><dt className="text-sm text-stone-500">Calendar sharing</dt><dd>{panel.me.calendar_sharing.audience.replaceAll('_', ' ')}</dd></div>
            <div><dt className="text-sm text-stone-500">Preferred activities</dt><dd>{panel.me.preferences.preferred_activities.join(', ') || 'None selected'}</dd></div>
            <div><dt className="text-sm text-stone-500">Private preference note</dt><dd>{panel.me.preferences.soft_preference_note || 'None'}</dd></div>
            <div><dt className="text-sm text-stone-500">Allowed activities · hard constraint</dt><dd>{panel.me.hard_constraints.allowed_activities.join(', ')}</dd></div>
            <div><dt className="text-sm text-stone-500">Maximum duration · hard constraint</dt><dd>{panel.me.hard_constraints.max_duration_minutes} minutes</dd></div>
          </dl>
        </section>
      </div>}
      {panel.status === 'ready' && panel.selectedId === selectedId && <Friendships key={`friendships-${selectedId}`} currentUser={panel.me} users={panel.users} />}
      {panel.status === 'ready' && panel.selectedId === selectedId && <SocialWindows key={`windows-${selectedId}`} user={panel.me} />}
>>>>>>> origin/main
    </div>
  </main>;
}

function ProposalRow({ proposal, timezone }: { proposal: DashboardProposal; timezone: string }) {
  const start = new Date(proposal.slot.start);
  const end = new Date(proposal.slot.end);
  const date = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: timezone }).format(start);
  const weekday = new Intl.DateTimeFormat('en-US', { weekday: 'short', timeZone: timezone }).format(start);
  const startTime = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', timeZone: timezone }).format(start);
  const endTime = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit', timeZone: timezone }).format(end);
  const status = { pending: ['Awaiting approval', 'pending'], approved: ['Both approved', 'approved'], scheduled: ['On the calendar', 'scheduled'], declined: ['Declined', 'declined'] }[proposal.status];
  const [statusLabel, statusClass] = status;
  return <Link to={`/proposals/${proposal.id}`} className="plan-card"><span className="plan-accent" /><span className="plan-copy"><strong>{proposal.activity} with {proposal.other_person}</strong><span>{weekday}, {date} · {startTime}–{endTime}</span></span><span className={`status-badge ${statusClass}`}>{statusLabel}</span></Link>;
}

const sections = {
  requests: { eyebrow: 'YOUR PLANS', title: 'Requests', description: 'Keep track of the plans you have started and the people you have invited.', action: { label: 'Create new', to: '/requests/new' } },
  proposals: { eyebrow: 'FINDING A TIME', title: 'Proposals', description: 'Review suggested times and follow the approvals for each plan.' },
  availability: { eyebrow: 'YOUR BOUNDARIES', title: 'Availability', description: 'Choose the windows you are comfortable sharing. Your calendar details stay private.' },
  settings: { eyebrow: 'YOUR DETAILS', title: 'Profile settings', description: 'Manage your demo profile, activity preferences, and timezone.' },
};

function SectionPage({ page }: { page: { eyebrow: string; title: string; description: string; action?: { label: string; to: string } } }) {
  return <main className="page-content section-page"><p className="eyebrow">{page.eyebrow}</p><h1>{page.title}</h1><p className="section-description">{page.description}</p>{page.action && <Link className="primary-button" to={page.action.to}><span aria-hidden="true">+</span>{page.action.label}</Link>}<section className="section-notice"><span className="notice-mark" aria-hidden="true">✳</span><div><strong>This space is taking shape.</strong><p>This section will be available as its workflow is connected.</p></div></section><Link className="back-link" to="/">← Back to overview</Link></main>;
}

function ProposalDetailPage() {
  const { proposalId } = useParams();
  const knownProposal = proposalId === 'proposal-demo-1' || proposalId === 'proposal-demo-2';
  return <SectionPage page={{ eyebrow: 'PROPOSAL', title: knownProposal ? 'Coffee with Sam' : 'Proposal not found', description: knownProposal ? 'Proposal details and approval actions will appear here.' : 'That proposal could not be found.' }} />;
}

function NewRequestPage() {
  const [selectedFriend, setSelectedFriend] = React.useState<Friend | null>(null);

  return <main className="page-content section-page request-create">
    <p className="eyebrow">MAKE A PLAN</p>
    <h1>Start a plan</h1>
    <p className="section-description">Choose a friend to plan something together.</p>
    <div className="request-create__workspace">
      <FriendPicker
        currentUserId="demo-alex"
        selectedFriendId={selectedFriend?.id ?? null}
        onSelect={setSelectedFriend}
      />
      <p className="request-create__selection" role="status" aria-live="polite">
        {selectedFriend ? `Selected: ${selectedFriend.display_name}` : 'No friend selected'}
      </p>
    </div>
    <Link className="back-link" to="/">← Back to overview</Link>
  </main>;
}

function AvailabilityPage() {
  return <main className="page-content section-page">
    <p className="eyebrow">YOUR BOUNDARIES</p>
    <h1>Availability</h1>
    <p className="section-description">Choose the windows you are comfortable sharing. Your calendar details stay private.</p>
    <SocialWindowForm userId="demo-alex" />
    <Link className="back-link" to="/">← Back to overview</Link>
  </main>;
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><Routes><Route element={<AppShell />}>
  <Route path="/" element={<DashboardPage />} />
  <Route path="/requests" element={<SectionPage page={sections.requests} />} />
  <Route path="/requests/new" element={<NewRequestPage />} />
  <Route path="/proposals" element={<SectionPage page={sections.proposals} />} />
  <Route path="/proposals/:proposalId" element={<ProposalDetailPage />} />
  <Route path="/availability" element={<AvailabilityPage />} />
  <Route path="/settings" element={<SectionPage page={sections.settings} />} />
  <Route path="*" element={<SectionPage page={{ eyebrow: 'NOT FOUND', title: 'Page not found', description: 'That page could not be found.' }} />} />
</Route></Routes></BrowserRouter></React.StrictMode>);
