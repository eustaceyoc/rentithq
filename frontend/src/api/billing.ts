import { ApiError } from './client'
import { errorFromResponse, request } from './session'

export type InvoiceLine = {
  description: string
  quantity: string
  unit_amount: string
  line_total: string
}

export type InvoiceRecord = {
  id: string
  reference: string
  resident_id: string
  resident_name: string
  tenancy_id: string | null
  issued_on: string
  due_on: string
  currency_code: string
  status: string
  lines: InvoiceLine[]
  total_amount: string
  allocated_amount: string
  outstanding_amount: string
  void_reason: string | null
}

export type PaymentAllocation = {
  id: string
  invoice_id: string
  invoice_reference: string
  amount: string
  reversed: boolean
}

export type PaymentRefund = {
  id: string
  amount: string
  refunded_on: string
  reason: string
  external_reference: string
}

export type PaymentRecord = {
  id: string
  reference: string
  resident_id: string
  resident_name: string
  amount: string
  currency_code: string
  paid_on: string
  method: string
  external_reference: string
  provider: string | null
  provider_reference: string | null
  provider_status: string | null
  status: string
  recorded_by_email: string
  allocated_amount: string
  refunded_amount: string
  unallocated_amount: string
  allocations: PaymentAllocation[]
  refunds: PaymentRefund[]
}

const page = 'page_size=100'

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

function parseLine(value: unknown): InvoiceLine {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const description = text(value, 'description')
  const quantity = text(value, 'quantity')
  const unitAmount = text(value, 'unit_amount')
  const lineTotal = text(value, 'line_total')
  if (
    description === null ||
    quantity === null ||
    unitAmount === null ||
    lineTotal === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    description,
    quantity,
    unit_amount: unitAmount,
    line_total: lineTotal,
  }
}

