import React from 'react';
import ReactDOM from 'react-dom/client';
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

function App() {
  const [health, setHealth] = React.useState('Not checked');
  async function checkHealth() {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/health`);
      if (!response.ok) throw new Error('Health check failed');
      const data = await response.json() as { status: string };
      setHealth(data.status);
    } catch { setHealth('Backend unavailable'); }
  }
  return <main className="min-h-screen bg-stone-50 p-10 text-stone-900">
    <div className="mx-auto max-w-xl space-y-6">
      <p className="text-sm font-semibold uppercase tracking-widest text-teal-700">Hackathon scaffold · Demo only</p>
      <h1 className="text-5xl font-bold">Mutual</h1>
      <p>Two personal agents. A plan that feels comfortable for both people.</p>
      <p className="text-stone-600">Scheduling and approval screens will be built in the frontend lane. Both people must approve before a calendar event is created.</p>
      <button onClick={checkHealth} className="rounded-lg bg-teal-800 px-5 py-3 text-white">Check backend health</button>
      <p role="status">Backend: {health}</p>
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
