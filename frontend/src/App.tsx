import React from 'react';
import { getMe, listUsers, listOverviews } from './lib/api';
import type { User, PublicUser, HangoutOverview, HangoutRequest } from './lib/api';
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
  const [identity,setIdentity] = React.useState('demo-zaynah');
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
      <label className="identity-picker">Demo identity<select aria-label="Demo identity" value={identity} onChange={e => setIdentity(e.target.value)}>{identities.map(name => <option key={name} value={`demo-${name.toLowerCase()}`}>{name}</option>)}</select></label>
    </div></header>
    <main className="page-content">
      <div className="demo-notice">Demo accounts · Calendar writes are simulated · <a href="/demo.html">Backend testing panel ↗</a></div>
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
          <PlanWorkspace user={me} users={profile.users} plans={plans} selected={selected} onSelect={setSelected} autoRequest={autoRequest} onAutoStarted={() => setAutoRequest(null)} active={page==='plans'} refresh={refresh} loading={plansLoading} error={planError}/>
        </div>
        <div hidden={page!=='people'}><h1>Friends</h1><Friendships currentUser={me} users={profile.users} active={page==='people'}/></div>
        <div hidden={page!=='availability'} className="space-y-6"><h1>My availability</h1><MatchingPreferences user={me} onSaved={updated}/><details><summary>Choose specific social windows instead</summary><SocialWindows user={me} users={profile.users} active={page==='availability'}/></details></div>
        <div hidden={page!=='settings'} className="demo-panel space-y-4"><h1>My preferences</h1><p>Your agent uses these privately when considering plans.</p><PrivatePreferences user={me} onSaved={updated}/><p>Timezone: {me.timezone}</p><p>Allowed activities: {me.hard_constraints.allowed_activities.join(', ')}</p><p>Maximum duration: {me.hard_constraints.max_duration_minutes} minutes</p><p>Activity boundaries and timezone are currently read-only.</p></div>
      </div>}
    </main>
  </div>;
}
