import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { OccupancyScreen } from './OccupancyScreen'

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body }
}

function page(results: unknown[]) {
  return jsonResponse({ count: results.length, next: null, previous: null, results })
}

const resident = {
  id: 'res-1',
  workspace_id: 'ws-ada',
  user_id: null,
  account_email: '',
  first_name: 'Ama',
  last_name: 'Mensah',
  email: 'ama@example.com',
  phone: '+233200000000',
  created_at: '2026-10-23T00:00:00Z',
  updated_at: '2026-10-23T00:00:00Z',
}

const room = {
  id: 'space-1',
  workspace_id: 'ws-ada',
  property_id: 'prop-1',
  building_id: null,
  floor_id: null,
  name: 'Room 12',
  kind: 'room',
  availability: 'active',
  block_reason: '',
  created_at: '2026-10-23T00:00:00Z',
  updated_at: '2026-10-23T00:00:00Z',
}

const stay = {
  id: 'stay-1',
  workspace_id: 'ws-ada',
  resident_id: 'res-1',
  resident_name: 'Ama Mensah',
  space_id: 'space-1',
  space_name: 'Room 12',
  bed_id: 'bed-1',
  bed_name: 'Bed A',
  booking_id: null,
  tenancy_id: 'ten-1',
  transferred_from_id: null,
  status: 'active',
  start_date: '2026-06-01',
  end_date: '2026-06-30',
  created_at: '2026-10-23T00:00:00Z',
  updated_at: '2026-10-23T00:00:00Z',
}

