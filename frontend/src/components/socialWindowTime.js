function getParts(timestamp, timeZone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(timestamp));

  return Object.fromEntries(parts.map(({ type, value }) => [type, value]));
}

export function localDateTimeToISO(date, time, timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone) {
  const dateMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  const timeMatch = /^(\d{2}):(\d{2})$/.exec(time);
  if (!dateMatch || !timeMatch) throw new RangeError('Enter a valid date and time.');

  const [, year, month, day] = dateMatch;
  const [, hour, minute] = timeMatch;
  const expected = Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute));
  const expectedDate = new Date(expected);
  if (expectedDate.getUTCFullYear() !== Number(year)
    || expectedDate.getUTCMonth() + 1 !== Number(month)
    || expectedDate.getUTCDate() !== Number(day)
    || Number(hour) > 23
    || Number(minute) > 59) {
    throw new RangeError('Enter a valid date and time.');
  }

  let timestamp = expected;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const local = getParts(timestamp, timeZone);
    const localAsUTC = Date.UTC(
      Number(local.year),
      Number(local.month) - 1,
      Number(local.day),
      Number(local.hour),
      Number(local.minute),
    );
    const adjustment = expected - localAsUTC;
    timestamp += adjustment;
    if (adjustment === 0) break;
  }

  const resolved = getParts(timestamp, timeZone);
  if (resolved.year !== year || resolved.month !== month || resolved.day !== day
    || resolved.hour !== hour || resolved.minute !== minute) {
    throw new RangeError(`That local time does not exist in ${timeZone} due to a daylight-saving transition.`);
  }

  const resolvedLocalAsUTC = Date.UTC(
    Number(resolved.year),
    Number(resolved.month) - 1,
    Number(resolved.day),
    Number(resolved.hour),
    Number(resolved.minute),
  );
  const offsetMinutes = Math.round((resolvedLocalAsUTC - timestamp) / 60000);
  const offsetSign = offsetMinutes >= 0 ? '+' : '-';
  const offsetHours = String(Math.floor(Math.abs(offsetMinutes) / 60)).padStart(2, '0');
  const offsetRemainder = String(Math.abs(offsetMinutes) % 60).padStart(2, '0');

  return `${date}T${time}:00${offsetSign}${offsetHours}:${offsetRemainder}`;
}