export function filterRows<T>(
  rows: T[],
  query: string,
  textOf: (row: T) => string,
  status: string,
  statusOf: (row: T) => string,
): T[] {
  const needle = query.trim().toLowerCase()
  return rows.filter((row) => {
    if (status !== '' && status !== 'all' && statusOf(row) !== status) {
      return false
    }
    if (needle === '') {
      return true
    }
    return textOf(row).toLowerCase().includes(needle)
  })
}

export function pageOf<T>(rows: T[], page: number, size: number): T[] {
  const start = Math.max(0, page - 1) * size
  return rows.slice(start, start + size)
}
