import { ApiError } from './client'
import { errorFromResponse, request } from './session'

export type CountMap = Record<string, number>

export type OccupancyReport = {
  on: string
  within_days: number
  spaces: { unit: CountMap; room: CountMap }
  beds: CountMap
  properties: Array<{
    property_id: string
    property_name: string
    occupied: number
    partly_occupied: number
    free: number
    unavailable: number
  }>
  active_tenancies: number
  active_residents: number
  upcoming_count: number
  upcoming_truncated: boolean
  upcoming_move_outs: Array<{
    kind: string
    resident_name: string
    label: string
    end_date: string
  }>
}

export type ArrearsReport = {
  on: string
  currency_code: string
  invoice_count: number
  outstanding_amount: string
  residents: Array<{
    resident_id: string
    resident_name: string
    invoice_count: number
    outstanding_amount: string
  }>
}

export type CollectionsReport = {
  from: string
  to: string
  currency_code: string
  payment_count: number
  collected_amount: string
  refund_count: number
  refunded_amount: string
  net_amount: string
  by_method: Array<{ method: string; count: number; amount: string }>
}

export type MaintenanceReport = {
  scope: string
  counts: CountMap
  open_count: number
  by_priority: CountMap
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function text(value: Record<string, unknown>, key: string): string | null {
  const field = value[key]
  return typeof field === 'string' ? field : null
}

function number(value: Record<string, unknown>, key: string): number | null {
  const field = value[key]
  return typeof field === 'number' ? field : null
}

function counts(value: unknown): CountMap | null {
  if (!isRecord(value)) {
    return null
  }
  const result: CountMap = {}
  for (const [key, item] of Object.entries(value)) {
    if (typeof item !== 'number') {
      return null
    }
    result[key] = item
  }
  return result
}

async function readBody(response: Response): Promise<unknown> {
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
  try {
    return await response.json()
  } catch {
    throw new ApiError('The API returned an unexpected response.')
  }
}

export async function loadOccupancyReport(
  workspaceId: string,
  on: string,
  signal?: AbortSignal,
): Promise<OccupancyReport> {
  const response = await request(
    `/api/v1/reports/occupancy/?on=${encodeURIComponent(on)}`,
    { workspaceId, signal },
  )
  const body = await readBody(response)
  if (!isRecord(body) || !isRecord(body.spaces) || !Array.isArray(body.properties)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const unit = counts(body.spaces.unit)
  const room = counts(body.spaces.room)
  const beds = counts(body.beds)
  const onDate = text(body, 'on')
  const within = number(body, 'within_days')
  const activeTenancies = number(body, 'active_tenancies')
  const activeResidents = number(body, 'active_residents')
  const upcomingCount = number(body, 'upcoming_count')
  if (
    unit === null ||
    room === null ||
    beds === null ||
    onDate === null ||
    within === null ||
    activeTenancies === null ||
    activeResidents === null ||
    upcomingCount === null ||
    typeof body.upcoming_truncated !== 'boolean' ||
    !Array.isArray(body.upcoming_move_outs)
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const properties = body.properties.map((item) => {
    if (!isRecord(item)) {
      throw new ApiError('The API returned an unexpected response.')
    }
    const propertyId = text(item, 'property_id')
    const propertyName = text(item, 'property_name')
    const occupied = number(item, 'occupied')
    const partly = number(item, 'partly_occupied')
    const free = number(item, 'free')
    const unavailable = number(item, 'unavailable')
    if (
      propertyId === null ||
      propertyName === null ||
      occupied === null ||
      partly === null ||
      free === null ||
      unavailable === null
    ) {
      throw new ApiError('The API returned an unexpected response.')
    }
    return {
      property_id: propertyId,
      property_name: propertyName,
      occupied,
      partly_occupied: partly,
      free,
      unavailable,
    }
  })
  const upcoming = body.upcoming_move_outs.map((item) => {
    if (!isRecord(item)) {
      throw new ApiError('The API returned an unexpected response.')
    }
    const kind = text(item, 'kind')
    const residentName = text(item, 'resident_name')
    const label = text(item, 'label')
    const endDate = text(item, 'end_date')
    if (kind === null || residentName === null || label === null || endDate === null) {
      throw new ApiError('The API returned an unexpected response.')
    }
    return { kind, resident_name: residentName, label, end_date: endDate }
  })
  return {
    on: onDate,
    within_days: within,
    spaces: { unit, room },
    beds,
    properties,
    active_tenancies: activeTenancies,
    active_residents: activeResidents,
    upcoming_count: upcomingCount,
    upcoming_truncated: body.upcoming_truncated,
    upcoming_move_outs: upcoming,
  }
}

export async function loadArrearsReport(
  workspaceId: string,
  on: string,
  signal?: AbortSignal,
): Promise<ArrearsReport> {
  const response = await request(`/api/v1/reports/arrears/?on=${encodeURIComponent(on)}`, {
    workspaceId,
    signal,
  })
  const body = await readBody(response)
  if (!isRecord(body) || !Array.isArray(body.residents)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const onDate = text(body, 'on')
  const currency = text(body, 'currency_code')
  const invoiceCount = number(body, 'invoice_count')
  const outstanding = text(body, 'outstanding_amount')
  if (onDate === null || currency === null || invoiceCount === null || outstanding === null) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    on: onDate,
    currency_code: currency,
    invoice_count: invoiceCount,
    outstanding_amount: outstanding,
    residents: body.residents.map((item) => {
      if (!isRecord(item)) {
        throw new ApiError('The API returned an unexpected response.')
      }
      const residentId = text(item, 'resident_id')
      const residentName = text(item, 'resident_name')
      const count = number(item, 'invoice_count')
      const amount = text(item, 'outstanding_amount')
      if (residentId === null || residentName === null || count === null || amount === null) {
        throw new ApiError('The API returned an unexpected response.')
      }
      return {
        resident_id: residentId,
        resident_name: residentName,
        invoice_count: count,
        outstanding_amount: amount,
      }
    }),
  }
}

export async function loadCollectionsReport(
  workspaceId: string,
  start: string,
  end: string,
  signal?: AbortSignal,
): Promise<CollectionsReport> {
  const response = await request(
    `/api/v1/reports/collections/?from=${encodeURIComponent(start)}&to=${encodeURIComponent(end)}`,
    { workspaceId, signal },
  )
  const body = await readBody(response)
  if (!isRecord(body) || !Array.isArray(body.by_method)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const from = text(body, 'from')
  const to = text(body, 'to')
  const currency = text(body, 'currency_code')
  const paymentCount = number(body, 'payment_count')
  const collected = text(body, 'collected_amount')
  const refundCount = number(body, 'refund_count')
  const refunded = text(body, 'refunded_amount')
  const net = text(body, 'net_amount')
  if (
    from === null ||
    to === null ||
    currency === null ||
    paymentCount === null ||
    collected === null ||
    refundCount === null ||
    refunded === null ||
    net === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    from,
    to,
    currency_code: currency,
    payment_count: paymentCount,
    collected_amount: collected,
    refund_count: refundCount,
    refunded_amount: refunded,
    net_amount: net,
    by_method: body.by_method.map((item) => {
      if (!isRecord(item)) {
        throw new ApiError('The API returned an unexpected response.')
      }
      const method = text(item, 'method')
      const count = number(item, 'count')
      const amount = text(item, 'amount')
      if (method === null || count === null || amount === null) {
        throw new ApiError('The API returned an unexpected response.')
      }
      return { method, count, amount }
    }),
  }
}

export async function loadMaintenanceReport(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<MaintenanceReport> {
  const response = await request('/api/v1/reports/maintenance/', { workspaceId, signal })
  const body = await readBody(response)
  if (!isRecord(body)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const scope = text(body, 'scope')
  const openCount = number(body, 'open_count')
  const statusCounts = counts(body.counts)
  const priorities = counts(body.by_priority)
  if (scope === null || openCount === null || statusCounts === null || priorities === null) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    scope,
    open_count: openCount,
    counts: statusCounts,
    by_priority: priorities,
  }
}

export async function downloadReport(
  workspaceId: string,
  path: string,
  filename: string,
): Promise<void> {
  const response = await request(path, { workspaceId })
  if (!response.ok) {
    throw await errorFromResponse(response)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
