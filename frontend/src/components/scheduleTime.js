export const DAY_START_MINUTE = 7 * 60;
export const DAY_END_MINUTE = 23 * 60;
export const VISIBLE_HOURS = [7, 9, 11, 13, 15, 17, 19, 21, 23];

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function getDateParts(value, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(value));

  return Object.fromEntries(parts.map(({ type, value: part }) => [type, part]));
}

function getTimeParts(value, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value));

  return Object.fromEntries(parts.map(({ type, value: part }) => [type, part]));
}

function dateKey({ year, month, day }) {
  return `${year}-${month}-${day}`;
}

function addDays(dayKey, amount) {
  const date = new Date(`${dayKey}T12:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return dateKey({
    year: String(date.getUTCFullYear()),
    month: String(date.getUTCMonth() + 1).padStart(2, '0'),
    day: String(date.getUTCDate()).padStart(2, '0'),
  });
}

export function getLocalDateKey(anchor, timeZone) {
  return dateKey(getDateParts(anchor, timeZone));
}

export function shiftCalendarDate(anchor, days, timeZone) {
  const nextKey = addDays(getLocalDateKey(anchor, timeZone), days);
  return new Date(getLocalMidnightISO(nextKey, timeZone));
}

export function getWeekDays(anchor, timeZone) {
  const startParts = getDateParts(anchor, timeZone);
  const startDate = new Date(Date.UTC(Number(startParts.year), Number(startParts.month) - 1, Number(startParts.day), 12));
  startDate.setUTCDate(startDate.getUTCDate() - startDate.getUTCDay());

  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(startDate);
    date.setUTCDate(startDate.getUTCDate() + index);
    const parts = {
      year: String(date.getUTCFullYear()),
      month: String(date.getUTCMonth() + 1).padStart(2, '0'),
      day: String(date.getUTCDate()).padStart(2, '0'),
    };

    return {
      key: dateKey(parts),
      label: WEEKDAYS[date.getUTCDay()],
      date: Number(parts.day),
    };
  });
}

function getLocalMidnightISO(dayKey, timeZone) {
  const [year, month, day] = dayKey.split('-').map(Number);
  const target = Date.UTC(year, month - 1, day);
  let timestamp = target;

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const dateParts = getDateParts(timestamp, timeZone);
    const timeParts = getTimeParts(timestamp, timeZone);
    const localAsUTC = Date.UTC(
      Number(dateParts.year),
      Number(dateParts.month) - 1,
      Number(dateParts.day),
      Number(timeParts.hour),
      Number(timeParts.minute),
    );
    const adjustment = target - localAsUTC;
    timestamp += adjustment;
    if (adjustment === 0) break;
  }

  return new Date(timestamp).toISOString();
}

export function getWeekRange(anchor, timeZone) {
  const firstDay = getWeekDays(anchor, timeZone)[0].key;
  return {
    start: getLocalMidnightISO(firstDay, timeZone),
    end: getLocalMidnightISO(addDays(firstDay, 7), timeZone),
  };
}

export function getDayRange(anchor, timeZone) {
  const day = getLocalDateKey(anchor, timeZone);
  return {
    start: getLocalMidnightISO(day, timeZone),
    end: getLocalMidnightISO(addDays(day, 1), timeZone),
  };
}

export function getDay(anchor, timeZone) {
  const key = getLocalDateKey(anchor, timeZone);
  return getWeekDays(anchor, timeZone).find((day) => day.key === key);
}

export function getBlockPosition(start, end, dayKey, timeZone) {
  const startDate = getDateParts(start, timeZone);
  const endDate = getDateParts(end, timeZone);
  const startKey = dateKey(startDate);
  const endKey = dateKey(endDate);

  if (startKey > dayKey || endKey < dayKey) return null;

  const startTime = getTimeParts(start, timeZone);
  const endTime = getTimeParts(end, timeZone);
  const startMinute = startKey === dayKey
    ? Number(startTime.hour) * 60 + Number(startTime.minute)
    : 0;
  const endMinute = endKey === dayKey
    ? Number(endTime.hour) * 60 + Number(endTime.minute)
    : 24 * 60;
  const visibleStart = Math.max(startMinute, DAY_START_MINUTE);
  const visibleEnd = Math.min(endMinute, DAY_END_MINUTE);

  if (visibleEnd <= visibleStart) return null;

  const visibleDuration = DAY_END_MINUTE - DAY_START_MINUTE;
  return {
    top: ((visibleStart - DAY_START_MINUTE) / visibleDuration) * 100,
    height: ((visibleEnd - visibleStart) / visibleDuration) * 100,
  };
}