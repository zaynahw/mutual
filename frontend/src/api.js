// Compatibility adapter for the calendar component from the frontend branch.
// Data comes from the same FastAPI client as the rest of the application.
import { getSchedule, listOverviews } from './lib/api';
import { visibleProposals } from './lib/proposals';
export const USE_MOCKS = false;
export const api = {
  async getSchedule(userId, start, end) {
    const controller = new AbortController();
    const [schedule, plans] = await Promise.all([
      getSchedule(userId,userId,{start,end},controller.signal),
      listOverviews(userId,controller.signal),
    ]);
    return {
      user_id: userId,
      busy_intervals: schedule.calendar_busy || [],
      social_windows: schedule.social_windows.map(window => ({...window,activity_types:window.allowed_activities})),
      proposals: plans.flatMap(item => visibleProposals(item.proposals.map(response => response.proposal)))
        .filter(plan => Date.parse(plan.slot.start)<Date.parse(end) && Date.parse(plan.slot.end)>Date.parse(start))
        .map(plan => ({id:plan.id,...plan.slot,activity:plan.activity,status:plan.status})),
    };
  },
};
