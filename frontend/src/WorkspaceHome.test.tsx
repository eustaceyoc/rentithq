import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { resetApiState, type WorkspaceSummary } from './api/session'
import { LoginPage } from './pages/LoginPage'
import { WorkspaceHome } from './WorkspaceHome'

function renderHome() {
  return render(
    <MemoryRouter initialEntries={['/app']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app/*" element={<WorkspaceHome />} />
      </Routes>
    </MemoryRouter>,
  )
}

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
  }
}

const user = {
  id: 'user-1',
  email: 'ada@example.com',
  first_name: 'Ada',
  last_name: 'Lovelace',
}

function workspace(name: string, id: string): WorkspaceSummary {
  return {
    id,
    name,
    currency_code: 'GHS',
    timezone: 'Africa/Accra',
    status: 'active',
  }
}

function sessionResponse(memberships: ReturnType<typeof membership>[]) {
  return jsonResponse({ user, memberships })
}

function membership(name: string, id: string, role: string) {
  return { id: `membership-${id}`, role, workspace: workspace(name, id) }
}

describe('Workspace home', () => {
  it('starts by checking the session', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    renderHome()
    expect(screen.getByText('Checking your session…')).toBeInTheDocument()
  })

  it('shows sign in when there is no session', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: 'not_authenticated',
              message: 'Authentication is required.',
              details: {},
            },
          },
          false,
          403,
        ),
      ),
    )
    renderHome()
    expect(
      await screen.findByRole('heading', { name: 'Sign in' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create an account' })).toBeInTheDocument()
  })

  it('asks for a workspace when the account has none', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sessionResponse([])))
    renderHome()
    expect(
      await screen.findByRole('heading', { name: 'Create a workspace' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/You do not belong to a workspace yet/)).toBeInTheDocument()
  })

  it('asks which workspace to open and hides workspaces that were not returned', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sessionResponse([
          membership('Ada House', 'ws-ada', 'owner'),
          membership('Bea House', 'ws-bea', 'resident'),
        ]),
      ),
    )
    renderHome()
    expect(
      await screen.findByRole('heading', { name: 'Choose a workspace' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ada House · Owner' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Bea House · Resident' }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Hidden Hostel/)).not.toBeInTheDocument()
  })

  it('shows a session failure without dumping the payload', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ status: 1, detail: 'secret-trace' }),
      ),
    )
    renderHome()
    expect(
      await screen.findByText('Your session could not be checked.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/secret-trace/)).not.toBeInTheDocument()
  })

  it('signs in without writing the password to local storage', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    let signedIn = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        const method = init?.method ?? 'GET'
        if (url.includes('/auth/csrf/')) {
          return jsonResponse({ csrfToken: 'csrf-test' })
        }
        if (url.includes('/auth/login/') && method === 'POST') {
          const body = JSON.parse(String(init?.body)) as { password?: string }
          expect(body.password).toBe('correct-horse-battery')
          signedIn = true
          return sessionResponse([])
        }
        if (url.includes('/auth/session/') && signedIn) {
          return sessionResponse([])
        }
        return jsonResponse(
          {
            error: {
              code: 'not_authenticated',
              message: 'Authentication is required.',
              details: {},
            },
          },
          false,
          403,
        )
      }),
    )
    renderHome()
    fireEvent.change(await screen.findByLabelText('Email'), {
      target: { value: 'ada@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'correct-horse-battery' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(
      await screen.findByRole('heading', { name: 'Create a workspace' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('correct-horse-battery')).not.toBeInTheDocument()
    expect(setItem).not.toHaveBeenCalled()
  })

  it('requests members with the selected workspace header', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/memberships/')) {
        const headers = new Headers(init?.headers)
        expect(headers.get('X-Workspace-Id')).toBe('ws-ada')
        return jsonResponse({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'membership-ws-ada',
              role: 'owner',
              user,
            },
          ],
        })
      }
      if (url.includes('/reports/maintenance')) {
        return jsonResponse({
          scope: 'workspace',
          counts: { open: 0, assigned: 0, in_progress: 0, completed: 0, cancelled: 0 },
          open_count: 0,
          by_priority: { low: 0, normal: 0, high: 0, urgent: 0 },
        })
      }
      if (url.includes('/reports/arrears')) {
        return jsonResponse({
          on: '2026-10-23',
          currency_code: 'GHS',
          invoice_count: 0,
          outstanding_amount: '0.0000',
          residents: [],
        })
      }
      if (url.includes('/reports/collections')) {
        return jsonResponse({
          from: '2026-10-23',
          to: '2026-10-23',
          currency_code: 'GHS',
          payment_count: 0,
          collected_amount: '0.0000',
          refund_count: 0,
          refunded_amount: '0.0000',
          net_amount: '0.0000',
          by_method: [],
        })
      }
      if (url.includes('/reports/occupancy')) {
        return jsonResponse({
          on: '2026-10-23',
          within_days: 30,
          spaces: {
            unit: { occupied: 0, partly_occupied: 0, free: 0, unavailable: 0 },
            room: { occupied: 0, partly_occupied: 0, free: 0, unavailable: 0 },
          },
          beds: { occupied: 0, free: 0, unavailable: 0 },
          properties: [],
          active_tenancies: 0,
          active_residents: 0,
          upcoming_count: 0,
          upcoming_truncated: false,
          upcoming_move_outs: [],
        })
      }
      if (
        url.includes('/properties/') ||
        url.includes('/buildings/') ||
        url.includes('/floors/') ||
        url.includes('/spaces/') ||
        url.includes('/beds/') ||
        url.includes('/residents/') ||
        url.includes('/bookings/') ||
        url.includes('/tenancies/') ||
        url.includes('/assignments/') ||
        url.includes('/invoices/') ||
        url.includes('/payments/') ||
        url.includes('/arrears/') ||
        url.includes('/maintenance-requests/')
      ) {
        return jsonResponse({ count: 0, next: null, previous: null, results: [] })
      }
      return sessionResponse([
        membership('Ada House', 'ws-ada', 'owner'),
        membership('Bea House', 'ws-bea', 'resident'),
      ])
    })
    vi.stubGlobal('fetch', fetchMock)
    renderHome()
    fireEvent.click(await screen.findByRole('button', { name: 'Ada House · Owner' }))
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.queryByText(/Bea House/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    fireEvent.click(await screen.findByRole('link', { name: 'Properties' }))
    expect(await screen.findByText(/No properties yet/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    fireEvent.click(await screen.findByRole('link', { name: 'Residents' }))
    expect(await screen.findByText(/No residents yet/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    fireEvent.click(await screen.findByRole('link', { name: 'Settings' }))
    expect(await screen.findAllByText('ada@example.com')).not.toHaveLength(0)
  })

  it('does not load properties for a resident', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (
        url.includes('/properties/') ||
        url.includes('/spaces/') ||
        url.includes('/bookings/') ||
        url.includes('/availability/') ||
        url.includes('/arrears/') ||
        url.includes('/reports/')
      ) {
        throw new Error('resident fetched staff records')
      }
      if (
        url.includes('/residents/') ||
        url.includes('/tenancies/') ||
        url.includes('/assignments/') ||
        url.includes('/invoices/') ||
        url.includes('/payments/') ||
        url.includes('/maintenance-requests/') ||
        url.includes('/assignments/')
      ) {
        return jsonResponse({ count: 0, next: null, previous: null, results: [] })
      }
      if (url.includes('/memberships/')) {
        return jsonResponse({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'membership-ws-ada',
              role: 'resident',
              user,
            },
          ],
        })
      }
      return sessionResponse([membership('Ada House', 'ws-ada', 'resident')])
    })
    vi.stubGlobal('fetch', fetchMock)
    renderHome()
    expect(await screen.findByRole('heading', { name: 'Your workspace' })).toBeInTheDocument()
    expect(screen.queryByText('Harbour House')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Open navigation' }))
    fireEvent.click(await screen.findByRole('link', { name: 'Your stay' }))
    expect(await screen.findByText(/No stay is recorded for you yet/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add resident' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Properties' })).not.toBeInTheDocument()
  })
})
