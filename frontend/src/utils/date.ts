const campusTimeFormatter = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: true,
});

export function formatCampusTimestamp(value?: string | null): string {
  if (!value) return '—';
  if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : campusTimeFormatter.format(date);
}
