import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MaintenanceScreen } from './MaintenanceScreen'
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

const request = {
  id: 'mnt-1',
  reference: 'MNT-0001',
  property_id: 'prop-1',
  property_name: 'Harbour House',
  space_id: null,
  space_name: '',
  bed_id: null,
  bed_name: '',
  resident_id: 'res-1',
  resident_name: 'Ama Mensah',
  description: 'The tap drips.',
  priority: 'high',
  status: 'open',
  completion_note: '',
  cost_amount: null,
  currency_code: 'GHS',
  assignee_id: null,
  assignee_email: '',
  reported_by_email: 'ada@example.com',
  location_blocked: false,
  updates: [
    {
      id: 'upd-1',
      status_before: '',
      status_after: 'open',
      note: 'Request opened.',
      cost_amount: null,
      assignee_id: null,
      actor_email: 'ada@example.com',
      created_at: '2026-06-01T00:00:00Z',
    },
  ],
}

describe('Maintenance screen', () => {
  it('shows a loading state', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    render(<MaintenanceScreen workspaceId="ws-ada" role="owner" />)
    expect(screen.getByText('Loading maintenance requests…')).toBeInTheDocument()
  })

  it('shows an empty state', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(page([]))))
    render(<MaintenanceScreen workspaceId="ws-ada" role="owner" />)
    expect(await screen.findByText('No maintenance requests yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'File request' })).toBeInTheDocument()
  })

  it('lets a resident file without loading the property catalogue', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/properties/') || url.includes('/spaces/') || url.includes('/beds/')) {
        throw new Error('resident fetched the property catalogue')
      }
      if (url.includes('/maintenance-requests/')) {
        return Promise.resolve(page([request]))
      }
      return Promise.resolve(page([]))
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MaintenanceScreen workspaceId="ws-ada" role="resident" />)
    expect(await screen.findByText(/MNT-0001 · high · open/)).toBeInTheDocument()
    expect(screen.getByText('The tap drips.')).toBeInTheDocument()
    expect(screen.getByText(/Request opened/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Property')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save MNT-0001' })).not.toBeInTheDocument()
  })

  it('shows an error and a way to try again', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    render(<MaintenanceScreen workspaceId="ws-ada" role="maintenance" />)
    expect(await screen.findByText('Maintenance requests could not be loaded')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })

  it('keeps a failed update on screen', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/auth/csrf/')) {
          return jsonResponse({ csrfToken: 'csrf-test' })
        }
        if ((init?.method ?? 'GET') === 'PATCH') {
          return jsonResponse(
            {
              error: {
                code: 'validation_error',
                message: 'The request could not be processed.',
                details: { status: 'That status change is not allowed.' },
              },
            },
            false,
            400,
          )
        }
        if (url.includes('/maintenance-requests/')) {
          return page([request])
        }
        return page([])
      }),
    )
    render(<MaintenanceScreen workspaceId="ws-ada" role="owner" />)
    expect(await screen.findByText(/MNT-0001 · high · open/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Save MNT-0001' }))
    expect(await screen.findByText(/That status change is not allowed/)).toBeInTheDocument()
    expect(screen.getByText('The tap drips.')).toBeInTheDocument()
  })
})
