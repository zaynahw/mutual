import {
  checkHealth as requestHealth,
  createMyWindow,
  getSchedule as requestSchedule,
  listFriendRequests,
  listOverviews,
  listUsers,
} from './lib/api';
import { visibleProposals } from './lib/proposals';

export const USE_MOCKS = false;

async function getSchedule(userId, start, end, signal = new AbortController().signal, ownerId = userId) {
  const [schedule, overviews] = await Promise.all([
    requestSchedule(userId, ownerId, { start, end }, signal),
    ownerId === userId ? listOverviews(userId, signal) : Promise.resolve([]),
  ]);

  return {
    user: schedule.user,
    calendar_busy: schedule.calendar_busy,
    social_windows: schedule.social_windows,
    proposals: overviews.flatMap((overview) => visibleProposals(overview.proposals.map(({ proposal }) => proposal)))
      .filter((proposal) => Date.parse(proposal.slot.start) < Date.parse(end)
        && Date.parse(proposal.slot.end) > Date.parse(start))
      .map((proposal) => ({
        id: proposal.id,
        start: proposal.slot.start,
        end: proposal.slot.end,
        activity: proposal.activity,
        status: proposal.status,
      })),
  };
}

async function getFriends(userId, signal = new AbortController().signal) {
  const [users, requests] = await Promise.all([
    listUsers(userId, signal),
    listFriendRequests(userId, signal),
  ]);
  const acceptedIds = new Set(requests
    .filter((request) => request.status === 'accepted')
    .map((request) => request.sender_id === userId ? request.recipient_id : request.sender_id));

  return users
    .filter((user) => user.id !== userId && acceptedIds.has(user.id))
    .map(({ id, display_name }) => ({ id, display_name }));
}

async function createSocialWindow(window, signal = new AbortController().signal) {
  const { user_id, ...input } = window;
  return createMyWindow(user_id, input, signal);
}

export const api = { checkHealth: requestHealth, getSchedule, getFriends, createSocialWindow };
