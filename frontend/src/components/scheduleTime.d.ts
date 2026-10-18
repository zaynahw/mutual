export const DAY_START_MINUTE: number;
export const DAY_END_MINUTE: number;
export const VISIBLE_HOURS: number[];

export interface ScheduleDay {
  key: string;
  label: string;
  date: number;
}

export interface BlockPosition {
  top: number;
  height: number;
}

export function getWeekDays(anchor: Date | string, timeZone: string): ScheduleDay[];
export function getWeekRange(anchor: Date | string, timeZone: string): { start: string; end: string };
export function getDayRange(anchor: Date | string, timeZone: string): { start: string; end: string };
export function getDay(anchor: Date | string, timeZone: string): ScheduleDay | undefined;
export function getLocalDateKey(anchor: Date | string, timeZone: string): string;
export function shiftCalendarDate(anchor: Date | string, days: number, timeZone: string): Date;
export function getBlockPosition(start: string, end: string, dayKey: string, timeZone: string): BlockPosition | null;