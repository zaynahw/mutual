export const USE_MOCKS: boolean;
export interface ScheduleData {
  user_id: string;
  busy_intervals: {start:string;end:string}[];
  social_windows: {start:string;end:string;activity_types:string[]}[];
  proposals: {id:string;start:string;end:string;activity:string;status:string}[];
}
export const api: {getSchedule(userId:string,start:string,end:string):Promise<ScheduleData>};
