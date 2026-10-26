import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReportsScreen } from './ReportsScreen'
import { resetApiState } from './api/session'

afterEach(() => {
  resetApiState()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function jsonResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => body,
    blob: async () => new Blob(['property_name\nHarbour House\n']),
  }
}

const occupancy = {
  on: '2026-06-10',
  within_days: 30,
  spaces: {
    unit: { occupied: 0, partly_occupied: 0, free: 1, unavailable: 0 },
    room: { occupied: 1, partly_occupied: 0, free: 0, unavailable: 0 },
  },
  beds: { occupied: 0, free: 0, unavailable: 0 },
  properties: [
    {
      property_id: 'prop-1',
      property_name: 'Harbour House',
      occupied: 1,
      partly_occupied: 0,
      free: 0,
      unavailable: 0,
    },
  ],
  active_tenancies: 0,
  active_residents: 0,
  upcoming_count: 1,
  upcoming_truncated: false,
  upcoming_move_outs: [
    {
      kind: 'booking',
      resident_name: 'Ama Mensah',
      label: 'Room 1',
      end_date: '2026-06-20',
    },
  ],
}

const arrears = {
  on: '2026-06-08',
  currency_code: 'GHS',
  invoice_count: 1,
  outstanding_amount: '80.0000',
  residents: [
    {
      resident_id: 'res-1',
      resident_name: 'Ama Mensah',
      invoice_count: 1,
      outstanding_amount: '80.0000',
    },
  ],
}

const collections = {
  from: '2026-06-01',
  to: '2026-06-30',
  currency_code: 'GHS',
  payment_count: 1,
  collected_amount: '30.0000',
  refund_count: 0,
  refunded_amount: '0.0000',
  net_amount: '30.0000',
  by_method: [{ method: 'cash', count: 1, amount: '30.0000' }],
}

const maintenance = {
  scope: 'workspace',
  counts: { open: 1, assigned: 0, in_progress: 0, completed: 0, cancelled: 0 },
  open_count: 1,
  by_priority: { low: 0, normal: 0, high: 0, urgent: 1 },
}

describe('Reports screen', () => {
  it('does not fetch reports for a resident', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<ReportsScreen workspaceId="ws-ada" role="resident" />)
    expect(screen.getByText(/Reports stay with the staff/)).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows workspace totals with currency minor units', async () => {
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        urls.push(url)
        if (url.includes('/reports/occupancy')) {
          return Promise.resolve(jsonResponse(occupancy))
        }
        if (url.includes('/reports/arrears')) {
          return Promise.resolve(jsonResponse(arrears))
        }
        if (url.includes('/reports/collections')) {
          return Promise.resolve(jsonResponse(collections))
        }
        return Promise.resolve(jsonResponse(maintenance))
      }),
    )
    render(<ReportsScreen workspaceId="ws-ada" role="owner" />)
    expect(await screen.findByText(/Harbour House: occupied 1/)).toBeInTheDocument()
    expect(screen.getByText(/80.00 GHS outstanding/)).toBeInTheDocument()
    expect(screen.getByText(/Collected 30.00 GHS/)).toBeInTheDocument()
    expect(screen.getByText(/Open work 1/)).toBeInTheDocument()
    expect(screen.queryByText(/80.0000/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Download arrears CSV' }))
    await waitFor(() => {
      expect(urls.some((url) => url.includes('export=csv'))).toBe(true)
    })
  })

  it('does not fetch money reports for maintenance staff', async () => {
    const urls: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        urls.push(url)
        if (url.includes('/reports/arrears') || url.includes('/reports/collections')) {
          throw new Error('maintenance fetched money totals')
        }
        if (url.includes('/reports/occupancy')) {
          return Promise.resolve(jsonResponse({ ...occupancy, properties: [] }))
        }
        return Promise.resolve(
          jsonResponse({ ...maintenance, scope: 'assigned', open_count: 0 }),
        )
      }),
    )
    render(<ReportsScreen workspaceId="ws-ada" role="maintenance" />)
    expect(await screen.findByText(/only the requests you can see/)).toBeInTheDocument()
    expect(screen.queryByText(/Arrears on/)).not.toBeInTheDocument()
    expect(urls.some((url) => url.includes('/reports/arrears'))).toBe(false)
  })

  it('shows an error and a way to try again', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    render(<ReportsScreen workspaceId="ws-ada" role="finance" />)
    expect(await screen.findByText('Reports could not be loaded')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
