import React from 'react';
import FriendPicker from './FriendPicker.jsx';
import ScheduleView from './ScheduleView.jsx';
import { getSchedule, requestJoinWindow } from '../lib/api';
import type { Activity, HangoutOverview, ScheduleResponse, User } from '../lib/api';
import { dateTime } from '../lib/display';
import { isoToZonedInput, zonedInputToISO } from '../lib/time';

type Window = ScheduleResponse['social_windows'][number];
export function FriendSchedule({user,active,calendarMode,initialFriend,initialWindow,onRequested}: {
  user:User;active:boolean;calendarMode:'google'|'mock';initialFriend:string|null;initialWindow?:string|null;onRequested:(result:HangoutOverview)=>void;
}) {
  const [friend,setFriend]=React.useState(initialFriend||'');
  const [schedule,setSchedule]=React.useState<ScheduleResponse|null>(null);
  const [selected,setSelected]=React.useState<Window|null>(null);
  const [loading,setLoading]=React.useState(false);
  const [busy,setBusy]=React.useState(false);
  const [joinError,setJoinError]=React.useState('');
  const [error,setError]=React.useState('');
  const [reload,setReload]=React.useState(0);
  const joinPanel=React.useRef<HTMLElement|null>(null);
  React.useEffect(()=>{if(selected)joinPanel.current?.scrollIntoView({behavior:'smooth',block:'start'});},[selected]);
  const pending=React.useRef<AbortController|null>(null);
  React.useEffect(()=>()=>pending.current?.abort(),[]);
  React.useEffect(()=>{if(initialFriend&&active){setFriend(initialFriend);setSelected(null);}},[initialFriend,active]);
  React.useEffect(()=>{
    if(!active||!friend)return;
    const controller=new AbortController();setLoading(true);setSchedule(null);setSelected(null);setError('');setJoinError('');
    const now=new Date();
    getSchedule(user.id,friend,{start:now.toISOString(),end:new Date(now.getTime()+7*86400000).toISOString()},controller.signal)
      .then(data=>{if(!controller.signal.aborted)setSchedule(data);})
      .catch(e=>{if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Could not load shared schedule.');})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[active,friend,user.id,reload]);
  React.useEffect(()=>{if(schedule&&initialWindow){const match=schedule.social_windows.find(w=>w.id===initialWindow);if(match)setSelected(match);}},[schedule,initialWindow]);
  const activities=selected?.allowed_activities.filter(a=>user.hard_constraints.allowed_activities.includes(a))||[];
  const earliest=selected?new Date(Math.max(Date.parse(selected.start),Math.ceil((Date.now()+300000)/300000)*300000)).toISOString():'';
  return <section className="friend-schedule space-y-6">
    <div className="page-intro"><div><h1>Shared schedules</h1><p className="intro-date">See permitted social time. Pick a window and request to join.</p></div></div>
    <FriendPicker currentUserId={user.id} selectedFriendId={friend||null} active={active} disabled={busy} onSelect={person=>{setFriend(person.id);setSelected(null);}}/>
    {error&&<p role="alert">{error}</p>}
    {loading&&<p role="status">Loading their shared availability…</p>}
    {schedule&&<>
      <div className="community-toolbar"><h2>{schedule.user.display_name}’s shared time</h2><button disabled={busy||loading} className="text-link" onClick={()=>setReload(n=>n+1)}>Refresh shared schedule</button></div>
      <p className="community-note">Only windows they’ve allowed you to see appear. {schedule.calendar_busy===null?'Their calendar busy times are private.':'Their shared calendar blocks show busy time only.'}</p>
      {active&&<ScheduleView key={`${friend}-${reload}`} userId={user.id} ownerId={friend} timezone={user.timezone} calendarMode={calendarMode} onSelect={item=>{
        if(item.type==='social_window'){
          const match=schedule.social_windows.find(w=>w.id===item.id);if(match){setSelected(match);setError('');setJoinError('');}
        }
      }}/>}
      <h2>Open to company · next 7 days</h2>
      {!schedule.social_windows.length&&<p>No visible social windows in the next seven days. They can share one under Community or Availability.</p>}
      <div className="community-cards">{schedule.social_windows.map(window=><article className="community-card" key={window.id}>
        <h2>{window.title||window.allowed_activities.join(' or ')}</h2><p>{window.allowed_activities.join(' or ')}</p><p>{dateTime(window.start,user.timezone)}<br/>until {dateTime(window.end,user.timezone)}</p>
        <button className="primary-button" disabled={busy} onClick={()=>{setSelected(window);setError('');setJoinError('');}}>Request to join</button>
      </article>)}</div>
    </>}
    {selected&&<section ref={joinPanel} className="community-publish" aria-label="Request to join shared time">
      <h2>Join {schedule?.user.display_name} for {selected.title||selected.allowed_activities.join(' or ')}</h2>
      <p>Choose an exact activity, start, and duration inside their shared window. Your personal hours are {user.matching.start_hour}:00–{user.matching.end_hour}:00 in {user.timezone}. Calendars and both people’s boundaries are checked before sending.</p>
      <p className="join-not-sent">Not sent yet. Choose the exact plan below, then press Send join request.</p>
      {joinError&&<div role="alert" className="join-inline-error">{joinError}</div>}
      {!activities.length?<p>No shared activity fits your current activity boundaries.</p>:<form key={selected.id} className="demo-form" onSubmit={async e=>{
        e.preventDefault();if(pending.current)return;
        const values=new FormData(e.currentTarget);const controller=new AbortController();pending.current=controller;setBusy(true);setJoinError('');
        try {
          const start=zonedInputToISO(String(values.get('start')),user.timezone);
          const end=new Date(Date.parse(start)+Number(values.get('duration'))*60000).toISOString();
          const result=await requestJoinWindow(user.id,friend,selected.id,{activity:String(values.get('activity')) as Activity,slot:{start,end}},controller.signal);
          if(!controller.signal.aborted){setSelected(null);onRequested(result);}
        }catch(e){if(!controller.signal.aborted)setJoinError(e instanceof TypeError?'Could not confirm delivery. Your connection may have dropped; retry this same request safely.':e instanceof Error?`Request not sent: ${e.message}. Check both calendar connections and retry.`:'Request not sent. Please retry.');}
        finally{if(!controller.signal.aborted){pending.current=null;setBusy(false);}}
      }}>
        <label>Activity<select name="activity" disabled={busy}>{activities.map(a=><option key={a} value={a}>{a}</option>)}</select></label>
        <label>Start · {user.timezone}<input name="start" type="datetime-local" required disabled={busy} defaultValue={isoToZonedInput(earliest,user.timezone)} min={isoToZonedInput(earliest,user.timezone)} max={isoToZonedInput(selected.end,user.timezone)}/></label>
        <label>Duration<select name="duration" disabled={busy}>{[30,60,90,120].filter(n=>n<=user.hard_constraints.max_duration_minutes).map(n=><option key={n} value={n}>{n} minutes</option>)}</select></label>
        <p className="w-full">Each join request creates a two-person plan. Sending does not approve or book it. Both of you review the exact plan under My plans.</p>
        <button disabled={busy}>{busy?'Checking and sending…':'Send join request'}</button>
        <button type="button" className="demo-secondary" disabled={busy} onClick={()=>setSelected(null)}>Cancel</button>
      </form>}
    </section>}
  </section>;
}
