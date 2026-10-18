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
import examples from '../../contracts/examples.json';

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const FRIENDS_ENDPOINT = (userId) => `${API_BASE_URL}/users/${encodeURIComponent(userId)}/friends`;
const SOCIAL_WINDOWS_ENDPOINT = `${API_BASE_URL}/users/me/social-windows`;
let mockSocialWindowId = 0;

const dashboardMock = {
  user: {
    id: 'demo-alex',
    display_name: 'Alex',
    is_demo: true,
    timezone: 'America/New_York',
    activity_preferences: ['Coffee'],
  },
  upcoming_proposals: [
    {
      id: 'proposal-demo-1',
      request_id: 'request-demo-1',
      activity: 'Coffee',
      other_person: 'Sam',
      slot: { start: '2026-10-18T15:00:00-04:00', end: '2026-10-18T16:00:00-04:00' },
      status: 'pending',
    },
    {
      id: 'proposal-demo-2',
      request_id: 'request-demo-2',
      activity: 'Coffee',
      other_person: 'Sam',
      slot: { start: '2026-10-20T17:30:00-04:00', end: '2026-10-20T18:30:00-04:00' },
      status: 'approved',
    },
  ],
};

async function checkHealth() {
  if (USE_MOCKS) return { status: 'ok' };

  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) throw new Error('Health check failed');
  return response.json();
}

async function getDashboard() {
  if (USE_MOCKS) return dashboardMock;
  throw new Error('Dashboard data is not available from the live API yet.');
}

function overlapsRange(item, start, end) {
  return Date.parse(item.start) < Date.parse(end) && Date.parse(item.end) > Date.parse(start);
}

function getMockSchedule(userId, start, end) {
  const user = examples.users.find((candidate) => candidate.id === userId);
  if (!user) throw new Error(`No mock schedule exists for ${userId}.`);

  const requestParticipants = [examples.request.requester_id, examples.request.invitee_id];
  const slot = examples.proposal.slot;
  return {
    user_id: userId,
    busy_intervals: examples.busy_intervals
      .filter((interval) => interval.user_id === userId && overlapsRange(interval, start, end))
      .map(({ start: intervalStart, end: intervalEnd }) => ({ start: intervalStart, end: intervalEnd })),
    social_windows: examples.social_windows
      .filter((window) => window.user_id === userId && overlapsRange(window, start, end))
      .map(({ start: windowStart, end: windowEnd }) => ({
        start: windowStart,
        end: windowEnd,
        visible_to: user.availability_visible_to,
        activity_types: user.activity_preferences,
      })),
    proposals: requestParticipants.includes(userId) && overlapsRange(slot, start, end)
      ? [{
        id: examples.proposal.id,
        start: slot.start,
        end: slot.end,
        activity: examples.request.activity,
        status: examples.proposal.status,
      }]
      : [],
  };
}

async function getSchedule(userId, start, end) {
  if (USE_MOCKS) return getMockSchedule(userId, start, end);

  const query = new URLSearchParams({ start, end });
  const response = await fetch(`${API_BASE_URL}/users/${encodeURIComponent(userId)}/schedule?${query}`, {
    headers: { 'X-Demo-User-Id': userId },
  });
  if (!response.ok) throw new Error(`Schedule request failed (${response.status}).`);
  return response.json();
}

function getMockFriends(userId) {
  if (!examples.users.some((user) => user.id === userId)) return [];

  return examples.users
    .filter((user) => user.id !== userId)
    .map((user) => ({ id: user.id, display_name: user.display_name }));
}

async function getFriends(userId) {
  if (USE_MOCKS) return getMockFriends(userId);

  const response = await fetch(FRIENDS_ENDPOINT(userId), {
    headers: { 'X-Demo-User-Id': userId },
  });
  if (!response.ok) throw new Error(`Friends request failed (${response.status}).`);

  const friends = await response.json();
  if (!Array.isArray(friends)) throw new Error('Friends response must be an array.');
  return friends
    .filter((friend) => friend.id !== userId)
    .map((friend) => ({ id: friend.id, display_name: friend.display_name ?? friend.name }));
}

async function createSocialWindow(window) {
  if (USE_MOCKS) {
    await new Promise((resolve) => setTimeout(resolve, 250));
    return { ...window, id: `social-window-demo-${++mockSocialWindowId}` };
  }

  const contractWindow = {
    user_id: window.user_id,
    start: window.start,
    end: window.end,
  };
  const headers = {
    'X-Demo-User-Id': window.user_id,
  };
  const currentResponse = await fetch(SOCIAL_WINDOWS_ENDPOINT, { headers });
  if (!currentResponse.ok) throw new Error(`Loading existing availability failed (${currentResponse.status}).`);
  const currentResult = await currentResponse.json();
  const existingWindows = Array.isArray(currentResult.windows) ? currentResult.windows : [];

  const response = await fetch(SOCIAL_WINDOWS_ENDPOINT, {
    method: 'PUT',
    headers: {
      ...headers,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ windows: [...existingWindows, contractWindow] }),
  });
  if (!response.ok) throw new Error(`Saving availability failed (${response.status}).`);

  const result = await response.json();
  const savedWindow = result.windows?.at(-1);
  if (!savedWindow) throw new Error('Availability response did not include the saved window.');
  return { ...window, ...savedWindow };
}

export const api = { checkHealth, getDashboard, getSchedule, getFriends, createSocialWindow };