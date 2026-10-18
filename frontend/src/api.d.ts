export const USE_MOCKS: boolean;

export interface ScheduleData {
  user_id: string;
  busy_intervals: {start:string;end:string}[];
  social_windows: {start:string;end:string;activity_types:string[]}[];
  proposals: {id:string;start:string;end:string;activity:string;status:string}[];
}
export const api: {getSchedule(userId:string,start:string,end:string):Promise<ScheduleData>};

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

export interface Friend {
  id: string;
  display_name: string;
}

export interface CreateSocialWindowInput {
  user_id: string;
  start: string;
  end: string;
  visible_to: string[];
  activity_types: string[];
}

export interface CreatedSocialWindow extends CreateSocialWindowInput {
  id?: string;
}

export interface ScheduleInterval {
  start: string;
  end: string;
}

// export interface ScheduleData {
//   user_id: string;
//   busy_intervals: ScheduleInterval[];
//   social_windows: Array<ScheduleInterval & { visible_to: string[]; activity_types: string[] }>;
//   proposals: Array<ScheduleInterval & {
//     id: string;
//     activity: string;
//     status: 'pending' | 'approved' | 'rejected' | 'declined' | 'scheduled';
//   }>;
// }

export const api: {
  checkHealth(): Promise<{ status: string }>;
  getDashboard(): Promise<DashboardData>;
  getSchedule(userId: string, start: string, end: string): Promise<ScheduleData>;
  getFriends(userId: string): Promise<Friend[]>;
  createSocialWindow(window: CreateSocialWindowInput): Promise<CreatedSocialWindow>;
};