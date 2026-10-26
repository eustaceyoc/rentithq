import { ApiError } from './client'
import { errorFromResponse, request } from './session'

const page = 'page_size=100'

export type MaintenanceUpdateRecord = {
  id: string
  status_before: string
  status_after: string
  note: string
  cost_amount: string | null
  assignee_id: string | null
  actor_email: string
  created_at: string
}

export type MaintenanceRequestRecord = {
  id: string
  reference: string
  property_id: string | null
  property_name: string
  space_id: string | null
  space_name: string
  bed_id: string | null
  bed_name: string
  resident_id: string | null
  resident_name: string
  description: string
  priority: string
  status: string
  completion_note: string
  cost_amount: string | null
  currency_code: string
  assignee_id: string | null
  assignee_email: string
  reported_by_email: string
  location_blocked: boolean
  updates: MaintenanceUpdateRecord[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function text(value: Record<string, unknown>, key: string): string | null {
  const field = value[key]
  return typeof field === 'string' ? field : null
}

function optionalText(value: Record<string, unknown>, key: string): string | null | undefined {
  const field = value[key]
  if (field === null) {
    return null
  }
  return typeof field === 'string' ? field : undefined
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

function parseUpdate(value: unknown): MaintenanceUpdateRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const statusBefore = text(value, 'status_before')
  const statusAfter = text(value, 'status_after')
  const note = text(value, 'note')
  const cost = optionalText(value, 'cost_amount')
  const assigneeId = optionalText(value, 'assignee_id')
  const actorEmail = text(value, 'actor_email')
  const createdAt = text(value, 'created_at')
  if (
    id === null ||
    statusBefore === null ||
    statusAfter === null ||
    note === null ||
    cost === undefined ||
    assigneeId === undefined ||
    actorEmail === null ||
    createdAt === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    status_before: statusBefore,
    status_after: statusAfter,
    note,
    cost_amount: cost,
    assignee_id: assigneeId,
    actor_email: actorEmail,
    created_at: createdAt,
  }
}

function parseRequest(value: unknown): MaintenanceRequestRecord {
  if (!isRecord(value) || !Array.isArray(value.updates)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const reference = text(value, 'reference')
  const propertyId = optionalText(value, 'property_id')
  const propertyName = text(value, 'property_name')
  const spaceId = optionalText(value, 'space_id')
  const spaceName = text(value, 'space_name')
  const bedId = optionalText(value, 'bed_id')
  const bedName = text(value, 'bed_name')
  const residentId = optionalText(value, 'resident_id')
  const residentName = text(value, 'resident_name')
  const description = text(value, 'description')
  const priority = text(value, 'priority')
  const status = text(value, 'status')
  const completionNote = text(value, 'completion_note')
  const cost = optionalText(value, 'cost_amount')
  const currency = text(value, 'currency_code')
  const assigneeId = optionalText(value, 'assignee_id')
  const assigneeEmail = text(value, 'assignee_email')
  const reportedBy = text(value, 'reported_by_email')
  if (
    id === null ||
    reference === null ||
    propertyId === undefined ||
    propertyName === null ||
    spaceId === undefined ||
    spaceName === null ||
    bedId === undefined ||
    bedName === null ||
    residentId === undefined ||
    residentName === null ||
    description === null ||
    priority === null ||
    status === null ||
    completionNote === null ||
    cost === undefined ||
    currency === null ||
    assigneeId === undefined ||
    assigneeEmail === null ||
    reportedBy === null ||
    typeof value.location_blocked !== 'boolean'
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    reference,
    property_id: propertyId,
    property_name: propertyName,
    space_id: spaceId,
    space_name: spaceName,
    bed_id: bedId,
    bed_name: bedName,
    resident_id: residentId,
    resident_name: residentName,
    description,
    priority,
    status,
    completion_note: completionNote,
    cost_amount: cost,
    currency_code: currency,
    assignee_id: assigneeId,
    assignee_email: assigneeEmail,
    reported_by_email: reportedBy,
    location_blocked: value.location_blocked,
    updates: value.updates.map(parseUpdate),
  }
}

export async function listMaintenanceRequests(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<MaintenanceRequestRecord[]> {
  const response = await request(`/api/v1/maintenance-requests/?${page}`, {
    workspaceId,
    signal,
  })
  const body = await readBody(response)
  if (!isRecord(body) || !Array.isArray(body.results)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return body.results.map(parseRequest)
}

export async function createMaintenanceRequest(
  workspaceId: string,
  input: {
    property_id?: string
    space_id?: string
    bed_id?: string
    resident_id?: string
    assignee_id?: string
    description: string
    priority: string
  },
): Promise<MaintenanceRequestRecord> {
  const response = await request('/api/v1/maintenance-requests/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseRequest(await readBody(response))
}

export async function updateMaintenanceRequest(
  workspaceId: string,
  requestId: string,
  input: {
    status?: string
    note?: string
    completion_note?: string
    cost_amount?: string
    assignee_id?: string | null
    priority?: string
    description?: string
  },
): Promise<MaintenanceRequestRecord> {
  const response = await request(`/api/v1/maintenance-requests/${requestId}/`, {
    method: 'PATCH',
    workspaceId,
    body: input,
  })
  return parseRequest(await readBody(response))
}
