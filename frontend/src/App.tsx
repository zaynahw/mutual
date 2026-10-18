import React from 'react';
import { getMe, listUsers, listOverviews, getAuthStatus, beginGoogle, logout } from './lib/api';
import type { User, PublicUser, HangoutOverview, HangoutRequest, AuthStatus } from './lib/api';
import { visibleProposals, planStatus } from './lib/proposals';
import { dateTime } from './lib/display';
import { IntentRequestForm } from './components/IntentRequestForm';
import { MatchingPreferences } from './components/MatchingPreferences';
import { PrivatePreferences } from './components/PrivatePreferences';
import { Friendships } from './components/Friendships';
import { SocialWindows } from './components/SocialWindows';
import ScheduleView from './components/ScheduleView.jsx';
import { PlanWorkspace } from './components/PlanWorkspace';
import logo from '../images/logo.jpg';

type Page = 'overview'|'new'|'plans'|'people'|'availability'|'settings';
const pages: [Page,string][] = [['overview','Overview'],['new','Plan with someone'],['plans','My plans'],['people','Friends'],['availability','Availability'],['settings','My preferences']];
const identities = ['Zaynah','Daniella','Kusum','Mariann'];

export function App() {
  const [auth,setAuth] = React.useState<AuthStatus|null>(null);
  const [error,setError] = React.useState('');
  const [reload,setReload] = React.useState(0);
  const [busy,setBusy] = React.useState(false);
  React.useEffect(() => {
    const controller=new AbortController();
    getAuthStatus(controller.signal).then(data => {if(!controller.signal.aborted) {setAuth(data);setError('');}})
      .catch(e => {if(!controller.signal.aborted) setError(e instanceof Error?e.message:'Cannot reach the backend.');});
    return () => controller.abort();
  },[reload]);
  async function authorize(purpose:'login'|'calendar') {
    if(busy)return;setBusy(true);setError('');
    try {const result=await beginGoogle(purpose,new AbortController().signal);window.location.assign(result.authorization_url);}
    catch(e) {setError(e instanceof Error?e.message:'Could not start Google sign-in.');setBusy(false);}
  }
  async function signOut() {
    setBusy(true);setError('');
    try {await logout(new AbortController().signal);setAuth(null);setReload(n=>n+1);}
    catch(e) {setError(e instanceof Error?e.message:'Could not sign out.');}
    finally {setBusy(false);}
  }
  if(!auth) return <main className="page-content"><h1>Mutual</h1><p role="status">Connecting to Mutual…</p>{error && <div role="alert"><p>{error}</p><button className="primary-button" onClick={()=>setReload(n=>n+1)}>Retry</button></div>}</main>;
  if(auth.mode==='google' && !auth.authenticated) return <main className="page-content login-page"><img src={logo} alt="Mutual" width="80"/><h1>Make time for your people.</h1><p>Sign in, connect your calendar, and let your personal agents help you find a plan.</p>
    {new URLSearchParams(window.location.search).get('auth')==='failed' && <p role="alert">Google sign-in or calendar consent did not finish. Try again and choose the same account when connecting your calendar.</p>}
    {!auth.configured && <p role="status">Google sign-in needs backend credentials and a token-encryption key. See the setup instructions.</p>}
    {error && <p role="alert">{error}</p>}<button className="primary-button" disabled={busy||!auth.configured} onClick={()=>void authorize('login')}>{busy?'Opening Google…':'Continue with Google'}</button></main>;
  return <><div className="auth-feedback">{error && <p role="alert">{error}</p>}</div><Workspace key={auth.user?.id||'demo'} auth={auth} authorize={()=>void authorize('calendar')} signOut={()=>void signOut()} authBusy={busy}/></>;
}

