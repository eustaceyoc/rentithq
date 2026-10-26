import { ApiError } from './client'
import { errorFromResponse, request } from './session'

export type ResidentRecord = {
  id: string
  first_name: string
  last_name: string
  email: string
  phone: string
  account_email: string
}

export type BookingRecord = {
  id: string
  resident_id: string
  resident_name: string
  status: string
  start_date: string
  end_date: string | null
  assignment_id: string | null
  space_id: string | null
  bed_id: string | null
}

export type TenancyRecord = {
  id: string
  resident_id: string
  resident_name: string
  status: string
  start_date: string
  end_date: string | null
  ended_on: string | null
  fee_amount: string
  fee_period: string
  deposit_amount: string
  currency_code: string
}

export type AssignmentRecord = {
  id: string
  resident_id: string
  resident_name: string
  space_id: string
  space_name: string
  bed_id: string | null
  bed_name: string | null
  status: string
  start_date: string
  end_date: string | null
  tenancy_id: string | null
  booking_id: string | null
}

export type AvailabilityRow = {
  on: string
  space_id: string
  space_name: string
  space_kind: string
  bed_id: string | null
  bed_name: string | null
  state: string
  resident_name: string | null
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function text(value: Record<string, unknown>, key: string): string | null {
  const field = value[key]
  return typeof field === 'string' ? field : null
}

function optionalText(
  value: Record<string, unknown>,
  key: string,
): string | null | undefined {
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
  if (response.status === 204) {
    return null
  }
  try {
    return await response.json()
  } catch {
    throw new ApiError('The API returned an unexpected response.')
  }
}

function pageItems(body: unknown): unknown[] {
  if (!isRecord(body) || !Array.isArray(body.results)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return body.results
}

async function readList<T>(
  response: Response,
  parse: (value: unknown) => T,
): Promise<T[]> {
  return pageItems(await readBody(response)).map(parse)
}

function parseResident(value: unknown): ResidentRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const firstName = text(value, 'first_name')
  const lastName = text(value, 'last_name')
  const email = text(value, 'email')
  const phone = text(value, 'phone')
  const accountEmail = text(value, 'account_email')
  if (
    id === null ||
    firstName === null ||
    lastName === null ||
    email === null ||
    phone === null ||
    accountEmail === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    first_name: firstName,
    last_name: lastName,
    email,
    phone,
    account_email: accountEmail,
  }
}

function parseBooking(value: unknown): BookingRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const residentId = text(value, 'resident_id')
  const residentName = text(value, 'resident_name')
  const status = text(value, 'status')
  const startDate = text(value, 'start_date')
  const endDate = optionalText(value, 'end_date')
  const assignmentId = optionalText(value, 'assignment_id')
  const spaceId = optionalText(value, 'space_id')
  const bedId = optionalText(value, 'bed_id')
  if (
    id === null ||
    residentId === null ||
    residentName === null ||
    status === null ||
    startDate === null ||
    endDate === undefined ||
    assignmentId === undefined ||
    spaceId === undefined ||
    bedId === undefined
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    resident_id: residentId,
    resident_name: residentName,
    status,
    start_date: startDate,
    end_date: endDate,
    assignment_id: assignmentId,
    space_id: spaceId,
    bed_id: bedId,
  }
}

function parseTenancy(value: unknown): TenancyRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const residentId = text(value, 'resident_id')
  const residentName = text(value, 'resident_name')
  const status = text(value, 'status')
  const startDate = text(value, 'start_date')
  const endDate = optionalText(value, 'end_date')
  const endedOn = optionalText(value, 'ended_on')
  const feeAmount = text(value, 'fee_amount')
  const feePeriod = text(value, 'fee_period')
  const depositAmount = text(value, 'deposit_amount')
  const currency = text(value, 'currency_code')
  if (
    id === null ||
    residentId === null ||
    residentName === null ||
    status === null ||
    startDate === null ||
    endDate === undefined ||
    endedOn === undefined ||
    feeAmount === null ||
    feePeriod === null ||
    depositAmount === null ||
    currency === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    resident_id: residentId,
    resident_name: residentName,
    status,
    start_date: startDate,
    end_date: endDate,
    ended_on: endedOn,
    fee_amount: feeAmount,
    fee_period: feePeriod,
    deposit_amount: depositAmount,
    currency_code: currency,
  }
}