function parseInvoice(value: unknown): InvoiceRecord {
  if (!isRecord(value) || !Array.isArray(value.lines)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const reference = text(value, 'reference')
  const residentId = text(value, 'resident_id')
  const residentName = text(value, 'resident_name')
  const tenancyId = optionalText(value, 'tenancy_id')
  const issuedOn = text(value, 'issued_on')
  const dueOn = text(value, 'due_on')
  const currency = text(value, 'currency_code')
  const status = text(value, 'status')
  const total = text(value, 'total_amount')
  const allocated = text(value, 'allocated_amount')
  const outstanding = text(value, 'outstanding_amount')
  const voidReason = optionalText(value, 'void_reason')
  if (
    id === null ||
    reference === null ||
    residentId === null ||
    residentName === null ||
    tenancyId === undefined ||
    issuedOn === null ||
    dueOn === null ||
    currency === null ||
    status === null ||
    total === null ||
    allocated === null ||
    outstanding === null ||
    voidReason === undefined
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    reference,
    resident_id: residentId,
    resident_name: residentName,
    tenancy_id: tenancyId,
    issued_on: issuedOn,
    due_on: dueOn,
    currency_code: currency,
    status,
    lines: value.lines.map(parseLine),
    total_amount: total,
    allocated_amount: allocated,
    outstanding_amount: outstanding,
    void_reason: voidReason,
  }
}

function parseAllocation(value: unknown): PaymentAllocation {
  if (!isRecord(value) || typeof value.reversed !== 'boolean') {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const invoiceId = text(value, 'invoice_id')
  const invoiceReference = text(value, 'invoice_reference')
  const amount = text(value, 'amount')
  if (id === null || invoiceId === null || invoiceReference === null || amount === null) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    invoice_id: invoiceId,
    invoice_reference: invoiceReference,
    amount,
    reversed: value.reversed,
  }
}

function parseRefund(value: unknown): PaymentRefund {
  if (!isRecord(value)) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const amount = text(value, 'amount')
  const refundedOn = text(value, 'refunded_on')
  const reason = text(value, 'reason')
  const externalReference = text(value, 'external_reference')
  if (
    id === null ||
    amount === null ||
    refundedOn === null ||
    reason === null ||
    externalReference === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    amount,
    refunded_on: refundedOn,
    reason,
    external_reference: externalReference,
  }
}

function parsePayment(value: unknown): PaymentRecord {
  if (
    !isRecord(value) ||
    !Array.isArray(value.allocations) ||
    !Array.isArray(value.refunds)
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  const id = text(value, 'id')
  const reference = text(value, 'reference')
  const residentId = text(value, 'resident_id')
  const residentName = text(value, 'resident_name')
  const amount = text(value, 'amount')
  const currency = text(value, 'currency_code')
  const paidOn = text(value, 'paid_on')
  const method = text(value, 'method')
  const externalReference = text(value, 'external_reference')
  const provider = optionalText(value, 'provider')
  const providerReference = optionalText(value, 'provider_reference')
  const providerStatus = optionalText(value, 'provider_status')
  const status = text(value, 'status')
  const recordedBy = text(value, 'recorded_by_email')
  const allocated = text(value, 'allocated_amount')
  const refunded = text(value, 'refunded_amount')
  const unallocated = text(value, 'unallocated_amount')
  if (
    id === null ||
    reference === null ||
    residentId === null ||
    residentName === null ||
    amount === null ||
    currency === null ||
    paidOn === null ||
    method === null ||
    externalReference === null ||
    provider === undefined ||
    providerReference === undefined ||
    providerStatus === undefined ||
    status === null ||
    recordedBy === null ||
    allocated === null ||
    refunded === null ||
    unallocated === null
  ) {
    throw new ApiError('The API returned an unexpected response.')
  }
  return {
    id,
    reference,
    resident_id: residentId,
    resident_name: residentName,
    amount,
    currency_code: currency,
    paid_on: paidOn,
    method,
    external_reference: externalReference,
    provider,
    provider_reference: providerReference,
    provider_status: providerStatus,
    status,
    recorded_by_email: recordedBy,
    allocated_amount: allocated,
    refunded_amount: refunded,
    unallocated_amount: unallocated,
    allocations: value.allocations.map(parseAllocation),
    refunds: value.refunds.map(parseRefund),
  }
}

export async function listInvoices(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<InvoiceRecord[]> {
  const response = await request(`/api/v1/invoices/?${page}`, { workspaceId, signal })
  return readList(response, parseInvoice)
}

export async function createInvoice(
  workspaceId: string,
  input: {
    resident_id: string
    issued_on: string
    due_on: string
    from_tenancy?: boolean
    include_deposit?: boolean
    tenancy_id?: string
    lines?: { description: string; quantity: string; unit_amount: string }[]
  },
): Promise<InvoiceRecord> {
  const response = await request('/api/v1/invoices/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseInvoice(await readBody(response))
}

export async function voidInvoice(
  workspaceId: string,
  invoiceId: string,
  input: { reason: string; voided_on: string },
): Promise<InvoiceRecord> {
  const response = await request(`/api/v1/invoices/${invoiceId}/void/`, {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parseInvoice(await readBody(response))
}

export async function listPayments(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<PaymentRecord[]> {
  const response = await request(`/api/v1/payments/?${page}`, { workspaceId, signal })
  return readList(response, parsePayment)
}

export async function recordPayment(
  workspaceId: string,
  input: {
    resident_id: string
    amount: string
    paid_on: string
    method: string
    external_reference?: string
  },
): Promise<PaymentRecord> {
  const response = await request('/api/v1/payments/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parsePayment(await readBody(response))
}

export async function voidPayment(
  workspaceId: string,
  paymentId: string,
  input: { reason: string; voided_on: string },
): Promise<PaymentRecord> {
  const response = await request(`/api/v1/payments/${paymentId}/void/`, {
    method: 'POST',
    workspaceId,
    body: input,
  })
  return parsePayment(await readBody(response))
}

export async function refundPayment(
  workspaceId: string,
  paymentId: string,
  input: { amount: string; refunded_on: string; reason: string },
): Promise<void> {
  const response = await request(`/api/v1/payments/${paymentId}/refunds/`, {
    method: 'POST',
    workspaceId,
    body: input,
  })
  await readBody(response)
}

export async function allocatePayment(
  workspaceId: string,
  input: { payment_id: string; invoice_id: string; amount: string },
): Promise<void> {
  const response = await request('/api/v1/allocations/', {
    method: 'POST',
    workspaceId,
    body: input,
  })
  await readBody(response)
}

export async function reverseAllocation(
  workspaceId: string,
  allocationId: string,
  input: { reason: string; reversed_on: string },
): Promise<void> {
  const response = await request(`/api/v1/allocations/${allocationId}/reverse/`, {
    method: 'POST',
    workspaceId,
    body: input,
  })
  await readBody(response)
}

export async function listArrears(
  workspaceId: string,
  on: string,
  signal?: AbortSignal,
): Promise<InvoiceRecord[]> {
  const response = await request(`/api/v1/arrears/?on=${encodeURIComponent(on)}&${page}`, {
    workspaceId,
    signal,
  })
  return readList(response, parseInvoice)
}
