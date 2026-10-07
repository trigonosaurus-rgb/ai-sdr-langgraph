// Dates the server sends as ISO strings in UTC.

// "at 3:15 PM" later today, otherwise "on Oct 31 at 9:00 AM", in the visitor's time zone.
export function when(iso: string, now = new Date()) {
  const date = new Date(iso)
  const time = date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  })
  if (date.toDateString() === now.toDateString()) return `at ${time}`
  const day = date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
  return `on ${day} at ${time}`
}