describe('Occupancy screen', () => {
  it('shows a loading state for residents', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    render(<OccupancyScreen workspaceId="ws-ada" role="owner" />)
    expect(screen.getByText('Loading residents…')).toBeInTheDocument()
  })

  it('shows an empty state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(page([])))
    render(<OccupancyScreen workspaceId="ws-ada" role="owner" />)
    expect(await screen.findByText(/No residents yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add resident' })).toBeInTheDocument()
  })

  it('shows an error state without dropping the form', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    render(<OccupancyScreen workspaceId="ws-ada" role="owner" />)
    expect(await screen.findByText('Residents could not be loaded')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add resident' })).toBeInTheDocument()
  })

  it('keeps finance on a view-only permission state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(page([resident])))
    render(<OccupancyScreen workspaceId="ws-ada" role="finance" />)
    expect(await screen.findByText(/Ama Mensah/)).toBeInTheDocument()
    expect(screen.getByText('View only')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add resident' })).not.toBeInTheDocument()
  })

  it('shows a resident only their own stay', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/properties/') || url.includes('/availability/')) {
        throw new Error('resident fetched staff records')
      }
      if (url.includes('/residents/')) {
        return page([resident])
      }
      if (url.includes('/tenancies/')) {
        return page([
          {
            id: 'ten-1',
            resident_id: 'res-1',
            resident_name: 'Ama Mensah',
            status: 'active',
            start_date: '2026-06-01',
            end_date: '2026-06-30',
            ended_on: null,
            fee_amount: '800.0000',
            fee_period: 'month',
            deposit_amount: '200.0000',
            currency_code: 'GHS',
          },
        ])
      }
      if (url.includes('/assignments/')) {
        return page([stay])
      }
      return page([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<OccupancyScreen workspaceId="ws-ada" role="resident" />)
    expect(await screen.findByRole('heading', { name: 'Your stay' })).toBeInTheDocument()
    expect(screen.getByText(/Ama Mensah/)).toBeInTheDocument()
    expect(screen.getByText(/800.00 GHS per month/)).toBeInTheDocument()
    expect(screen.getByText(/Room 12 · Bed A · active/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Residents' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add resident' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save contact details' })).toBeInTheDocument()
    expect(screen.getByLabelText('Phone')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.queryByLabelText('First name')).not.toBeInTheDocument()
  })

  it('shows a booking conflict and keeps the reservation list', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      if (url.endsWith('/api/v1/bookings/') && method === 'POST') {
        return jsonResponse(
          {
            error: {
              code: 'validation_error',
              message: 'The request could not be processed.',
              details: { detail: 'That space is already occupied for those dates.' },
            },
          },
          false,
          400,
        )
      }
      if (url.includes('/auth/csrf/')) {
        return jsonResponse({ csrfToken: 'csrf-test' })
      }
      if (url.includes('/bookings/')) {
        return page([
          {
            id: 'book-1',
            resident_id: 'res-1',
            resident_name: 'Ama Mensah',
            status: 'confirmed',
            start_date: '2026-06-01',
            end_date: '2026-06-03',
            assignment_id: 'stay-1',
            space_id: 'space-1',
            bed_id: null,
          },
        ])
      }
      if (url.includes('/residents/')) {
        return page([resident])
      }
      if (url.includes('/properties/')) {
        return page([
          {
            id: 'prop-1',
            name: 'Harbour House',
            address: '1 Dock Street',
          },
        ])
      }
      if (url.includes('/spaces/')) {
        return page([room])
      }
      if (url.includes('/beds/')) {
        return page([])
      }
      return page([])
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<OccupancyScreen workspaceId="ws-ada" role="property_manager" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Bookings' }))
    expect(await screen.findByText(/Ama Mensah · confirmed/)).toBeInTheDocument()
    expect(await screen.findByText(/Room 12/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'New reservation' }))
    fireEvent.mouseDown(await screen.findByLabelText('Resident'))
    fireEvent.click(await screen.findByText('Ama Mensah', { selector: '.ant-select-item-option-content' }))
    fireEvent.mouseDown(screen.getByLabelText('Space'))
    fireEvent.click(await screen.findByText(/Room 12 · Room/))
    fireEvent.change(screen.getByLabelText('Start date'), {
      target: { value: '2026-06-01' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add reservation' }))
    expect(
      await screen.findByText('That space is already occupied for those dates.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Ama Mensah · confirmed/)).toBeInTheDocument()
  })

  it('checks a resident out of one stay without using another stay’s date', async () => {
    const calls: string[] = []
    let checkedOut = false
    const other = {
      ...stay,
      id: 'stay-2',
      resident_name: 'Kojo Boateng',
      bed_id: 'bed-2',
      bed_name: 'Bed B',
      start_date: '2026-07-01',
      end_date: '2026-07-31',
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? 'GET'
        if (url.includes('/auth/csrf/')) {
          return jsonResponse({ csrfToken: 'csrf-test' })
        }
        if (url.includes('/check-out/') && method === 'POST') {
          calls.push(String(init?.body))
          checkedOut = true
          return jsonResponse({
            ...stay,
            status: 'checked_out',
            end_date: '2026-06-04',
          })
        }
        if (url.includes('/assignments/')) {
          return page([
            checkedOut ? { ...stay, status: 'checked_out', end_date: '2026-06-04' } : stay,
            other,
          ])
        }
        if (url.includes('/properties/')) {
          return page([{ id: 'prop-1', name: 'Harbour House', address: '' }])
        }
        if (url.includes('/spaces/')) {
          return page([room])
        }
        if (url.includes('/beds/')) {
          return page([])
        }
        return page([])
      }),
    )
    render(<OccupancyScreen workspaceId="ws-ada" role="owner" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Stays' }))
    const amaEnd = await screen.findByLabelText('Last occupied day for Ama Mensah')
    const kojoEnd = screen.getByLabelText('Last occupied day for Kojo Boateng')
    fireEvent.change(amaEnd, { target: { value: '2026-06-04' } })
    fireEvent.change(kojoEnd, { target: { value: '2026-07-15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Check out Ama Mensah' }))
    expect(await screen.findByText(/checked_out/)).toBeInTheDocument()
    expect(calls).toEqual(['{"end_date":"2026-06-04"}'])
  })

  it('shows availability states for a chosen day', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/availability/')) {
          expect(url).toContain('on=2026-06-02')
          return page([
            {
              on: '2026-06-02',
              space_id: 'space-1',
              space_name: 'Room 12',
              space_kind: 'room',
              bed_id: null,
              bed_name: null,
              state: 'partly_occupied',
              resident_name: null,
            },
            {
              on: '2026-06-02',
              space_id: 'space-1',
              space_name: 'Room 12',
              space_kind: 'room',
              bed_id: 'bed-1',
              bed_name: 'Bed A',
              state: 'occupied',
              resident_name: 'Ama Mensah',
            },
            {
              on: '2026-06-02',
              space_id: 'space-2',
              space_name: 'Store',
              space_kind: 'unit',
              bed_id: null,
              bed_name: null,
              state: 'unavailable',
              resident_name: null,
            },
          ])
        }
        return page([])
      }),
    )
    render(<OccupancyScreen workspaceId="ws-ada" role="maintenance" />)
    fireEvent.click(screen.getByRole('button', { name: 'Availability' }))
    fireEvent.change(screen.getByLabelText('Availability date'), {
      target: { value: '2026-06-02' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Show availability' }))
    expect(await screen.findByText(/Not free to book as a whole/)).toBeInTheDocument()
    expect(screen.getByText(/Bed A · Occupied · Ama Mensah/)).toBeInTheDocument()
    expect(screen.getByText(/Store · Unavailable/)).toBeInTheDocument()
  })
})
