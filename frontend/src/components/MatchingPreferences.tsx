import React from 'react';
import { updateMatching } from '../lib/api';
import type { User } from '../lib/api';

export function MatchingPreferences({user,onSaved}: {user: User; onSaved:(user:User)=>void}) {
  const [settings,setSettings] = React.useState(user.matching);
  React.useEffect(() => setSettings(user.matching), [user.matching]);
  const [busy,setBusy] = React.useState(false);
  const [notice,setNotice] = React.useState('');
  const pending=React.useRef<AbortController|null>(null);
  React.useEffect(() => () => pending.current?.abort(),[]);
  return <section className="demo-panel space-y-3">
    <h2>How friends can find time with me</h2>
    <p>Calendar matching is optional and off by default. This setting permits matching with accepted friends; it does not share your calendar view or event details.</p>
    <form className="demo-form" onSubmit={async e => {
      e.preventDefault(); if(pending.current) return;
      const controller=new AbortController();pending.current=controller;setBusy(true);setNotice('');
      try { const updated=await updateMatching(user.id,settings,controller.signal);if(!controller.signal.aborted) {onSaved(updated);setNotice('Matching settings saved.');} }
      catch(error) {if(!controller.signal.aborted) setNotice(error instanceof Error ? error.message : 'Could not save.');}
      finally {if(!controller.signal.aborted) {pending.current=null;setBusy(false);}}
    }}>
      <label>Matching mode<select disabled={busy} value={settings.mode} onChange={e => setSettings({...settings,mode:e.target.value as User['matching']['mode']})}>
        <option value="social_windows">Only my shared social windows</option>
        <option value="calendar_guided">Let friends’ agents use my calendar-free time</option>
      </select></label>
      <label>Personal hours start<input type="number" min={0} max={23} required disabled={busy} value={settings.start_hour} onChange={e => setSettings({...settings,start_hour:Number(e.target.value)})}/></label>
      <label>End (24 = midnight)<input type="number" min={settings.start_hour+1} max={24} required disabled={busy} value={settings.end_hour} onChange={e => setSettings({...settings,end_hour:Number(e.target.value)})}/></label>
      <p className="w-full text-sm">Hours use {user.timezone}. Existing activity and duration boundaries still apply. For a request you send, confirming the interpretation grants matching within these hours for that request.</p>
      <button disabled={busy}>{busy ? 'Saving…' : 'Save my matching choice'}</button>
    </form>
    {notice && <p role="status">{notice}</p>}
  </section>;
}
