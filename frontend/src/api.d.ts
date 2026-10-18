import type { ScheduleResponse, SocialWindow, SocialWindowInput } from './lib/api';

export const USE_MOCKS: boolean;

export interface Friend {
  id: string;
  display_name: string;
}

export type ScheduleData = ScheduleResponse & {
  proposals: Array<{ id: string; start: string; end: string; activity: string; status: string }>;
};

export type CreateSocialWindowInput = SocialWindowInput & { user_id: string };
export type CreatedSocialWindow = SocialWindow;

export const api: {
  checkHealth(): Promise<string>;
  getSchedule(userId: string, start: string, end: string, signal?: AbortSignal): Promise<ScheduleData>;
  getFriends(userId: string, signal?: AbortSignal): Promise<Friend[]>;
  createSocialWindow(window: CreateSocialWindowInput, signal?: AbortSignal): Promise<CreatedSocialWindow>;
};