function parseAssignment(value: unknown): AssignmentRecord {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const residentId = text(value, 'resident_id')
  const residentName = text(value, 'resident_name')
  const spaceId = text(value, 'space_id')
  const spaceName = text(value, 'space_name')
  const bedId = optionalText(value, 'bed_id')
  const bedName = optionalText(value, 'bed_name')
  const status = text(value, 'status')
  const startDate = text(value, 'start_date')
  const endDate = optionalText(value, 'end_date')
  const tenancyId = optionalText(value, 'tenancy_id')
  const bookingId = optionalText(value, 'booking_id')
  if (
    id === null ||
    residentId === null ||
    residentName === null ||
    spaceId === null ||
    spaceName === null ||
    bedId === undefined ||
    bedName === undefined ||
    status === null ||
    startDate === null ||
    endDate === undefined ||
    tenancyId === undefined ||
    bookingId === undefined
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    resident_id: residentId,
    resident_name: residentName,
    space_id: spaceId,
    space_name: spaceName,
    bed_id: bedId,
    bed_name: bedName,
    status,
    start_date: startDate,
    end_date: endDate,
    tenancy_id: tenancyId,
    booking_id: bookingId,
  }
}

function parseAvailability(value: unknown): AvailabilityRow {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const on = text(value, 'on')
  const spaceId = text(value, 'space_id')
  const spaceName = text(value, 'space_name')
  const spaceKind = text(value, 'space_kind')
  const bedId = optionalText(value, 'bed_id')
  const bedName = optionalText(value, 'bed_name')
  const state = text(value, 'state')
  const residentName = optionalText(value, 'resident_name')
  if (
    on === null ||
    spaceId === null ||
    spaceName === null ||
    spaceKind === null ||
    bedId === undefined ||
    bedName === undefined ||
    state === null ||
    residentName === undefined
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    on,
    space_id: spaceId,
    space_name: spaceName,
    space_kind: spaceKind,
    bed_id: bedId,
    bed_name: bedName,
    state,
    resident_name: residentName,
  }
}

const page = 'page_size=100'

