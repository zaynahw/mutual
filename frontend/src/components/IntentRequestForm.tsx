import React from 'react';
import { interpretIntent, sendIntent, listFriendRequests } from '../lib/api';
import type { IntentDraft, PublicUser, User, HangoutRequest, AvailabilityCard } from '../lib/api';
import FriendPicker from './FriendPicker.jsx';
import { isoToZonedInput } from '../lib/time';

export function IntentRequestForm({user, users, onSaved, active=true, initialIdea}: {initialIdea?:AvailabilityCard|null;active?:boolean; user: User; users: PublicUser[]; onSaved: (request: HangoutRequest) => void}) {
  const today = isoToZonedInput(new Date().toISOString(),user.timezone).slice(0,10);
  const nextDay = (offset: number) => new Date(Date.parse(`${today}T12:00:00Z`)+offset*86400000).toISOString().slice(0,10);
  const [friends,setFriends] = React.useState<string[]>([]);
  const [invitee,setInvitee] = React.useState('');
  const [days,setDays] = React.useState<string[]>([today]);
  const [message,setMessage] = React.useState('Something chill, like a walk or food. I prefer earlier in the morning.');
  const [preview,setPreview] = React.useState<IntentDraft|null>(null);
  const [busy,setBusy] = React.useState(false);
  const [error,setError] = React.useState('');
  const pending = React.useRef<AbortController|null>(null);
  React.useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    listFriendRequests(user.id,controller.signal).then(items => {
      const ids = items.filter(item => item.status === 'accepted').map(item => item.sender_id === user.id ? item.recipient_id : item.sender_id);
      setFriends(ids); setInvitee(current => ids.includes(current) ? current : ids[0] || '');
    }).catch(e => {if (!controller.signal.aborted) setError(e.message);});
    return () => controller.abort();
  },[user.id,active]);
  React.useEffect(() => {
    if(!initialIdea) return;
    setInvitee(initialIdea.owner.id);
    const start=isoToZonedInput(initialIdea.window.start,user.timezone);
    const end=isoToZonedInput(initialIdea.window.end,user.timezone);
    setDays([start.slice(0,10)]);
    const range=start.slice(0,10)===end.slice(0,10)?` between ${start.slice(11,16)} and ${end.slice(11,16)}`:'';
    setMessage(`I'd like ${initialIdea.window.allowed_activities.join(' or ')}${range}.`);
    setPreview(null);setError('');
  },[initialIdea,user.timezone]);
  React.useEffect(() => () => pending.current?.abort(),[]);
  function change() { setPreview(null); setError(''); }
  async function submit(send: boolean) {
    if (pending.current) return;
    const controller = new AbortController(); pending.current = controller; setBusy(true); setError('');
    try {
      if (send && preview) { const request = await sendIntent(user.id,preview.id,controller.signal); if (!controller.signal.aborted) {setPreview(null);setMessage('');onSaved(request);} }
      else { const result = await interpretIntent(user.id,{invitee_id:invitee,days,message},controller.signal); if (!controller.signal.aborted) setPreview(result); }
    } catch(e) {if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not prepare request.');}
    finally {if (!controller.signal.aborted) {pending.current = null;setBusy(false);}}
  }
  const parsed = preview?.result.interpretation;
  return <section className="demo-choice space-y-4">
    <p>Tell your agent what sounds good. It will find a plan that also fits your friend’s availability and preferences.</p>
    <form className="demo-form" onSubmit={e => {e.preventDefault(); void submit(false);}}>
      <div className="w-full"><FriendPicker currentUserId={user.id} selectedFriendId={invitee||null} disabled={busy} active={active} onSelect={friend=>{setInvitee(friend.id);change();}}/></div>
      <fieldset disabled={busy} className="w-full space-y-2"><legend>Which days? · {user.timezone}</legend>
        <div className="flex gap-2">{[[today,'Today'],[nextDay(1),'Tomorrow']].map(([day,label]) => <label key={day}><input type="checkbox" checked={days.includes(day)} onChange={() => {setDays(current => current.includes(day) ? current.filter(d => d!==day) : [...current,day].sort());change();}} /> {label}</label>)}</div>
        <label>Add a specific date<input type="date" min={today} max={nextDay(14)} value="" onChange={e => {const day=e.target.value;if(day && !days.includes(day) && days.length<7) {setDays([...days,day].sort());change();}}}/></label>
        <div className="flex flex-wrap gap-2">{days.map(day => <button type="button" className="demo-secondary" key={day} onClick={() => {setDays(days.filter(d => d!==day));change();}}>{day} ×</button>)}</div>
      </fieldset>
      <label className="w-full">What do you have in mind?<textarea required maxLength={1000} rows={3} disabled={busy} value={message} onChange={e => {setMessage(e.target.value);change();}} /></label>
      <p className="w-full text-sm text-stone-600">“Prefer mornings” is flexible. “Only before noon” is a requirement. Supported activities: coffee, meal, walk, study, concert.</p>
      <button disabled={busy || !invitee || !days.length || days.length>7 || !message.trim()}>{busy ? 'Working…' : 'Review what my agent understood'}</button>
    </form>
    {!friends.length && <p>Accept a friendship in People first.</p>}
    {error && <p role="alert">{error}</p>}
    {parsed && <section className="space-y-3 rounded-lg bg-teal-50 p-4" aria-label="Confirm interpretation">
      <h3>Check before sending</h3>
      <p>{preview!.result.source === 'local_agent' ? 'Interpreted by local AI' : preview!.result.source === 'mock' ? 'Mock interpretation · no AI inference' : 'Deterministic fallback interpretation'}</p>
      <p>{days.join(', ')} · {parsed.activities.join(', ')} · {parsed.allowed_durations.join(' or ')} minutes</p>
      <p>Flexible preference: {parsed.preferred_periods.join(', ') || 'any time'}.</p>
      <p>Your request limits: {parsed.earliest ? `after ${parsed.earliest}` : 'no earliest limit'}; {parsed.latest ? `before ${parsed.latest}` : 'no latest limit'} ({user.timezone}).</p>
      {parsed.clarification ? <p role="status">Please edit your message: {parsed.clarification}</p> : <>
        <p className="text-sm">We’ll search within your saved personal hours, {user.matching.start_hour}:00–{user.matching.end_hour}:00 ({user.timezone}), and your request limits. {parsed.earliest && Number(parsed.earliest.slice(0,2)) < user.matching.start_hour ? `Your saved start time is later than ${parsed.earliest}, so the search starts at ${user.matching.start_hour}:00. Change it under Availability if you want earlier plans.` : ''} {parsed.latest && Number(parsed.latest.slice(0,2)) > user.matching.end_hour ? `Your saved end time is earlier than ${parsed.latest}, so the search ends at ${user.matching.end_hour}:00. Change it under Availability if you want later plans.` : ''} Your friend also needs shared availability or calendar matching enabled. Both of you approve the final plan.</p>
        <button disabled={busy} onClick={() => void submit(true)}>Confirm and ask agents</button>
      </>}
    </section>}
  </section>;
}