function Workspace({auth,authorize,signOut,authBusy}:{auth:AuthStatus;authorize:()=>void;signOut:()=>void;authBusy:boolean}) {
  const [identity,setIdentity] = React.useState(auth.user?.id || 'demo-zaynah');
  const [profile,setProfile] = React.useState<{user:User;users:PublicUser[]}|null>(null);
  const [page,setPage] = React.useState<Page>('overview');
  const [error,setError] = React.useState('');
  const [reload,setReload] = React.useState(0);
  const [plans,setPlans] = React.useState<HangoutOverview[]>([]);
  const [planError,setPlanError] = React.useState('');
  const [selected,setSelected] = React.useState<string|null>(null);
  const [autoRequest,setAutoRequest] = React.useState<string|null>(null);
  const [plansLoading,setPlansLoading] = React.useState(true);
  React.useEffect(() => {
    const controller = new AbortController();setError('');setProfile(null);setPlans([]);setSelected(null);setAutoRequest(null);
    Promise.all([getMe(identity,controller.signal),listUsers(identity,controller.signal)])
      .then(([user,users]) => {if(!controller.signal.aborted) setProfile({user,users});})
      .catch(e => {if(!controller.signal.aborted) setError(e instanceof TypeError ? 'Cannot reach the backend on port 8000.' : e.message);});
    return () => controller.abort();
  },[identity,reload]);
  const refresh = React.useCallback(async (signal:AbortSignal) => {
    setPlansLoading(true);
    try {const data=await listOverviews(identity,signal);if(!signal.aborted) {setPlans(data);setPlanError('');}}
    catch(e) {if(!signal.aborted) setPlanError(e instanceof Error ? e.message : 'Could not load plans.');}
    finally {if(!signal.aborted) setPlansLoading(false);}
  },[identity]);
  React.useEffect(() => {const controller=new AbortController();void refresh(controller.signal);return () => controller.abort();},[page,refresh,reload]);
  function saved(request:HangoutRequest) {
    setPlans(old => [...old.filter(item => item.request.id!==request.id),{request,proposals:[]}]);
    setSelected(request.id);setAutoRequest(request.id);setPage('plans');
  }
  function updated(user:User) {setProfile(old => old?.user.id===user.id ? {...old,user} : old);}
  function open(id:string) {setSelected(id);setPage('plans');}
  const me = profile?.user;
  const activePlans = plans.filter(item => visibleProposals(item.proposals.map(response => response.proposal)).length>0);
  return <div className="app-shell mutual-product">
    <header className="site-header"><div className="header-inner">
      <button className="brand" onClick={() => setPage('overview')} aria-label="Mutual overview"><img className="brand-mark" src={logo} alt=""/><span>mutual</span></button>
      <nav className="primary-nav" aria-label="Main navigation">{pages.map(([key,label]) => <button key={key} aria-current={page===key?'page':undefined} className={`nav-link ${page===key?'active':''}`} onClick={() => setPage(key)}>{label}</button>)}</nav>
      {auth.mode==='demo' ? <label className="identity-picker">Demo identity<select aria-label="Demo identity" value={identity} onChange={e => setIdentity(e.target.value)}>{identities.map(name => <option key={name} value={`demo-${name.toLowerCase()}`}>{name}</option>)}</select></label> : <div className="identity-picker"><span>{auth.user?.display_name}</span><button disabled={authBusy} onClick={signOut}>Sign out</button></div>}
    </div></header>
    <main className="page-content">
      {auth.mode==='demo' ? <div className="demo-notice">Demo accounts · Calendar writes are simulated · <a href="/demo.html">Backend testing panel ↗</a></div> : <section className="calendar-connection">
        <span>{auth.calendar_connected?'Google Calendar connected · Approved plans create real events':'Connect Google Calendar to check availability and schedule approved plans.'}</span>
        <button className="primary-button" disabled={authBusy||!auth.configured} onClick={authorize}>{authBusy?'Opening Google…':auth.calendar_connected?'Reconnect calendar':'Connect Google Calendar'}</button>
        {new URLSearchParams(window.location.search).get('auth')==='failed' && <p role="alert">Connection did not finish. Please retry and choose the same Google account you signed in with.</p>}
      </section>}
      {error && <div role="alert" className="demo-panel"><p>{error}</p><button onClick={() => setReload(n => n+1)}>Retry connection</button></div>}
      {!profile && !error && <p role="status">Loading your space…</p>}
      {profile && me && me.id===identity && <div key={identity}>
        <div hidden={page!=='overview'}>
          <section className="page-intro"><div><h1>Welcome, {me.display_name.replace(/\s*\(demo\)/i,'')}</h1><p className="intro-date">Make room for the people you want to see.</p></div><button className="primary-button" onClick={() => setPage('new')}>Start a plan</button></section>
          <div className="dashboard-grid">
            <section className="plans-panel"><div className="panel-heading"><h2>Your plans</h2><button className="text-link" onClick={() => setPage('plans')}>View all ↗</button></div>
              {plansLoading && <p role="status">Loading plans…</p>}
              {planError && <p role="alert">{planError}</p>}
              {!plansLoading && !planError && !activePlans.length && <p>No suggestions yet. Tell your agent what sounds good.</p>}
              <div className="plan-list">{activePlans.slice(0,4).map(item => {
                const proposal=visibleProposals(item.proposals.map(p => p.proposal))[0];
                const other=item.request.requester_id===identity?item.request.invitee_id:item.request.requester_id;
                return <button className="plan-card" key={item.request.id} onClick={() => open(item.request.id)}><span className="plan-accent"/><span className="plan-copy"><strong>{proposal.activity} with {profile.users.find(u => u.id===other)?.display_name || other}</strong><span>{dateTime(proposal.slot.start,me.timezone)}</span><span>{planStatus(item.proposals,identity)}</span></span></button>;
              })}</div>
            </section>
            {page==='overview' && <ScheduleView key={`${identity}-${reload}`} userId={identity} timezone={me.timezone} onSelect={item => {if(item.type==='proposal') {const match=plans.find(p => p.proposals.some(value => value.proposal.id===item.id));if(match) open(match.request.id);}}}/>}
          </div>
        </div>
        <div hidden={page!=='new'} className="product-request">
          <div className="page-intro"><div><h1>Plan with someone</h1><p className="intro-date">Share an idea. Your agents can work out the details.</p></div></div>
          <div className="demo-panel"><IntentRequestForm active={page==='new'} user={me} users={profile.users} onSaved={saved}/></div>
        </div>
        <div hidden={page!=='plans'}>
          <div className="page-intro"><div><h1>My plans</h1><p className="intro-date">Suggestions, responses, and your next hangout.</p></div><button className="primary-button" onClick={() => setPage('new')}>Start a plan</button></div>
          <PlanWorkspace calendarMode={auth.calendar_mode} calendarConnected={auth.calendar_connected || auth.mode==='demo'} user={me} users={profile.users} plans={plans} selected={selected} onSelect={setSelected} autoRequest={autoRequest} onAutoStarted={() => setAutoRequest(null)} active={page==='plans'} refresh={refresh} loading={plansLoading} error={planError}/>
        </div>
        <div hidden={page!=='people'}><h1>Friends</h1><Friendships currentUser={me} users={profile.users} active={page==='people'}/></div>
        <div hidden={page!=='availability'} className="space-y-6"><h1>My availability</h1><MatchingPreferences user={me} onSaved={updated}/><details><summary>Choose specific social windows instead</summary><SocialWindows user={me} users={profile.users} active={page==='availability'}/></details></div>
        <div hidden={page!=='settings'} className="demo-panel space-y-4"><h1>My preferences</h1><p>Your agent uses these privately when considering plans.</p><PrivatePreferences user={me} onSaved={updated}/><p>Timezone: {me.timezone}</p><p>Allowed activities: {me.hard_constraints.allowed_activities.join(', ')}</p><p>Maximum duration: {me.hard_constraints.max_duration_minutes} minutes</p><p>Activity boundaries and timezone are currently read-only.</p></div>
      </div>}
    </main>
  </div>;
}
