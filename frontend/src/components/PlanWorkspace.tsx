import React from 'react';
import { negotiateHangout } from '../lib/api';
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
  const [workingId,setWorkingId] = React.useState<string|null>(null);
  const pending=React.useRef<AbortController|null>(null);
  const started=React.useRef<string|null>(null);
  React.useEffect(() => () => pending.current?.abort(),[]);
  async function run(id:string,negotiate:boolean) {
    if(pending.current) return;
    const controller=new AbortController();pending.current=controller;setBusy(true);setFailure('');
    if(negotiate) {setWorkingId(id);setResult(null);}
    try {
      if(negotiate) {
        const data=await negotiateHangout(user.id,id,controller.signal);
        if(!controller.signal.aborted) setResult({id,value:data});
      }
      await refresh(controller.signal);
    } catch(e) {if(!controller.signal.aborted) setFailure(e instanceof Error ? e.message : 'Could not find a plan. Your request is saved; you can retry.');}
    finally {if(!controller.signal.aborted) {pending.current=null;setBusy(false);setWorkingId(null);}}
  }
  React.useEffect(() => {
    if(autoRequest && started.current!==autoRequest) {
      started.current=autoRequest;onAutoStarted();void run(autoRequest,true);
    }
  },[autoRequest]);
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
      {failure && <p role="alert">{failure}</p>}
      {busy && <p role="status">{workingId?'Your agents are considering compatible plans. This can take up to two minutes.':'Refreshing…'}</p>}
      {!chosen && !busy && <p>Choose a conversation to see its suggested plan and next step.</p>}
      {chosen && <>
        <h2>You and {name(chosen.request.requester_id===user.id?chosen.request.invitee_id:chosen.request.requester_id)}</h2>
        <details className="search-details"><summary>What you’re planning</summary><p>{chosen.request.allowed_activities.join(' or ')} · {chosen.request.allowed_durations.join(' or ')} minutes</p>{(chosen.request.search_windows.length?chosen.request.search_windows:[chosen.request]).map(window => <p key={window.start}>{dateTime(window.start,user.timezone)} – {dateTime(window.end,user.timezone)}</p>)}</details>
        {result?.id===chosen.request.id && <div className="agent-summary">
          <p>{result.value.source==='local_agent'?(result.value.turns.length?'Your personal agents considered the options.':'Availability checked before contacting the agents.'):result.value.source==='mock'?'Mock agents · no AI inference':'Demo fallback · deterministic selection'}</p>
          {result.value.status==='no_match' && <p>No compatible plan was found. Check that your friend has shared social windows or enabled calendar matching, or try different days and activities. Private reasons stay private.</p>}
          {result.value.status==='exhausted' && <p>The agents did not agree within the round limit. You can try again or send a different idea.</p>}
          {result.value.turns.length>0 && <details><summary>See agent exchange</summary><ol>{result.value.turns.map((turn,index) => <li key={index}>{name(turn.actor_id)}’s agent: {turn.decision}{turn.activity?` · ${turn.activity}`:''}{turn.slot?` · ${dateTime(turn.slot.start,user.timezone)}`:''}</li>)}</ol></details>}
        </div>}
        {proposals.map(proposal => {
          const response=chosen.proposals.find(item => item.proposal.id===proposal.id)!;
          return <ProposalViewer calendarMode={calendarMode} calendarConnected={calendarConnected} key={proposal.id} user={user} users={users} value={response} onRefresh={() => void run('',false)} onChange={() => void run('',false)}/>;
        })}
        {!settled && !busy && <div className="space-y-3"><p>{proposals.length?'Want a different suggestion? Both people must approve whichever plan you choose.':'Ready to find a plan? Your request is saved.'}</p><button disabled={busy||loading||!active} onClick={() => void run(chosen.request.id,true)}>{proposals.length?'Ask agents for another option':'Ask agents to find a plan'}</button><p className="text-sm">Sending an idea isn’t approval of an exact time. You’ll both review the suggestion.</p></div>}
      </>}
    </section>
  </div>;
}
