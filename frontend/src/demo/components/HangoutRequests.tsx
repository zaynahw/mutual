import React from 'react';
import { IntentRequestForm } from '../../components/IntentRequestForm';
import { createProposal, getCandidates, listOverviews, negotiateHangout } from '../../lib/api';
import type { Activity, CandidateOption, Duration, HangoutOverview, HangoutRequest, NegotiationResponse, ProposalResponse, PublicUser, User } from '../../lib/api';
import { visibleProposals, planStatus } from '../../lib/proposals';
import { ProposalViewer } from '../../components/ProposalViewer';
import { HangoutForm } from '../../components/HangoutForm';
import type { HangoutDraft } from '../../components/HangoutForm';
import { dateTime } from '../../lib/display';
import { isoToZonedInput, zonedInputToISO } from '../../lib/time';

function CandidateChoice({ option, timezone, disabled, save }: {
  option: CandidateOption; timezone: string; disabled: boolean;
  save: (activity: Activity, start: string, duration: Duration) => void;
}) {
  const [activity, setActivity] = React.useState(option.eligible_activities[0]);
  const [duration, setDuration] = React.useState(option.eligible_durations[0]);
  const [start, setStart] = React.useState(isoToZonedInput(option.slot.start, timezone));
  return <form className="demo-choice demo-form" onSubmit={e => { e.preventDefault(); save(activity, start, duration); }}>
    <p className="w-full">Available {dateTime(option.slot.start, timezone)} – {dateTime(option.slot.end, timezone)}</p>
    <label>Activity<select value={activity} disabled={disabled} onChange={e => setActivity(e.target.value as Activity)}>{option.eligible_activities.map(a => <option key={a}>{a}</option>)}</select></label>
    <label>Exact start<input required type="datetime-local" value={start} disabled={disabled} onChange={e => setStart(e.target.value)} /></label>
    <label>Minutes<select value={duration} disabled={disabled} onChange={e => setDuration(Number(e.target.value) as Duration)}>{option.eligible_durations.map(d => <option key={d}>{d}</option>)}</select></label>
    <button disabled={disabled}>Propose and approve this plan</button>
  </form>;
}

