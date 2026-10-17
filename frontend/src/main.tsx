import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Link, NavLink, Outlet, Route, Routes, useParams } from 'react-router-dom';
import { api, type DashboardData, type DashboardProposal, type Friend, USE_MOCKS } from './api.js';
import logoUrl from '../images/logo.jpg';
import ScheduleView from './components/ScheduleView.jsx';
import FriendPicker from './components/FriendPicker.jsx';
import SocialWindowForm from './components/SocialWindowForm.jsx';
import './style.css';

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
