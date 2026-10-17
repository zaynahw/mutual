import examples from '../../contracts/examples.json';

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

export const api = { checkHealth, getDashboard, getSchedule };