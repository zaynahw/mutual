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
