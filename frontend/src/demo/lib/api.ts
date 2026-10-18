import { creationKey } from './creationKeys';
// These types mirror backend/models.py. The API contract is the source of truth.
export type Activity = 'coffee' | 'meal' | 'walk' | 'study' | 'concert';
export interface PublicUser {
  id: string;
  display_name: string;
  is_demo: true;
  community: 'georgia_tech';
}
export interface User extends PublicUser {
  timezone: string;
  matching: {mode: "social_windows" | "calendar_guided"; start_hour: number; end_hour: number};
  calendar_sharing: {
    audience: 'private' | 'community' | 'friends' | 'selected_friends';
    selected_friend_ids: string[];
  };
  preferences: {
    preferred_activities: Activity[];
    soft_preference_note: string;
  };
  hard_constraints: {
    allowed_activities: Activity[];
    max_duration_minutes: 30 | 60 | 90 | 120;
  };
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

interface RequestOptions {
  userId?: string;
  signal?: AbortSignal;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  idempotencyKey?: string;
}

// All requests share identity headers and error handling. Callers decode JSON
// only when a response body is expected (DELETE returns an empty 204).
async function request(path: string, options: RequestOptions = {}): Promise<Response> {
  const { userId, signal, method = 'GET', body, idempotencyKey } = options;
  const response = await fetch(`${baseUrl}${path}`, {
    method, signal,
    headers: {
      ...(userId ? { 'X-Demo-User-Id': userId } : {}),
      ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Demo user unavailable. Run the backend seed command, then reload.');
    }
    // A proxy/server failure may return HTML or no body instead of JSON.
    const data = await response.json().catch(() => null) as {
      detail?: string | { msg: string }[];
    } | null;
    const detail = typeof data?.detail === 'string' ? data.detail
      : Array.isArray(data?.detail) ? data.detail.map(item => item.msg).join('; ')
      : `Request failed (HTTP ${response.status}).`;
    throw new Error(detail);
  }
  return response;
}

async function requestJson<T>(path: string, options: RequestOptions): Promise<T> {
  return (await request(path, options)).json() as Promise<T>;
}

export const listUsers = (userId: string, signal: AbortSignal) =>
  requestJson<PublicUser[]>('/users', { userId, signal });

export const getMe = (userId: string, signal: AbortSignal) =>
  requestJson<User>('/users/me', { userId, signal });

export async function checkHealth(): Promise<string> {
  const data = await requestJson<{ status: string }>('/health', {});
  return data.status;
}

export interface SocialWindowInput {
  start: string;
  end: string;
  allowed_activities: Activity[];
  visibility: User['calendar_sharing'];
  sharing_mode: 'visible' | 'matching_only';
}
export interface SocialWindow extends SocialWindowInput {
  id: string;
  user_id: string;
}
const windowsPath = '/users/me/social-windows';
const windowPath = (id: string) => `${windowsPath}/${encodeURIComponent(id)}`;

export const listMyWindows = (userId: string, signal: AbortSignal) =>
  requestJson<SocialWindow[]>(windowsPath, { userId, signal });

export const createMyWindow = (userId: string, input: SocialWindowInput, signal: AbortSignal) =>
  requestJson<SocialWindow>(windowsPath, { userId, signal, method: 'POST', body: input });

export const updateMyWindow = (userId: string, windowId: string, input: SocialWindowInput, signal: AbortSignal) =>
  requestJson<SocialWindow>(windowPath(windowId), { userId, signal, method: 'PUT', body: input });

export async function deleteMyWindow(userId: string, windowId: string, signal: AbortSignal): Promise<void> {
  await request(windowPath(windowId), { userId, signal, method: 'DELETE' });
}

export interface FriendRequest {
  id: string;
  sender_id: string;
  recipient_id: string;
  status: 'pending' | 'accepted' | 'declined' | 'removed';
  created_at: string;
  responded_at: string | null;
}

const friendshipsPath = '/friend-requests';

export const listFriendRequests = (userId: string, signal: AbortSignal) =>
  requestJson<FriendRequest[]>(friendshipsPath, { userId, signal });

export const sendFriendRequest = (userId: string, recipientId: string, signal: AbortSignal) =>
  requestJson<FriendRequest>(friendshipsPath, {
    userId, signal, method: 'POST', body: { recipient_id: recipientId },
  });

export const respondToFriendRequest = (
  userId: string, requestId: string, decision: 'accept' | 'decline', signal: AbortSignal,
) => requestJson<FriendRequest>(`${friendshipsPath}/${encodeURIComponent(requestId)}/respond`, {
  userId, signal, method: 'POST', body: { decision },
});

export const removeFriendship = (userId: string, requestId: string, signal: AbortSignal) =>
  requestJson<FriendRequest>(`${friendshipsPath}/${encodeURIComponent(requestId)}/remove`, {
    userId, signal, method: 'POST',
  });

export interface Interval { start: string; end: string }
export interface ScheduleResponse {
  user: PublicUser;
  social_windows: (Interval & { id: string; allowed_activities: Activity[] })[];
  calendar_busy: Interval[] | null;
}
export type Duration = 30 | 60 | 90 | 120;
export interface HangoutInput extends Interval {
  invitee_id: string;
  allowed_activities: Activity[];
  allowed_durations: Duration[];
  location: string | null;
}
export interface HangoutRequest extends HangoutInput { id: string; requester_id: string; origin: "manual" | "intent"; search_windows: Interval[] }
export interface CandidateOption {
  slot: Interval;
  eligible_activities: Activity[];
  eligible_durations: Duration[];
}
export interface ProposalInput { activity: Activity; slot: Interval }
export interface Proposal extends ProposalInput {
  source: 'manual' | 'local_agent' | 'demo_fallback' | 'mock';
  id: string;
  request_id: string;
  location: string | null;
  status: 'pending' | 'approved' | 'declined' | 'cancelled' | 'scheduled';
}
export interface ProposalResponse {
  proposal: Proposal;
  approvals: { proposal_id: string; user_id: string; decision: 'approve' | 'decline'; decided_at: string }[];
}
export const getSchedule = (userId: string, ownerId: string, range: Interval, signal: AbortSignal) =>
  requestJson<ScheduleResponse>(`/users/${encodeURIComponent(ownerId)}/schedule?${new URLSearchParams({ ...range })}`, { userId, signal });
export const listHangouts = (userId: string, signal: AbortSignal) =>
  requestJson<HangoutRequest[]>('/hangout-requests', { userId, signal });
export async function createHangout(userId: string, body: HangoutInput, signal: AbortSignal) {
  const retry = await creationKey(userId, 'hangout', body);
  const result = await requestJson<HangoutRequest>('/hangout-requests', { userId, signal, method: 'POST', body, idempotencyKey: retry.key });
  retry.confirmed();
  return result;
}
export const getCandidates = (userId: string, id: string, signal: AbortSignal) =>
  requestJson<CandidateOption[]>(`/hangout-requests/${encodeURIComponent(id)}/candidates`, { userId, signal, method: 'POST' });
export async function createProposal(userId: string, id: string, body: ProposalInput, signal: AbortSignal) {
  const retry = await creationKey(userId, `proposal:${id}`, body);
  const result = await requestJson<Proposal>(`/hangout-requests/${encodeURIComponent(id)}/proposals`, { userId, signal, method: 'POST', body, idempotencyKey: retry.key });
  retry.confirmed();
  return result;
}
export const getProposal = (userId: string, id: string, signal: AbortSignal) =>
  requestJson<ProposalResponse>(`/proposals/${encodeURIComponent(id)}`, { userId, signal });
export const decideProposal = (userId: string, id: string, decision: 'approve' | 'decline', signal: AbortSignal) =>
  requestJson<ProposalResponse>(`/proposals/${encodeURIComponent(id)}/approvals`, {
    userId, signal, method: 'POST', body: { decision },
  });
export const listProposals = (userId: string, requestId: string, signal: AbortSignal) =>
  requestJson<Proposal[]>(`/hangout-requests/${encodeURIComponent(requestId)}/proposals`, { userId, signal });

export const scheduleProposal = (userId: string, id: string, key: string, signal: AbortSignal) =>
  requestJson<{ proposal_id: string; event_id: string }>(`/proposals/${encodeURIComponent(id)}/calendar-event`, {
    userId, signal, method: 'POST', idempotencyKey: key,
  });

export interface HangoutOverview { request: HangoutRequest; proposals: ProposalResponse[] }
export const listOverviews = (userId: string, signal: AbortSignal) =>
  requestJson<HangoutOverview[]>('/hangout-requests/overview', { userId, signal });
export const replanProposal = (userId: string, id: string, signal: AbortSignal) =>
  requestJson<ProposalResponse>(`/proposals/${encodeURIComponent(id)}/replan`, { userId, signal, method: 'POST' });

export interface NegotiationResponse {
  status: 'agreed' | 'no_match' | 'exhausted';
  source: 'local_agent' | 'demo_fallback' | 'mock';
  proposal: Proposal | null;
  turns: { actor_id: string; decision: 'propose' | 'counter' | 'accept' | 'no_match'; activity: Activity | null; slot: Interval | null }[];
}
export async function negotiateHangout(userId: string, requestId: string, signal: AbortSignal) {
  const retry = await creationKey(userId, `negotiate:${requestId}`, {});
  const result = await requestJson<NegotiationResponse>(`/hangout-requests/${encodeURIComponent(requestId)}/negotiate`, {
    userId, signal, method: 'POST', idempotencyKey: retry.key,
  });
  retry.confirmed();
  return result;
}

export const updatePreferenceNote = (userId: string, note: string, signal: AbortSignal) =>
  requestJson<User>('/users/me/preferences', {userId,signal,method:'PATCH',body:{soft_preference_note:note}});

export interface IntentInput { invitee_id: string; days: string[]; message: string }
export interface IntentDraft {
  id: string; owner_id: string; input: IntentInput; timezone: string; request_id: string|null;
  result: {source: NegotiationResponse['source']; interpretation: {
    activities: Activity[]; allowed_durations: Duration[]; preferred_periods: string[];
    earliest: string|null; latest: string|null; clarification: string|null;
  }};
}
export const interpretIntent = (userId: string,body: IntentInput,signal: AbortSignal) =>
  requestJson<IntentDraft>('/hangout-intents/interpret',{userId,body,signal,method:'POST'});
export const sendIntent = (userId: string,id: string,signal: AbortSignal) =>
  requestJson<HangoutRequest>(`/hangout-intents/${encodeURIComponent(id)}/send`,{userId,signal,method:'POST'});
export const updateMatching = (userId: string,body: User['matching'],signal: AbortSignal) =>
  requestJson<User>('/users/me/matching',{userId,body,signal,method:'PATCH'});
