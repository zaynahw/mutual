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
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
}

// All requests share identity headers and error handling. Callers decode JSON
// only when a response body is expected (DELETE returns an empty 204).
async function request(path: string, options: RequestOptions = {}): Promise<Response> {
  const { userId, signal, method = 'GET', body } = options;
  const response = await fetch(`${baseUrl}${path}`, {
    method, signal,
    headers: {
      ...(userId ? { 'X-Demo-User-Id': userId } : {}),
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
