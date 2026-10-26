import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { PropertiesScreen } from './PropertiesScreen'

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body }
}

function page(results: unknown[]) {
  return jsonResponse({ count: results.length, next: null, previous: null, results })
}

const property = {
  id: 'prop-1',
  workspace_id: 'ws-ada',
  name: 'Harbour House',
  address: '1 Dock Street',
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

const bed = {
  id: 'bed-1',
  workspace_id: 'ws-ada',
  space_id: 'space-1',
  name: 'Bed A',
  availability: 'active',
  block_reason: '',
  created_at: '2026-10-23T00:00:00Z',
  updated_at: '2026-10-23T00:00:00Z',
}

describe('Properties screen', () => {
  it('shows a permission state and does not fetch for a resident', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    render(<PropertiesScreen workspaceId="ws-ada" role="resident" />)
    expect(
      screen.getByText(
        'Residents cannot view or manage properties, rooms, or beds.',
      ),
    ).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows a loading state', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    render(<PropertiesScreen workspaceId="ws-ada" role="owner" />)
    expect(screen.getByText('Loading properties…')).toBeInTheDocument()
  })

  it('shows an error state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('failed')),
    )
    render(<PropertiesScreen workspaceId="ws-ada" role="owner" />)
    expect(
      await screen.findByText('Properties could not be loaded'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Harbour House')).not.toBeInTheDocument()
  })

  it('shows an empty state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(page([])))
    render(<PropertiesScreen workspaceId="ws-ada" role="owner" />)
    expect(await screen.findByText(/No properties yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New property' })).toBeInTheDocument()
  })

  it('lets finance view a property without a create button', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(page([property])))
    render(<PropertiesScreen workspaceId="ws-ada" role="finance" />)
    expect(await screen.findByText('Harbour House')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Add property' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText(/Owners and property managers make changes/),
    ).toBeInTheDocument()
  })

  it('opens a room and its beds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/beds/')) {
          return page([bed])
        }
        if (url.includes('/spaces/')) {
          return page([room])
        }
        if (url.includes('/buildings/') || url.includes('/floors/')) {
          return page([])
        }
        return page([property])
      }),
    )
    render(<PropertiesScreen workspaceId="ws-ada" role="property_manager" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Open Harbour House' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Room 12 · Room' }))
    expect(await screen.findByText('Bed A')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add bed' })).toBeInTheDocument()
  })

  it('creates a property and shows the empty room state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? 'GET'
        if (url.includes('/auth/csrf/')) {
          return jsonResponse({ csrfToken: 'csrf-test' })
        }
        if (url.endsWith('/properties/') && method === 'POST') {
          return jsonResponse(property, true, 201)
        }
        if (url.includes('/buildings/') || url.includes('/floors/') || url.includes('/spaces/')) {
          return page([])
        }
        return page([property])
      }),
    )
    render(<PropertiesScreen workspaceId="ws-ada" role="owner" />)
    fireEvent.click(await screen.findByRole('button', { name: 'New property' }))
    fireEvent.change(await screen.findByLabelText('Property name'), {
      target: { value: 'Harbour House' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add property' }))
    expect(await screen.findByText(/No rooms or whole units yet/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Harbour House' })).toBeInTheDocument()
  })
})