export function HangoutRequests({ user, users, active, onNavigate }: {
  user: User; users: PublicUser[]; active: boolean;
  onNavigate: (section: 'people' | 'availability') => void;
}) {
  const initialDraft = (): HangoutDraft => ({ invitee: users.find(p => p.id !== user.id)?.id || '', start:'2026-10-18T14:00', end:'2026-10-18T20:00', activities:['coffee'], durations:[30,60], location:'' });
  const [draft, setDraft] = React.useState<HangoutDraft>(initialDraft);
  const [overviews, setOverviews] = React.useState<HangoutOverview[]>([]);
  const [options, setOptions] = React.useState<{ requestId: string; items: CandidateOption[] } | null>(null);
  const [proposalId, setProposalId] = React.useState<string | null>(null);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [manual, setManual] = React.useState(false);
  const [showForm, setShowForm] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [negotiation, setNegotiation] = React.useState<{requestId: string; result: NegotiationResponse} | null>(null);
  const [negotiating, setNegotiating] = React.useState(false);
  const [notice, setNotice] = React.useState('');
  const [error, setError] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const pending = React.useRef<AbortController | null>(null);
  const readPending = React.useRef<AbortController | null>(null);
  const refresh = React.useCallback(async () => {
    readPending.current?.abort();
    const controller = new AbortController(); readPending.current = controller;
    setLoading(true);
    try {
      const data = await listOverviews(user.id, controller.signal);
      if (!controller.signal.aborted) {
        setOverviews(data);
        setSelectedId(id => data.some(item => item.request.id === id) ? id : null);
        setError('');
      }
    } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load plans.'); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }, [user.id]);
  React.useEffect(() => { if (active) void refresh(); }, [active, refresh]);
  React.useEffect(() => () => { pending.current?.abort(); readPending.current?.abort(); }, []);
  async function run(action: (signal: AbortSignal) => Promise<void>) {
    if (pending.current) return;
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setError(''); setNotice('');
    try { await action(controller.signal); }
    catch (e) { if (!controller.signal.aborted) setError(e instanceof TypeError ? 'Connection lost. Refresh this request before retrying; the same input can be retried safely.' : e instanceof Error ? e.message : 'Request failed.'); }
    finally { if (!controller.signal.aborted) { pending.current = null; setBusy(false); } }
  }
  const selected = overviews.find(item => item.request.id === selectedId);
  const visible = visibleProposals(selected?.proposals.map(item => item.proposal) || []);
  const agreed = visible.some(plan => plan.status === 'approved' || plan.status === 'scheduled');
  const displayedId = visible.find(plan => plan.id === proposalId)?.id || visible[0]?.id;
  const displayed = selected?.proposals.find(item => item.proposal.id === displayedId);
  const name = (id: string) => users.find(person => person.id === id)?.display_name || id;
  const other = (request: HangoutRequest) => request.requester_id === user.id ? request.invitee_id : request.requester_id;
  function updateProposal(result: ProposalResponse) {
    setOverviews(old => old.map(item => item.request.id === result.proposal.request_id ? { ...item, proposals:item.proposals.map(response => response.proposal.id === result.proposal.id ? result : result.proposal.status === 'cancelled' && ['pending','approved'].includes(response.proposal.status) ? {...response,proposal:{...response.proposal,status:'cancelled' as const}} : response) } : item));
    if (result.proposal.status === 'declined') setNotice('Plan declined. Other available options remain below.');
    if (result.proposal.status === 'cancelled') { setOptions(null); setNotice('Old options closed. Find another time, or revise the search. Fresh approvals will be required.'); void refresh(); }
    if (result.proposal.status === 'approved') { setOptions(null); setNotice('You both agreed. Other options are hidden.'); }
    if (result.proposal.status === 'scheduled') { setOptions(null); setNotice('Scheduled in the demo calendar. This time now counts as busy for both participants.'); }
  }
  function findTimes(request: HangoutRequest) {
    setOptions(null);
    void run(async signal => {
      const items = await getCandidates(user.id, request.id, signal);
      if (!signal.aborted) setOptions({requestId:request.id, items});
    });
  }
  function revise(request: HangoutRequest) {
    setDraft({invitee:other(request), start:isoToZonedInput(request.start,user.timezone), end:isoToZonedInput(request.end,user.timezone), activities:request.allowed_activities, durations:request.allowed_durations, location:request.location || ''});
    setNotice(''); setManual(true); setShowForm(true);
  }
  function askAgents(requestId: string) {
    setNegotiation(null);
    void run(async signal => {
      setNegotiating(true);
      try {
        const result = await negotiateHangout(user.id,requestId,signal);
        if (!signal.aborted) {
          setNegotiation({requestId,result});
          if (result.proposal) {setProposalId(result.proposal.id);setOptions(null);}
          await refresh();
        }
      } finally {if (!signal.aborted) setNegotiating(false);}
    });
  }
  function saved(request: HangoutRequest, useAgent: boolean) {
    setOverviews(old => [...old.filter(item => item.request.id !== request.id), {request,proposals:[]}]);
    setSelectedId(request.id); setProposalId(null); setShowForm(false); setDraft(initialDraft());
    if (useAgent) askAgents(request.id); else findTimes(request);
  }
  if (showForm) return <section className="demo-panel space-y-4">
    <button className="demo-secondary" onClick={() => setShowForm(false)}>Back to plans</button>
    <h2>Make time for someone</h2>
    <div className="flex gap-2"><button onClick={() => setManual(false)} aria-pressed={!manual}>Tell my agent</button><button className="demo-secondary" onClick={() => setManual(true)} aria-pressed={manual}>Advanced manual search</button></div>
    <div hidden={manual}><IntentRequestForm user={user} users={users} onSaved={request => saved(request,true)} /></div>
    <div hidden={!manual}><HangoutForm user={user} users={users} draft={draft} setDraft={setDraft} onBack={() => setShowForm(false)} onSaved={request => saved(request,false)} /></div>
  </section>;
  return <section className="demo-panel">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2>My plans</h2><p className="text-sm text-stone-600">Choose a request to continue. Status shows whose turn it is.</p></div>
      <div className="flex gap-2">
        <button className="demo-secondary" disabled={busy || loading} onClick={() => void refresh()}>Refresh plans</button>
        <button disabled={busy || loading} onClick={() => {setNotice('');setManual(false);setShowForm(true);}}>New hangout</button>
      </div>
    </div>
    <p className="text-sm text-stone-600">Mock calendars · manual or agent suggestions · times in {user.timezone}</p>
    {loading && <p role="status">Refreshing plans…</p>}
    {busy && <p role="status">{negotiating ? 'Agents are considering the options… This may take up to two minutes.' : 'Working…'}</p>}
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status" className="rounded-lg bg-teal-50 p-3">{notice}</p>}
    {!loading && !error && overviews.length === 0 && <p>No plans yet. Choose New hangout to start.</p>}
    <div className="grid items-start gap-5 lg:grid-cols-[280px_1fr]">
      <div className="space-y-2" aria-label="Your hangout requests">
        {overviews.map(item => {
          const plans = visibleProposals(item.proposals.map(response => response.proposal));
          const focus = plans.find(plan => plan.status === 'approved' || plan.status === 'scheduled') || plans[0];
          return <button key={item.request.id} className={`demo-request ${selectedId === item.request.id ? 'demo-request-active' : ''}`} disabled={busy} aria-pressed={selectedId === item.request.id} onClick={() => {setSelectedId(item.request.id);setProposalId(null);setNotice('');setError('');}}>
            <span className="block font-semibold">{name(other(item.request))} · {focus?.activity || item.request.allowed_activities.join(', ')}</span>
            <span className="block text-sm">{focus ? dateTime(focus.slot.start,user.timezone) : dateTime(item.request.start,user.timezone) + ' – ' + dateTime(item.request.end,user.timezone)}</span>
            <span className="block text-sm">{item.request.location || 'Location to be arranged'} · {item.request.requester_id === user.id ? 'You invited them' : 'They invited you'}</span>
            <span className="mt-2 block text-sm font-semibold text-teal-800">{planStatus(item.proposals,user.id)}</span>
            <span className="block text-xs text-stone-500">Request {item.request.id.slice(-6)}</span>
          </button>;
        })}
      </div>
      <div className="space-y-5">
        {!selected && overviews.length > 0 && <p className="demo-choice">Choose a request to see its options and next step.</p>}
        {selected && <>
          <div className="demo-choice space-y-2">
            <h3>You and {name(other(selected.request))}</h3>
            <p>Search: {(selected.request.search_windows.length ? selected.request.search_windows : [selected.request]).map(window => `${dateTime(window.start,user.timezone)} – ${dateTime(window.end,user.timezone)}`).join('; ')}</p>
            <p>{selected.request.allowed_activities.join(', ')} · {selected.request.allowed_durations.join(', ')} minutes</p>
            {!agreed && <button className="demo-secondary" disabled={busy} onClick={() => revise(selected.request)}>Revise search in a new request</button>}
          </div>
          {visible.length > 0 && <div className="space-y-3">
            <h3>{agreed ? 'Your agreed plan' : 'Choose a proposed option'}</h3>
            {visible.map(item => <button className="demo-secondary mr-2 mb-2" aria-pressed={displayedId === item.id} key={item.id} disabled={busy} onClick={() => setProposalId(item.id)}>{item.activity} · {dateTime(item.slot.start,user.timezone)} · {(Date.parse(item.slot.end)-Date.parse(item.slot.start))/60_000} min</button>)}
            {displayed && <ProposalViewer key={displayed.proposal.id} user={user} users={users} value={displayed} onChange={updateProposal} onRefresh={() => void refresh()} />}
          </div>}
          {!agreed && <div className="space-y-3">
            {!visible.length && <p>No active proposal yet. Find times below or revise your search.</p>}
            <button disabled={busy || loading} onClick={() => askAgents(selected.request.id)}>Let agents suggest a plan</button>
            <p className="text-sm text-stone-600">Agent suggestions need both humans’ approval. Mock and fallback results are explicitly labeled.</p>
            <button disabled={busy || loading} onClick={() => findTimes(selected.request)}>{visible.length ? 'Find another option' : 'Find available times'}</button>
          </div>}
          {negotiation?.requestId === selected.request.id && <section className="demo-choice space-y-2" aria-label="Agent negotiation result">
            <h3>{negotiation.result.source === 'mock' ? 'Mock negotiation — no AI inference' : negotiation.result.source === 'demo_fallback' ? 'Deterministic fallback — not a full AI negotiation' : 'Local AI negotiation'}</h3>
            <p>{negotiation.result.status === 'agreed' ? 'Suggested plan saved. Both humans must approve before scheduling.' : negotiation.result.status === 'exhausted' ? 'The agents did not agree within the round limit. Try manual selection.' : 'No acceptable plan was found. Check availability or try manual selection.'}</p>
            <ol>{negotiation.result.turns.map((turn,index) => <li key={index}>{name(turn.actor_id)}’s agent: {turn.decision}{turn.activity ? ` · ${turn.activity}` : ''}{turn.slot ? ` · ${dateTime(turn.slot.start,user.timezone)}` : ''}</li>)}</ol>
          </section>}
          {options?.requestId === selected.request.id && !agreed && (options.items.length === 0 ? <div className="demo-choice space-y-3">
            <h3>No compatible times found</h3><p>Both people need compatible activities and duration, plus shared social windows or explicit calendar matching consent. Calendar conflicts and visibility also apply. Private reasons are not disclosed.</p>
            <div className="flex flex-wrap gap-2">
              <button className="demo-secondary" onClick={() => onNavigate('availability')}>Check my availability</button>
              <button className="demo-secondary" onClick={() => onNavigate('people')}>Check friendships</button>
              <button className="demo-secondary" onClick={() => revise(selected.request)}>Try different constraints</button>
            </div>
          </div> : <div className="space-y-3">
            <h3>Choose an exact plan</h3><p>Submitting counts as your approval. The other person still needs to approve.</p>
            {options.items.map(option => <CandidateChoice key={JSON.stringify(option)} option={option} timezone={user.timezone} disabled={busy} save={(activity, wallStart, duration) => {
              void run(async signal => {
                const start = zonedInputToISO(wallStart,user.timezone);
                const end = new Date(Date.parse(start)+duration*60_000).toISOString();
                if (Date.parse(start)<Date.parse(option.slot.start) || Date.parse(end)>Date.parse(option.slot.end)) throw new Error('The whole plan must fit inside this available interval.');
                const saved = await createProposal(user.id,selected.request.id,{activity,slot:{start,end}},signal);
                if (!signal.aborted) {setProposalId(saved.id);setOptions(null);setNotice('Proposed and approved by you. Switch demo users to respond as the other person.');await refresh();}
              });
            }} />)}
          </div>)}
        </>}
      </div>
    </div>
  </section>;
}
