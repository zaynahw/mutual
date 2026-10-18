import React from 'react';
import type { AvailabilityCard } from '../lib/api';
import { connectionKind, layoutCommunityDay } from '../lib/community';
import { dateTime } from '../lib/display';
import { DAY_START_MINUTE, DAY_END_MINUTE, VISIBLE_HOURS, getDay, shiftCalendarDate } from './scheduleTime.js';
import './ScheduleView.css';

export function CommunityCalendar({cards,userId,friends,timezone,onSelect}:{
  cards:AvailabilityCard[];userId:string;friends:Set<string>;timezone:string;onSelect:(card:AvailabilityCard)=>void;
}) {
  const [anchor]=React.useState(()=>new Date());
  const days=Array.from({length:7},(_,n)=>getDay(shiftCalendarDate(anchor,n,timezone),timezone)).filter((day):day is NonNullable<typeof day>=>!!day);
  return <section className="schedule-view community-calendar" aria-label="Friends and community calendar">
    <div className="schedule-view__heading"><div><h2>Everyone’s shared time</h2><span>Next 7 days · {timezone}</span></div></div>
    <div className="community-calendar-legend"><span className="connection-badge connection-badge--friend">Friends</span><span className="connection-badge connection-badge--community">Community members</span><span className="connection-badge connection-badge--own">Your windows</span></div>
    <p className="schedule-view__caption">Select a shared window to request to join. Only availability shared with you appears; full times and join buttons are listed below.</p>
    <div className="schedule-view__scroll"><div className="schedule-view__grid" style={{'--day-count':days.length} as React.CSSProperties}>
      <div/>{days.map(day=><div className="schedule-view__day-heading" key={day.key}><span>{day.label}</span><small>{day.date}</small></div>)}
      <div className="schedule-view__time-axis"><div className="schedule-view__time-labels">{VISIBLE_HOURS.map(hour=><span key={hour} style={{top:`${(hour*60-DAY_START_MINUTE)/(DAY_END_MINUTE-DAY_START_MINUTE)*100}%`}}>{hour%12||12}{hour<12?'am':'pm'}</span>)}</div></div>
      {days.map(day=><div className="schedule-view__day" key={day.key}><div className="schedule-view__hour-lines" aria-hidden="true"/>
        {layoutCommunityDay(cards,day.key,timezone).map(({card,position,lane,lanes})=>{
          const kind=connectionKind(card,userId,friends);
          const label=`${card.owner.id===userId?'You':card.owner.display_name} · ${card.window.title||card.window.allowed_activities.join(' or ')} · ${dateTime(card.window.start,timezone)} · ${kind==='friend'?'Friend':kind==='own'?'Your window':'Community member'}`;
          return <button type="button" key={card.window.id} className={`schedule-view__block community-calendar-block community-calendar-block--${kind}`} style={{top:`${position.top}%`,height:`${position.height}%`,left:`calc(${lane/lanes*100}% + 2px)`,width:`calc(${100/lanes}% - 4px)`}} aria-label={label} title={label} onClick={()=>onSelect(card)}>
            <span>{card.owner.id===userId?'You':card.owner.display_name.replace(/\s*\(demo\)/,'')}</span><small>{card.window.title||card.window.allowed_activities.join(', ')}</small><small>{kind==='friend'?'Friend':kind==='own'?'Your window':'Community'}</small>
          </button>;
        })}
      </div>)}
    </div></div>
  </section>;
}
