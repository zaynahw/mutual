import React from 'react';
import { updateCommunity } from '../lib/api';
import type { User } from '../lib/api';

export function CommunityMembership({user,onSaved}:{user:User;onSaved:(user:User)=>void}) {
  const [busy,setBusy]=React.useState(false);
  const [error,setError]=React.useState('');
  const pending=React.useRef<AbortController|null>(null);
  React.useEffect(()=>()=>pending.current?.abort(),[]);
  return <section className="community-membership" aria-label="Community membership">
    <strong>Georgia Tech community</strong>
    <span>{user.community==='georgia_tech'?'Member · open MVP community':'Not joined'}</span>
    <p>For this hackathon, membership is self-selected and is not proof of student status. Community-shared windows are visible to everyone who joins. Friends-only windows stay limited to accepted friends.</p>
    <button className="demo-secondary" disabled={busy} onClick={async()=>{
      if(pending.current)return;
      const controller=new AbortController();pending.current=controller;setBusy(true);setError('');
      try {const updated=await updateCommunity(user.id,user.community==='georgia_tech'?null:'georgia_tech',controller.signal);if(!controller.signal.aborted)onSaved(updated);}
      catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Could not change membership.');}
      finally{if(!controller.signal.aborted){pending.current=null;setBusy(false);}}
    }}>{busy?'Saving…':user.community==='georgia_tech'?'Leave community':'Join Georgia Tech community'}</button>
    {error&&<p role="alert">{error}</p>}
  </section>;
}
