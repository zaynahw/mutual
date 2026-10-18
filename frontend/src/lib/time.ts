/** Convert a wall-clock input in an IANA timezone, independent of browser timezone.
 * Reject DST gaps and repeated times rather than silently choosing an instant.
 */
export function zonedInputToISO(value: string, timeZone: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) throw new Error('Enter a complete date and time.');
  const wallTime = (instant: number) => isoToZonedInput(new Date(instant).toISOString(), timeZone);
  const target = Date.parse(`${value}:00Z`);
  if (!Number.isFinite(target) || new Date(target).toISOString().slice(0, 16) !== value) {
    throw new Error('Enter a valid date and time.');
  }
  // Sample nearby offsets on both sides of a possible DST transition.
  const offsets = new Set<number>();
  for (const hours of [-36, 0, 36]) {
    const sample = target + hours * 3_600_000;
    offsets.add(Date.parse(`${wallTime(sample)}:00Z`) - sample);
  }
  const matches = [...offsets].map(offset => target - offset).filter(instant => wallTime(instant) === value);
  if (matches.length === 0) throw new Error('This time does not exist because the clocks change. Choose another time.');
  if (matches.length > 1) throw new Error('This time occurs twice because the clocks change. Choose another time.');
  return new Date(matches[0]).toISOString();
}

/** Format an instant for datetime-local in the profile timezone. */
export function isoToZonedInput(value: string, timeZone: string): string {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  });
  const parts = Object.fromEntries(formatter.formatToParts(new Date(value)).map(part => [part.type, part.value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}
