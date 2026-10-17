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

async function get<T>(path: string, userId: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { 'X-Demo-User-Id': userId }, signal,
  });
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Demo user unavailable. Run the backend seed command, then reload.');
    }
    throw new Error(`Could not load data (HTTP ${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export const listUsers = (userId: string, signal: AbortSignal) => get<PublicUser[]>('/users', userId, signal);
export const getMe = (userId: string, signal: AbortSignal) => get<User>('/users/me', userId, signal);

export async function checkHealth(): Promise<string> {
  const response = await fetch(`${baseUrl}/health`);
  if (!response.ok) throw new Error('Health check failed');
  const data = await response.json() as { status: string };
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
export const listMyWindows = (userId: string, signal: AbortSignal) =>
  get<SocialWindow[]>('/users/me/social-windows', userId, signal);

async function writeWindow(userId: string, method: 'POST' | 'PUT' | 'DELETE', path: string, signal: AbortSignal, input?: SocialWindowInput): Promise<Response> {
  const response = await fetch(`${baseUrl}${path}`, {
    method,
    headers: { 'X-Demo-User-Id': userId, ...(input ? { 'Content-Type': 'application/json' } : {}) },
    ...(input ? { body: JSON.stringify(input) } : {}), signal,
  });
  if (!response.ok) {
    const data = await response.json() as { detail?: string | { msg: string }[] };
    const detail = typeof data.detail === 'string' ? data.detail
      : Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('; ') : 'Could not change window';
    throw new Error(detail);
  }
  return response;
}

export async function createMyWindow(userId: string, input: SocialWindowInput, signal: AbortSignal): Promise<SocialWindow> {
  return (await writeWindow(userId, 'POST', '/users/me/social-windows', signal, input)).json();
}

export async function updateMyWindow(userId: string, windowId: string, input: SocialWindowInput, signal: AbortSignal): Promise<SocialWindow> {
  return (await writeWindow(userId, 'PUT', `/users/me/social-windows/${encodeURIComponent(windowId)}`, signal, input)).json();
}

export async function deleteMyWindow(userId: string, windowId: string, signal: AbortSignal): Promise<void> {
  await writeWindow(userId, 'DELETE', `/users/me/social-windows/${encodeURIComponent(windowId)}`, signal);
}
