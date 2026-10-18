import React from 'react';
import { negotiateHangout, getNegotiation } from '../lib/api';
import type { User, PublicUser, HangoutOverview, NegotiationResponse } from '../lib/api';
import { planAttention, planFingerprint } from '../lib/proposals';
import { visibleProposals } from '../lib/proposals';
import { dateTime } from '../lib/display';
import { ProposalViewer } from './ProposalViewer';

export function PlanWorkspace({calendarMode,calendarConnected,user,users,plans,selected,onSelect,focusRequest,seen,onReviewAll,autoRequest,onAutoStarted,active,refresh,loading,error}: {
  calendarMode:'mock'|'google';calendarConnected:boolean;
  user:User;users:PublicUser[];plans:HangoutOverview[];
  focusRequest?:string|null;seen:Record<string,string>;onReviewAll:()=>void;
  selected:string|null;onSelect:(id:string)=>void;autoRequest:string|null;onAutoStarted:()=>void;active:boolean;
  refresh:(signal:AbortSignal)=>Promise<void>;loading:boolean;error:string;
}) {
  const [filter,setFilter]=React.useState('all');
  React.useEffect(()=>{if(focusRequest)setFilter('joins');},[focusRequest]);
  const [busy,setBusy] = React.useState(false);
  const [failure,setFailure] = React.useState('');
  const [result,setResult] = React.useState<{id:string;value:NegotiationResponse}|null>(null);
  const [failedId,setFailedId] = React.useState<string|null>(null);
  const [workingId,setWorkingId] = React.useState<string|null>(null);
  const pending=React.useRef<AbortController|null>(null);
  const started=React.useRef<string|null>(null);
  const detail=React.useRef<HTMLElement|null>(null);
  React.useEffect(()=>{if(active&&selected&&window.matchMedia('(max-width:760px)').matches)detail.current?.scrollIntoView({behavior:'smooth',block:'start'});},[selected,active]);
  React.useEffect(() => () => pending.current?.abort(),[]);
  async function run(id:string,negotiate:boolean,variation:'any'|'different_time'='any') {
    if(pending.current) return;
    const controller=new AbortController();pending.current=controller;setBusy(true);setFailure('');
    if(negotiate) {setWorkingId(id);setResult(null);setFailedId(null);}
    try {
      if(negotiate) {
        const data=await negotiateHangout(user.id,id,controller.signal,variation);
        if(!controller.signal.aborted) setResult({id,value:data});
      }
      await refresh(controller.signal);
    } catch(e) {if(!controller.signal.aborted) {if(negotiate) setFailedId(id);setFailure(e instanceof Error ? e.message : 'Could not find a plan. Your request is saved; you can retry.');}}
    finally {if(!controller.signal.aborted) {pending.current=null;setBusy(false);setWorkingId(null);}}
  }
  React.useEffect(() => {
    if(autoRequest && started.current!==autoRequest) {
      started.current=autoRequest;onAutoStarted();void run(autoRequest,true);
    }
  },[autoRequest]);
  React.useEffect(() => {
    if(!selected) return;
    const controller=new AbortController();
    getNegotiation(user.id,selected,controller.signal).then(value => {
      if(!controller.signal.aborted && !pending.current && selected!==failedId) setResult(value?{id:selected,value}:null);
    }).catch(() => { /* Plan controls remain usable if exchange history cannot load. */ });
    return () => controller.abort();
  },[selected,user.id,failedId]);
  const updates=plans.filter(item=>seen[item.request.id]!==planFingerprint(item));
  const needsAction=plans.filter(item=>planAttention(item,user.id).action);
  const ready=plans.filter(item=>planAttention(item,user.id).kind==='schedule');
  const waiting=plans.filter(item=>planAttention(item,user.id).kind==='waiting');
  const shown=plans.filter(item=>filter==='all'||(filter==='action'&&planAttention(item,user.id).action)||(filter==='updates'&&seen[item.request.id]!==planFingerprint(item))||(filter==='waiting'&&planAttention(item,user.id).kind==='waiting')||(filter==='joins'&&!!item.request.join_window_id)||(filter==='ready'&&planAttention(item,user.id).kind==='schedule'))
    .sort((a,b)=>planAttention(a,user.id).priority-planAttention(b,user.id).priority||Number(seen[a.request.id]===planFingerprint(a))-Number(seen[b.request.id]===planFingerprint(b))||a.request.start.localeCompare(b.request.start));
  const chosen=plans.find(item => item.request.id===selected);
  const proposals=visibleProposals(chosen?.proposals.map(item => item.proposal)||[]);
  const settled=proposals.some(plan => plan.status==='approved'||plan.status==='scheduled');
  const name=(id:string) => users.find(person => person.id===id)?.display_name || id;
  function downloadNegotiation() {
    if (!chosen || result?.id!==chosen.request.id) return;
    const exchange=result.value;
    const lines=[
      'Mutual · recorded agent negotiation',
      'This export contains validated agent decisions, not private internal reasoning.',
      `Participants: ${name(chosen.request.requester_id)} and ${name(chosen.request.invitee_id)}`,
      `Timezone: ${user.timezone}`,
      `Source: ${exchange.source}`,
      `Outcome: ${exchange.status}`,
      `Eligible options: ${exchange.candidate_count ?? 'Not recorded'}`,
      ...(exchange.outcome_code ? [`Outcome detail: ${exchange.outcome_code}`] : []),
      '', 'Recorded exchange:',
      ...exchange.turns.map((turn,index)=>`${index+1}. ${name(turn.actor_id)}’s agent: ${turn.decision}${turn.activity?` · ${turn.activity}`:''}${turn.slot?` · ${dateTime(turn.slot.start,user.timezone)} – ${dateTime(turn.slot.end,user.timezone)}`:''}`),
      ...(!exchange.turns.length ? ['No agent turns recorded for this attempt.'] : []),
      '', 'Calendar and permission checks are enforced by the backend. Both people must approve the exact plan before scheduling.',
    ];
    const url=URL.createObjectURL(new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'}));
    const link=document.createElement('a');
    link.href=url;link.download=`mutual-negotiation-${chosen.request.id}.txt`;
    document.body.appendChild(link);link.click();link.remove();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return <div className="plans-workspace-shell">
    <div className="plan-activity-summary" aria-label="Plan activity summary">
      <button aria-pressed={filter==='action'} onClick={()=>setFilter('action')}><strong>{needsAction.length}</strong><span>Need your action</span></button>
      <button aria-pressed={filter==='updates'} onClick={()=>setFilter('updates')}><strong>{updates.length}</strong><span>New or updated</span></button>
      <button aria-pressed={filter==='waiting'} onClick={()=>setFilter('waiting')}><strong>{waiting.length}</strong><span>Waiting for others</span></button>
      <button aria-pressed={filter==='ready'} onClick={()=>setFilter('ready')}><strong>{ready.length}</strong><span>Ready for calendar</span></button>
    </div>
    <div className="plan-updates-toolbar"><div className="community-filters">{[['all','All plans'],['action','Needs action'],['updates','Updates'],['joins','Join requests'],['waiting','Waiting'],['ready','Ready to schedule']].map(([key,label])=><button key={key} aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label}</button>)}</div><button className="text-link" disabled={!updates.length} onClick={onReviewAll}>Mark updates seen</button></div>
    <p className="plan-live-note">Checks for changes every 15 seconds while this app is visible. Marking updates seen does not approve a plan.</p>
    <div className="plan-workspace">
    <section className="plan-inbox" aria-label="Hangout requests">
      <div className="flex items-center justify-between gap-2"><h2>Requests & plans</h2><button className="text-link" disabled={busy||loading} onClick={() => void run('',false)}>Refresh</button></div>
      {loading && <p role="status">Refreshing plans…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && !plans.length && <p>No plans yet. Choose Plan with someone to start.</p>}
      {!loading&&plans.length>0&&!shown.length&&<p>No plans in this filter. Choose All plans to see the rest.</p>}
      {shown.map(item => {
        const friend=item.request.requester_id===user.id?item.request.invitee_id:item.request.requester_id;
        const attention=planAttention(item,user.id);
        const unread=seen[item.request.id]!==planFingerprint(item);
        const day=new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',timeZone:user.timezone}).format(new Date(item.request.start));
        return <button key={item.request.id} className={`inbox-item ${selected===item.request.id?'selected':''} ${attention.action?'inbox-item--action':''} ${unread?'inbox-item--unread':''}`} aria-pressed={selected===item.request.id} onClick={() => onSelect(item.request.id)}>
          <span className="inbox-item-heading"><strong>{name(friend)}</strong>{unread&&<span className="plan-update-badge">{seen[item.request.id]?'Updated':'New'}</span>}</span><span>{item.request.join_window_title||item.request.allowed_activities.join(' or ')} · {item.request.join_window_id?dateTime(item.request.start,user.timezone):day}</span><span>{workingId===item.request.id?'Agents are finding a plan…':attention.label}</span>
        </button>;
      })}
    </section>
    <section ref={detail} className="demo-panel plan-detail" aria-label="Selected plan">
      {failure && (!failedId || failedId===selected) && <p role="alert">{failure}</p>}
      {busy && <p role="status">{workingId?'Your agents are considering compatible plans. This can take up to two minutes.':'Refreshing…'}</p>}
      {!chosen && !busy && <p>Choose a conversation to see its suggested plan and next step.</p>}
      {chosen && <>
        <div className={`plan-next-action plan-next-action--${planAttention(chosen,user.id).kind}`} role="status"><strong>{planAttention(chosen,user.id).label}</strong><p>{planAttention(chosen,user.id).kind==='respond'?'Review the exact plan below, then approve or decline.':planAttention(chosen,user.id).kind==='schedule'?'Both people approved. Add the plan to your calendar below.':planAttention(chosen,user.id).kind==='waiting'?'Your response is saved. This view refreshes when the other person responds.':planAttention(chosen,user.id).kind==='find'?'Choose a concrete plan for this invitation using the agents below.':'See the saved plan and decisions below.'}</p></div>
        {chosen.request.join_window_id&&<p className="join-request-kind">{chosen.request.invitee_id===user.id?'Incoming join request':'Your sent join request'}</p>}
        <h2>You and {name(chosen.request.requester_id===user.id?chosen.request.invitee_id:chosen.request.requester_id)}</h2>
        <details className="search-details"><summary>What you’re planning</summary><p>{chosen.request.allowed_activities.join(' or ')} · {chosen.request.allowed_durations.join(' or ')} minutes</p>{(chosen.request.search_windows.length?chosen.request.search_windows:[chosen.request]).map(window => <p key={window.start}>{dateTime(window.start,user.timezone)} – {dateTime(window.end,user.timezone)}</p>)}</details>
        {result?.id===chosen.request.id && failedId!==chosen.request.id && <div className="agent-summary">
          <button className="demo-secondary" onClick={downloadNegotiation}>Download negotiation (.txt)</button>
          <p>{result.value.source==='local_agent'?(result.value.turns.length?'Your personal agents considered the options.':'Availability checked before contacting the agents.'):result.value.source==='mock'?'Mock agents · no AI inference':'Demo fallback · deterministic selection'}</p>
          {result.value.candidate_count!=null && <p>{result.value.candidate_count} eligible options after social permissions, boundaries, and calendar conflict checks.</p>}
          {result.value.status==='no_match' && <p>{result.value.outcome_code==='no_new_options'?'No new options remain in this search. Your existing suggestions are still available; try different days or activities for more choices.':result.value.outcome_code==='no_eligible_options'?'No eligible options reached the agents. Check shared social windows or calendar-matching consent, or try different days and activities.': (result.value.turns.length===1 && result.value.turns[0].decision==='no_match'?'The requester’s agent did not suggest another plan. The other agent was not contacted. Your existing suggestions are still available.':'The agents did not find another agreement. Your existing suggestions are still available.')} Private reasons stay private.</p>}
          {result.value.status==='exhausted' && <p>The agents did not agree within the round limit. You can try again or send a different idea.</p>}
          {result.value.turns.length>0 && <details><summary>How the agents reached this plan</summary><p>These are the actual validated choices exchanged by the agents. Private notes and internal reasoning are never shown. Calendar checks and permissions are enforced by the backend; both people make the final decision.</p><ol>{result.value.turns.map((turn,index) => <li key={index}>{name(turn.actor_id)}’s agent: {turn.decision}{turn.activity?` · ${turn.activity}`:''}{turn.slot?` · ${dateTime(turn.slot.start,user.timezone)}`:''}</li>)}</ol></details>}
        </div>}
        {proposals.map(proposal => {
          const response=chosen.proposals.find(item => item.proposal.id===proposal.id)!;
          return <ProposalViewer calendarMode={calendarMode} calendarConnected={calendarConnected} key={proposal.id} user={user} users={users} value={response} onRefresh={() => void run('',false)} onChange={() => void run('',false)}/>;
        })}
        {chosen.request.join_window_id && <p className="text-sm">Requested from shared availability. To request another activity or time, return to the shared schedule and choose a new plan.</p>}
        {!settled && !busy && !chosen.request.join_window_id && <div className="space-y-3"><p>{proposals.length?'Want a different suggestion? Both people must approve whichever plan you choose.':'Ready to find a plan? Your request is saved.'}</p><button disabled={busy||loading||!active} onClick={() => void run(chosen.request.id,true)}>{proposals.length?'Different activity or time':'Ask agents to find a plan'}</button>{proposals.length>0 && <button className="demo-secondary" disabled={busy||loading||!active} onClick={() => void run(chosen.request.id,true,'different_time')}>Try a different time</button>}<p className="text-sm">“Different time” excludes every start time already suggested for this request.</p><p className="text-sm">Sending an idea isn’t approval of an exact time. You’ll both review the suggestion.</p></div>}
      </>}
    </section>
  </div></div>;
}
