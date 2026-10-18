import { useEffect, useState } from 'react';
import { api, USE_MOCKS } from '../api.js';
import { DAY_END_MINUTE, DAY_START_MINUTE, VISIBLE_HOURS, getBlockPosition, getDay, getDayRange, getLocalDateKey, getWeekDays, getWeekRange, shiftCalendarDate } from './scheduleTime.js';
import './ScheduleView.css';

const mockWeek = new Date('2026-10-18T12:00:00-04:00');

function timeLabel(hour) {
  const displayHour = hour % 12 || 12;
  return `${displayHour}${hour < 12 ? 'am' : 'pm'}`;
}

function ScheduleView({ userId, timezone = Intl.DateTimeFormat().resolvedOptions().timeZone, calendarMode="mock", ownerId=userId, onSelect }) {
  const [schedule, setSchedule] = useState(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [layers,setLayers] = useState({busy:true,social:true,proposal:true});
  const [view, setView] = useState('week');
  const [anchor, setAnchor] = useState(() => USE_MOCKS ? mockWeek : new Date());
  const range = view === 'week' ? getWeekRange(anchor, timezone) : getDayRange(anchor, timezone);
  const days = view === 'week' ? getWeekDays(anchor, timezone) : [getDay(anchor, timezone)].filter(Boolean);
  const rangeLabel = view === 'week'
    ? `Week of ${new Intl.DateTimeFormat('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: timezone }).format(new Date(range.start))}`
    : new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', timeZone: timezone }).format(anchor);

  useEffect(() => {
    let active = true;
    setSchedule(null);
    setError('');
    api.getSchedule(userId, range.start, range.end, undefined, ownerId)
      .then((result) => { if (active) setSchedule(result); })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : 'Could not load the schedule.'); });

    return () => { active = false; };
  }, [userId, ownerId, range.start, range.end, retry]);

  const blocks = [
    ...(schedule?.calendar_busy || []).map((item) => ({ ...item, type: 'busy' })),
    ...(schedule?.social_windows || []).map((item) => ({ ...item, type: 'social' })),
    ...(schedule?.proposals || []).map((item) => ({ ...item, type: 'proposal' })),
  ];
  const visibleBlocks = blocks.filter((block) => layers[block.type] && days.some((day) => getBlockPosition(block.start, block.end, day.key, timezone)));
  const navigationUnit = view === 'week' ? 7 : 1;

  return <section className="schedule-view" aria-labelledby="schedule-view-title" aria-label={`Schedule for ${userId}`}>
    <div className="schedule-view__heading">
      <div><h2 id="schedule-view-title">{view === 'week' ? 'This week’s schedule' : 'Day schedule'}</h2><span>{rangeLabel}</span></div>
      <div className="schedule-view__controls">
        <div className="schedule-view__modes" aria-label="Schedule view">
          <button type="button" aria-pressed={view === 'day'} onClick={() => setView('day')}>Day</button>
          <button type="button" aria-pressed={view === 'week'} onClick={() => setView('week')}>Week</button>
        </div>
        <button type="button" className="schedule-view__today" onClick={() => setAnchor(new Date())}>Today</button>
        <button type="button" className="schedule-view__step" aria-label={`Previous ${view}`} onClick={() => setAnchor((current) => shiftCalendarDate(current, -navigationUnit, timezone))}>‹</button>
        <button type="button" className="schedule-view__step" aria-label={`Next ${view}`} onClick={() => setAnchor((current) => shiftCalendarDate(current, navigationUnit, timezone))}>›</button>
      </div>
    </div>
    <div className="schedule-view__legend" aria-label="Calendar layers">
      {[['busy',calendarMode==='google'?'Google Calendar · busy':'Demo calendar · busy'],['social','Open to company'],['proposal','Mutual plans']].filter(([type])=>ownerId===userId||type!=='proposal').map(([type,label])=><button type="button" key={type} aria-pressed={layers[type]} className={`schedule-view__legend-item schedule-view__legend-item--${type}`} onClick={()=>setLayers(current=>({...current,[type]:!current[type]}))}><i aria-hidden="true"/>{label}</button>)}
    </div>
    <p className="schedule-view__caption">{timezone} · Calendar blocks show busy time only. {ownerId===userId?'Select a Mutual plan to review it.':'Select shared availability to request to join.'}</p>
    {schedule?.calendar_busy === null && <p className="schedule-view__state" role="status">Calendar busy times are not shared with this viewer.</p>}
    {error ? <div className="schedule-view__state" role="alert"><p>{error}</p><button type="button" onClick={() => setRetry((attempt) => attempt + 1)}>Retry</button></div>
      : !schedule ? <p className="schedule-view__state" role="status">Loading schedule…</p>
        : visibleBlocks.length === 0 ? <p className="schedule-view__state" role="status">Nothing on the schedule for this {view}.</p>
          : <div className="schedule-view__scroll">
      <div className={`schedule-view__grid schedule-view__grid--${view}`} style={{ '--day-count': days.length }}>
        <div className="schedule-view__corner" />
        {days.map((day) => <div className="schedule-view__day-heading" key={day.key}>
          <span>{day.label}</span><small>{day.date}</small>
        </div>)}
        <div className="schedule-view__time-axis">
          <div className="schedule-view__time-labels">{VISIBLE_HOURS.map((hour) => <span key={hour} style={{ top: `${((hour * 60 - DAY_START_MINUTE) / (DAY_END_MINUTE - DAY_START_MINUTE)) * 100}%` }}>{timeLabel(hour)}</span>)}</div>
        </div>
        {days.map((day) => <div className="schedule-view__day" key={day.key}>
          <div className="schedule-view__hour-lines" aria-hidden="true" />
          {visibleBlocks.map((block) => {
            const position = getBlockPosition(block.start, block.end, day.key, timezone);
            if (!position) return null;

            const label = block.type === 'busy'
              ? `${calendarMode==='google'?'Google Calendar':'Demo calendar'} · Busy`
              : block.type === 'social'
                ? `Available: ${block.title|| (block.allowed_activities || []).join(', ')}`
                : `${block.status === 'scheduled' ? 'Mutual hangout' : 'Suggested hangout'}: ${block.activity}, ${block.status}`;
            const proposalStyle = block.type === 'proposal'
              ? block.status === 'declined' || block.status === 'rejected'
                ? 'rejected'
                : block.status === 'approved' || block.status === 'scheduled'
                  ? block.status==='scheduled'?'scheduled':'approved'
                  : 'pending'
              : '';
            const selectedItem = block.type === 'social'
              ? { ...block, type: 'social_window' }
              : { ...block, type: 'proposal' };
            const blockClass = `schedule-view__block schedule-view__block--${block.type}${proposalStyle ? ` schedule-view__block--${proposalStyle}` : ''}`;

            return block.type === 'busy' ? <div
              key={`${block.type}-${block.start}`}
              className={blockClass}
              style={{ top: `${position.top}%`, height: `${position.height}%` }}
              aria-label={label}
              title={`${label} · ${new Intl.DateTimeFormat('en-US',{hour:'numeric',minute:'2-digit',timeZone:timezone}).format(new Date(block.start))}`}
            ><span>{calendarMode==='google'?'Google Calendar':'Calendar'}</span><small>Busy</small></div> : <button
              type="button"
              key={`${block.type}-${block.id || block.start}`}
              className={blockClass}
              style={{ top: `${position.top}%`, height: `${position.height}%` }}
              aria-label={label}
              title={label}
              onClick={() => onSelect?.(selectedItem)}
            >
              {block.type === 'social' && <><span>{block.title||'Open to company'}</span><small>{(block.allowed_activities || []).join(', ')}</small></>}
              {block.type === 'proposal' && <><span>{block.activity}</span><small>{block.status==='scheduled'?'Mutual · scheduled':block.status==='approved'?'Both approved':'Mutual · suggested'}</small></>}
            </button>;
          })}
        </div>)}
      </div>
    </div>}
  </section>;
}

export default ScheduleView;