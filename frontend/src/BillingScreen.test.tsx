import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BillingScreen } from './BillingScreen'
import { resetApiState } from './api/session'

afterEach(() => {
  resetApiState()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body }
}

function page(results: unknown[]) {
  return jsonResponse({ count: results.length, next: null, previous: null, results })
}

const resident = {
  id: 'res-1',
  first_name: 'Ama',
  last_name: 'Mensah',
  email: 'ama@example.com',
  phone: '',
  account_email: '',
}

const invoice = {
  id: 'inv-1',
  reference: 'INV-0001',
  resident_id: 'res-1',
  resident_name: 'Ama Mensah',
  tenancy_id: null,
  issued_on: '2026-06-01',
  due_on: '2026-06-07',
  currency_code: 'GHS',
  status: 'issued',
  lines: [
    {
      description: 'June rent',
      quantity: '1.0000',
      unit_amount: '80.0000',
      line_total: '80.0000',
    },
  ],
  total_amount: '80.0000',
  allocated_amount: '0.0000',
  outstanding_amount: '80.0000',
  void_reason: null,
}

function emptyLists(url: string) {
  if (url.includes('/residents/')) {
    return page([resident])
  }
  if (url.includes('/invoices/')) {
    return page([invoice])
  }
  return page([])
}

describe('Billing screen', () => {
  it('shows a loading state', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    render(<BillingScreen workspaceId="ws-ada" role="owner" />)
    expect(screen.getByText('Loading invoices…')).toBeInTheDocument()
  })

  it('shows an empty state and records a card payment by hand', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/auth/csrf/')) {
          return jsonResponse({ csrfToken: 'csrf-test' })
        }
        if ((init?.method ?? 'GET') === 'POST' && url.includes('/payments/')) {
          bodies.push(JSON.parse(String(init?.body)))
          return jsonResponse(
            {
              id: 'pay-1',
              reference: 'PAY-0001',
              resident_id: 'res-1',
              resident_name: 'Ama Mensah',
              amount: '12.0000',
              currency_code: 'GHS',
              paid_on: '2026-06-02',
              method: 'card',
              external_reference: '',
              provider: null,
              provider_reference: null,
              provider_status: null,
              status: 'recorded',
              recorded_by_email: 'ada@example.com',
              allocated_amount: '0.0000',
              refunded_amount: '0.0000',
              unallocated_amount: '12.0000',
              allocations: [],
              refunds: [],
            },
            true,
            201,
          )
        }
        if (url.includes('/residents/')) {
          return page([resident])
        }
        if (url.includes('/payments/') && bodies.length > 0) {
          return page([
            {
              id: 'pay-1',
              reference: 'PAY-0001',
              resident_id: 'res-1',
              resident_name: 'Ama Mensah',
              amount: '12.0000',
              currency_code: 'GHS',
              paid_on: '2026-06-02',
              method: 'card',
              external_reference: '',
              provider: null,
              provider_reference: null,
              provider_status: null,
              status: 'recorded',
              recorded_by_email: 'ada@example.com',
              allocated_amount: '0.0000',
              refunded_amount: '0.0000',
              unallocated_amount: '12.0000',
              allocations: [],
              refunds: [],
            },
          ])
        }
        return page([])
      }),
    )
    render(<BillingScreen workspaceId="ws-ada" role="finance" />)
    expect(await screen.findByText(/No invoices yet/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Payments' }))
    expect(await screen.findByText(/No payments yet/)).toBeInTheDocument()
    fireEvent.mouseDown(screen.getByLabelText('Resident'))
    fireEvent.click(await screen.findByText('Ama Mensah', { selector: '.ant-select-item-option-content' }))
    fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '12.0000' } })
    fireEvent.change(screen.getByLabelText('Paid on'), { target: { value: '2026-06-02' } })
    fireEvent.mouseDown(screen.getByLabelText('Method'))
    fireEvent.click(await screen.findByText('Card', { selector: '.ant-select-item-option-content' }))
    fireEvent.click(screen.getByRole('button', { name: 'Record payment' }))
    expect(await screen.findByText(/Receipt PAY-0001/)).toBeInTheDocument()
    expect(bodies).toEqual([
      {
        resident_id: 'res-1',
        amount: '12.0000',
        paid_on: '2026-06-02',
        method: 'card',
      },
    ])
    expect(JSON.stringify(bodies[0])).not.toContain('provider')
  })

  it('shows an error and keeps a way to try again', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    render(<BillingScreen workspaceId="ws-ada" role="owner" />)
    expect(await screen.findByText('Invoices could not be loaded')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Issue invoice' })).not.toBeInTheDocument()
  })

  it('keeps a property manager on a view-only state', async () => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => Promise.resolve(emptyLists(String(input)))))
    render(<BillingScreen workspaceId="ws-ada" role="property_manager" />)
    expect(await screen.findByText(/INV-0001 · Ama Mensah/)).toBeInTheDocument()
    expect(screen.getAllByText(/80.00 GHS/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Recording money stays with the owner and finance/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Issue invoice' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Arrears' }))
    expect(await screen.findByText(/No one is in arrears on this date/)).toBeInTheDocument()
  })

  it('does not fetch money for maintenance', () => {
    const fetchMock = vi.fn(() => Promise.resolve(page([])))
    vi.stubGlobal('fetch', fetchMock)
    render(<BillingScreen workspaceId="ws-ada" role="maintenance" />)
    expect(screen.getByText('Maintenance cannot view invoices or payments.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows a resident their own invoice and does not ask for arrears', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/arrears/')) {
        throw new Error('resident fetched arrears')
      }
      if (url.includes('/invoices/')) {
        return Promise.resolve(page([invoice]))
      }
      return Promise.resolve(page([]))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<BillingScreen workspaceId="ws-ada" role="resident" />)
    expect(await screen.findByText(/INV-0001 · issued/)).toBeInTheDocument()
    expect(screen.getByText(/No payments are recorded for you yet/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Issue invoice' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Arrears' })).not.toBeInTheDocument()
  })
})
