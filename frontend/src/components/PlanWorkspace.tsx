import React from 'react';
import { negotiateHangout, getNegotiation } from '../lib/api';
import type { User, PublicUser, HangoutOverview, NegotiationResponse } from '../lib/api';
import { visibleProposals, planStatus } from '../lib/proposals';
import { dateTime } from '../lib/display';
import { ProposalViewer } from './ProposalViewer';

export function PlanWorkspace({calendarMode,calendarConnected,user,users,plans,selected,onSelect,autoRequest,onAutoStarted,active,refresh,loading,error}: {
  calendarMode:'mock'|'google';calendarConnected:boolean;
  user:User;users:PublicUser[];plans:HangoutOverview[];
  selected:string|null;onSelect:(id:string)=>void;autoRequest:string|null;onAutoStarted:()=>void;active:boolean;
  refresh:(signal:AbortSignal)=>Promise<void>;loading:boolean;error:string;
}) {
  const [busy,setBusy] = React.useState(false);
  const [failure,setFailure] = React.useState('');
  const [result,setResult] = React.useState<{id:string;value:NegotiationResponse}|null>(null);
  const [failedId,setFailedId] = React.useState<string|null>(null);
  const [workingId,setWorkingId] = React.useState<string|null>(null);
  const pending=React.useRef<AbortController|null>(null);
  const started=React.useRef<string|null>(null);
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
  const chosen=plans.find(item => item.request.id===selected);
  const proposals=visibleProposals(chosen?.proposals.map(item => item.proposal)||[]);
  const settled=proposals.some(plan => plan.status==='approved'||plan.status==='scheduled');
  const name=(id:string) => users.find(person => person.id===id)?.display_name || id;
  return <div className="plan-workspace">
    <section className="plan-inbox" aria-label="Hangout requests">
      <div className="flex items-center justify-between gap-2"><h2>Conversations</h2><button className="text-link" disabled={busy||loading} onClick={() => void run('',false)}>Refresh</button></div>
      {loading && <p role="status">Refreshing plans…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && !plans.length && <p>No plans yet. Choose Plan with someone to start.</p>}
      {plans.map(item => {
        const friend=item.request.requester_id===user.id?item.request.invitee_id:item.request.requester_id;
        const day=new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',timeZone:user.timezone}).format(new Date(item.request.start));
        return <button key={item.request.id} className={`inbox-item ${selected===item.request.id?'selected':''}`} aria-pressed={selected===item.request.id} onClick={() => onSelect(item.request.id)}>
          <strong>{name(friend)}</strong><span>{item.request.allowed_activities.join(' or ')} · {day}</span><span>{workingId===item.request.id?'Agents are finding a plan…':planStatus(item.proposals,user.id)}</span>
        </button>;
      })}
    </section>
    <section className="demo-panel plan-detail" aria-label="Selected plan">
      {failure && (!failedId || failedId===selected) && <p role="alert">{failure}</p>}
      {busy && <p role="status">{workingId?'Your agents are considering compatible plans. This can take up to two minutes.':'Refreshing…'}</p>}
      {!chosen && !busy && <p>Choose a conversation to see its suggested plan and next step.</p>}
      {chosen && <>
        <h2>You and {name(chosen.request.requester_id===user.id?chosen.request.invitee_id:chosen.request.requester_id)}</h2>
        <details className="search-details"><summary>What you’re planning</summary><p>{chosen.request.allowed_activities.join(' or ')} · {chosen.request.allowed_durations.join(' or ')} minutes</p>{(chosen.request.search_windows.length?chosen.request.search_windows:[chosen.request]).map(window => <p key={window.start}>{dateTime(window.start,user.timezone)} – {dateTime(window.end,user.timezone)}</p>)}</details>
        {result?.id===chosen.request.id && failedId!==chosen.request.id && <div className="agent-summary">
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
        {!settled && !busy && <div className="space-y-3"><p>{proposals.length?'Want a different suggestion? Both people must approve whichever plan you choose.':'Ready to find a plan? Your request is saved.'}</p><button disabled={busy||loading||!active} onClick={() => void run(chosen.request.id,true)}>{proposals.length?'Different activity or time':'Ask agents to find a plan'}</button>{proposals.length>0 && <button className="demo-secondary" disabled={busy||loading||!active} onClick={() => void run(chosen.request.id,true,'different_time')}>Try a different time</button>}<p className="text-sm">“Different time” excludes every start time already suggested for this request.</p><p className="text-sm">Sending an idea isn’t approval of an exact time. You’ll both review the suggestion.</p></div>}
      </>}
    </section>
  </div>;
}
