import type { ComponentType } from 'react';

export type ScheduleItem =
  | { type: 'social_window'; start: string; end: string; visible_to?: string[]; activity_types: string[] }
  | { type: 'proposal'; id: string; start: string; end: string; activity: string; status: string };

declare const ScheduleView: ComponentType<{
  userId: string;
  timezone?: string;
  onSelect?: (item: ScheduleItem) => void;
}>;

export default ScheduleView;