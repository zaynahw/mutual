import React from 'react';
import { createMyWindow, getAvailabilityBoard, listFriendRequests, sendFriendRequest } from '../lib/api';
import type { Activity, AvailabilityCard, FriendRequest, HangoutOverview, PublicUser, User } from '../lib/api';
import { dateTime } from '../lib/display';
import { isoToZonedInput, zonedInputToISO } from '../lib/time';
import './CommunityBoard.css';
import { CommunityCalendar } from './CommunityCalendar';
import { planAttention } from '../lib/proposals';
import { connectionKind } from '../lib/community';
import { CommunityMembership } from './CommunityMembership';

export function CommunityBoard({user,active,onPlan,onFriends,onSchedule,onUserSaved,onBrowseFriends,plans,onOpenPlan,users}: {
  users:PublicUser[];plans:HangoutOverview[];onOpenPlan:(id:string)=>void;user:User;active:boolean;onPlan:(card:AvailabilityCard)=>void;onFriends:()=>void;onSchedule:(id:string,windowId?:string)=>void;onBrowseFriends:()=>void;onUserSaved:(user:User)=>void;
}) {
  const [cards,setCards]=React.useState<AvailabilityCard[]>([]);
  const [relationships,setRelationships]=React.useState<FriendRequest[]>([]);
  const [loading,setLoading]=React.useState(false);
  const [busy,setBusy]=React.useState(false);
  const [error,setError]=React.useState('');
  const [notice,setNotice]=React.useState('');
  const [reload,setReload]=React.useState(0);
  const [peopleFilter,setPeopleFilter]=React.useState('all');
  const [filter,setFilter]=React.useState('all');
  const pending=React.useRef<AbortController|null>(null);
  React.useEffect(()=>()=>pending.current?.abort(),[]);
  React.useEffect(()=>{
    if(!active) return;
    const controller=new AbortController();setLoading(true);setError('');
    const now=new Date();
    Promise.all([getAvailabilityBoard(user.id,now.toISOString(),new Date(now.getTime()+7*86400000).toISOString(),controller.signal),listFriendRequests(user.id,controller.signal)])
      .then(([items,friends])=>{if(!controller.signal.aborted){setCards(items);setRelationships(friends);}})
      .catch(e=>{if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Could not load shared availability.');})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[active,user.id,user.community,reload]);
  async function act(action:(signal:AbortSignal)=>Promise<unknown>,message:string) {
    if(pending.current)return;
    const controller=new AbortController();pending.current=controller;setBusy(true);setError('');setNotice('');
    try {await action(controller.signal);if(!controller.signal.aborted){setNotice(message);setReload(n=>n+1);}}
    catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Could not save.');}
    finally {if(!controller.signal.aborted){pending.current=null;setBusy(false);}}
  }
  const friends=new Set(relationships.filter(r=>r.status==='accepted').map(r=>r.sender_id===user.id?r.recipient_id:r.sender_id));
  const joinRequests=plans.filter(p=>p.request.join_window_id);
  const shown=cards.filter(card=>(filter==='all'||card.window.allowed_activities.includes(filter as Activity))&&(peopleFilter==='all'||connectionKind(card,user.id,friends)===peopleFilter));
  function openWindow(card:AvailabilityCard){if(card.owner.id===user.id){setNotice('This is your shared window. Edit or remove it under Availability.');}else onSchedule(card.owner.id,card.window.id);}

  return <section className="community-board">
    <div className="community-hero"><div><span className="community-eyebrow">A LITTLE MORE TOGETHER</span><h1>Your community, together</h1><p>A coffee between classes. A walk with company. Discover time people have chosen to share.</p></div><span className="community-orbit" aria-hidden="true">✳</span></div>
    <div className="community-toolbar"><button className="demo-secondary" onClick={onBrowseFriends}>Browse a friend’s schedule</button><p>Friends & community · next 7 days</p><button className="text-link" disabled={loading||busy} onClick={()=>setReload(n=>n+1)}>Refresh</button></div>
    {joinRequests.length>0&&<section className="community-join-inbox" aria-label="Community join requests"><h2>Your join requests · {joinRequests.length}</h2><p>Sent requests and requests to your shared windows are also saved in My plans.</p>{joinRequests.slice().sort((a,b)=>planAttention(a,user.id).priority-planAttention(b,user.id).priority).map(item=><button key={item.request.id} onClick={()=>onOpenPlan(item.request.id)}><span><strong>{item.request.invitee_id===user.id?`${users.find(p=>p.id===item.request.requester_id)?.display_name||'A member'} requested to join`:`Your request to ${users.find(p=>p.id===item.request.invitee_id)?.display_name||'a member'}`}</strong> · {item.request.join_window_title||item.request.allowed_activities.join(' or ')}</span><small>{planAttention(item,user.id).label} ↗</small></button>)}</section>}
    <CommunityMembership user={user} onSaved={onUserSaved}/>
    <details className="community-publish"><summary>+ Share a time you’re open to company</summary>
      <p>Publish social availability, then agree on an exact plan together. This does not create an event or RSVP.</p>
      <form className="demo-form" onSubmit={e=>{e.preventDefault();const form=e.currentTarget;const values=new FormData(form);void act(async signal=>{
        const startISO=zonedInputToISO(String(values.get('start')),user.timezone),endISO=zonedInputToISO(String(values.get('end')),user.timezone);
        if(Date.parse(startISO)<=Date.now())throw new Error('Choose a future start time.');
        if(Date.parse(endISO)<=Date.parse(startISO))throw new Error('End must be after start.');
        await createMyWindow(user.id,{start:startISO,end:endISO,title:String(values.get('title')||'').trim()||null,allowed_activities:[String(values.get('activity')) as Activity],visibility:{audience:String(values.get('audience')) as 'friends'|'community',selected_friend_ids:[]},sharing_mode:'visible'},signal);
        if(!signal.aborted)form.reset();
      },'Your availability is shared. You can edit or remove it under Availability.');}}>
        <label>Activity<select name="activity" disabled={busy} defaultValue={user.hard_constraints.allowed_activities[0]}>{user.hard_constraints.allowed_activities.map(a=><option key={a} value={a}>{a}</option>)}</select></label>
        <label>Concert artist or plan name (optional)<input name="title" maxLength={100} disabled={busy} placeholder="e.g. Laufey concert, coffee at the student center"/></label>
        <label>Start · {user.timezone}<input name="start" type="datetime-local" min={isoToZonedInput(new Date().toISOString(),user.timezone)} required disabled={busy}/></label>
        <label>End<input name="end" type="datetime-local" required disabled={busy}/></label>
        <label>Who can see it?<select name="audience" disabled={busy} defaultValue="friends"><option value="friends">Accepted friends</option><option value="community" disabled={!user.community}>Georgia Tech community</option></select></label>
        <button disabled={busy}>{busy?'Sharing…':'Share availability'}</button>
      </form>
    </details>
    <div className="community-filters" aria-label="Filter people">{[['all','Everyone'],['friend','Friends'],['community','Community members'],['own','My windows']].map(([key,label])=><button key={key} aria-pressed={peopleFilter===key} onClick={()=>setPeopleFilter(key)}>{label}</button>)}</div>
    <div className="community-filters" aria-label="Filter activities">{['all','coffee','walk','meal','study','concert'].map(a=><button key={a} aria-pressed={filter===a} onClick={()=>setFilter(a)}>{a==='all'?'Everything':a}</button>)}</div>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {!loading&&!error&&<CommunityCalendar cards={shown} userId={user.id} friends={friends} timezone={user.timezone} onSelect={openWindow}/>}
    <h2 className="community-list-heading">Joinable windows · {shown.length} shared</h2>
    {loading?<p role="status">Finding shared moments…</p>:!shown.length?<div className="community-empty"><h2>Make the first move.</h2><p>No shared windows for this filter yet. Publish a future time or invite a friend to share theirs.</p></div>:<div className="community-cards">{shown.map(card=>{
      const mine=card.owner.id===user.id;
      const pair=relationships.filter(r=>[r.sender_id,r.recipient_id].includes(card.owner.id));
      const friend=pair.some(r=>r.status==='accepted');
      const kind=connectionKind(card,user.id,friends);
      const pendingRequest=pair.find(r=>r.status==='pending');
      return <article className="community-card" key={card.window.id}>
        <div className="community-card-top"><span className="community-avatar" aria-hidden="true">{card.owner.display_name.slice(0,1).toUpperCase()}</span><span><strong>{mine?'You':card.owner.display_name}</strong><small>{card.audience==='community'?'Shared with community':'Shared with friends'}</small></span></div>
        <span className={`connection-badge connection-badge--${kind}`}>{kind==='friend'?'Friend':kind==='own'?'Your window':'Community member'}</span>
        <h2>{card.window.title||card.window.allowed_activities.join(' or ')}<span className="community-open">Open to company</span></h2>
        <p>{dateTime(card.window.start,user.timezone)}<br/>until {dateTime(card.window.end,user.timezone)}</p>
        <p className="community-card-note">Shared social availability · calendars checked when planning</p>
        {mine?<span className="community-own">Your shared window</span>:friend?<div className="space-y-3"><button className="primary-button" disabled={busy} onClick={()=>openWindow(card)}>Request to join ↗</button><button className="text-link" disabled={busy} onClick={()=>onPlan(card)}>Ask agents to plan instead</button></div>:card.audience==='community'?<button className="primary-button" disabled={busy} onClick={()=>openWindow(card)}>Request to join ↗</button>:pendingRequest?<button className="text-link" disabled={pendingRequest.sender_id===user.id} onClick={onFriends}>{pendingRequest.sender_id===user.id?'Friend request sent':'Review friend request'}</button>:<button className="primary-button" disabled={busy} onClick={()=>void act(signal=>sendFriendRequest(user.id,card.owner.id,signal),'Friend request sent. Once accepted, you can plan together.')}>Connect to plan</button>}
      </article>;
    })}</div>}
    <p className="community-note">Only explicitly shared windows appear. Connecting is not approval of a hangout; both people still approve the final plan.</p>
  </section>;
}
