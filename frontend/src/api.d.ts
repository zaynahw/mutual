export const USE_MOCKS: boolean;

export interface DashboardProposal {
  id: string;
  request_id: string;
  activity: string;
  other_person: string;
  slot: { start: string; end: string };
  status: 'pending' | 'approved' | 'declined' | 'scheduled';
}

export interface DashboardData {
  user: {
    id: string;
    display_name: string;
    is_demo: boolean;
    timezone: string;
    activity_preferences: string[];
  };
  upcoming_proposals: DashboardProposal[];
}

export interface ScheduleInterval {
  start: string;
  end: string;
}

export interface ScheduleData {
  user_id: string;
  busy_intervals: ScheduleInterval[];
  social_windows: Array<ScheduleInterval & { visible_to: string[]; activity_types: string[] }>;
  proposals: Array<ScheduleInterval & {
    id: string;
    activity: string;
    status: 'pending' | 'approved' | 'rejected' | 'declined' | 'scheduled';
  }>;
}

export const api: {
  checkHealth(): Promise<{ status: string }>;
  getDashboard(): Promise<DashboardData>;
  getSchedule(userId: string, start: string, end: string): Promise<ScheduleData>;
};