export async function listResidents(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<ResidentRecord[]> {
  const response = await request(`/api/v1/residents/?${page}`, {
    workspaceId,
    signal,
  })
  return readList(response, parseResident)
}

export async function updateOwnContact(
  workspaceId: string,
  residentId: string,
  input: { phone: string; email: string },
): Promise<ResidentRecord> {
  const response = await request(`/api/v1/residents/${residentId}/`, {
    method: 'PATCH',
    workspaceId,
    body: {
      phone: input.phone,
      email: input.email,
    },
  })
  return parseResident(await readBody(response))
}

export async function updateResident(
  workspaceId: string,
  residentId: string,
  input: {
    first_name: string
    last_name: string
    email: string
    phone: string
    account_email: string
  },
): Promise<ResidentRecord> {
  const response = await request(`/api/v1/residents/${residentId}/`, {
    method: 'PATCH',
    workspaceId,
    body: input,
  })
  return parseResident(await readBody(response))
}

export async function createResident(
  workspaceId: string,
  input: {
    first_name: string
    last_name: string
    email: string
    phone: string
    account_email: string
  },
): Promise<ResidentRecord> {
  const response = await request('/api/v1/residents/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseResident(await readBody(response))
}

export async function listBookings(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<BookingRecord[]> {
  const response = await request(`/api/v1/bookings/?${page}`, {
    workspaceId,
    signal,
  })
  return readList(response, parseBooking)
}

export async function createBooking(
  workspaceId: string,
  input: {
    resident_id: string
    space_id: string
    bed_id: string | null
    start_date: string
    end_date: string | null
  },
): Promise<BookingRecord> {
  const response = await request('/api/v1/bookings/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseBooking(await readBody(response))
}

export async function cancelBooking(
  workspaceId: string,
  bookingId: string,
): Promise<BookingRecord> {
  const response = await request(`/api/v1/bookings/${bookingId}/cancel/`, {
    method: 'POST',
    workspaceId,
    body: {},
  })
  return parseBooking(await readBody(response))
}

export async function convertBooking(
  workspaceId: string,
  bookingId: string,
  input: {
    fee_amount: string
    fee_period: string
    deposit_amount: string
    check_in: boolean
  },
): Promise<TenancyRecord> {
  const response = await request(`/api/v1/bookings/${bookingId}/convert/`, {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseTenancy(await readBody(response))
}

export async function listTenancies(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<TenancyRecord[]> {
  const response = await request(`/api/v1/tenancies/?${page}`, {
    workspaceId,
    signal,
  })
  return readList(response, parseTenancy)
}

export async function createTenancy(
  workspaceId: string,
  input: {
    resident_id: string
    space_id: string
    bed_id: string | null
    start_date: string
    end_date: string | null
    fee_amount: string
    fee_period: string
    deposit_amount: string
    check_in: boolean
  },
): Promise<TenancyRecord> {
  const response = await request('/api/v1/tenancies/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseTenancy(await readBody(response))
}

export async function cancelTenancy(
  workspaceId: string,
  tenancyId: string,
): Promise<TenancyRecord> {
  const response = await request(`/api/v1/tenancies/${tenancyId}/cancel/`, {
    method: 'POST',
    workspaceId,
    body: {},
  })
  return parseTenancy(await readBody(response))
}

export async function endTenancy(
  workspaceId: string,
  tenancyId: string,
  endedOn: string,
): Promise<TenancyRecord> {
  const response = await request(`/api/v1/tenancies/${tenancyId}/end/`, {
    method: 'POST',
    workspaceId,
    body: { ended_on: endedOn },
  })
  return parseTenancy(await readBody(response))
}

export async function listAssignments(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<AssignmentRecord[]> {
  const response = await request(`/api/v1/assignments/?${page}`, {
    workspaceId,
    signal,
  })
  return readList(response, parseAssignment)
}

export async function updateAssignment(
  workspaceId: string,
  assignmentId: string,
  input: { start_date: string; end_date: string | null },
): Promise<AssignmentRecord> {
  const response = await request(`/api/v1/assignments/${assignmentId}/`, {
    method: 'PATCH',
    workspaceId,
    body: input,
  })
  return parseAssignment(await readBody(response))
}

export async function cancelAssignment(
  workspaceId: string,
  assignmentId: string,
): Promise<AssignmentRecord> {
  const response = await request(
    `/api/v1/assignments/${assignmentId}/cancel/`,
    { method: 'POST', workspaceId, body: {} },
  )
  return parseAssignment(await readBody(response))
}

export async function checkInAssignment(
  workspaceId: string,
  assignmentId: string,
): Promise<AssignmentRecord> {
  const response = await request(
    `/api/v1/assignments/${assignmentId}/check-in/`,
    { method: 'POST', workspaceId, body: {} },
  )
  return parseAssignment(await readBody(response))
}

export async function checkOutAssignment(
  workspaceId: string,
  assignmentId: string,
  endDate: string,
): Promise<AssignmentRecord> {
  const response = await request(
    `/api/v1/assignments/${assignmentId}/check-out/`,
    { method: 'POST', workspaceId, body: { end_date: endDate } },
  )
  return parseAssignment(await readBody(response))
}

export async function transferAssignment(
  workspaceId: string,
  assignmentId: string,
  input: { space_id: string; bed_id: string | null; start_date: string },
): Promise<AssignmentRecord> {
  const response = await request(
    `/api/v1/assignments/${assignmentId}/transfer/`,
    { method: 'POST', workspaceId, body: input },
  )
  return parseAssignment(await readBody(response))
}

export async function listAvailability(
  workspaceId: string,
  on: string,
  signal?: AbortSignal,
): Promise<AvailabilityRow[]> {
  const response = await request(
    `/api/v1/availability/?on=${encodeURIComponent(on)}&${page}`,
    { workspaceId, signal },
  )
  return readList(response, parseAvailability)
}
