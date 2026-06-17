/**
 * Shared date-parsing utilities used across the Access Control pages.
 */

/**
 * Parse a UTC date-string, appending 'Z' when no timezone info is present.
 */
export function parseUTC(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null
  let normalized = dateStr
  if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !/-\d{2}:\d{2}$/.test(dateStr)) {
    normalized = dateStr + 'Z'
  }
  return new Date(normalized)
}

/**
 * Convert a Date to a local datetime-local string for <input type="datetime-local">.
 */
export function toLocalDateTimeString(date: Date | null): string {
  if (!date) return ''
  const tzOffset = date.getTimezoneOffset() * 60000
  const localISOTime = new Date(date.getTime() - tzOffset).toISOString().slice(0, 16)
  return localISOTime
}
