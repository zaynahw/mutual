export function dateTime(value: string, timezone: string) {
  return new Date(value).toLocaleString(undefined, {
    timeZone: timezone, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}
