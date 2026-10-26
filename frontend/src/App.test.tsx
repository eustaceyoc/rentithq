import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { resetApiState } from './api/session'

afterEach(() => {
  resetApiState()
  vi.unstubAllGlobals()
})

function jsonResponse(body: unknown, ok = true, status = 200) {
  return {
    ok,
    status,
    json: async () => body,
  }
}

function installFetch(
  health: () => { ok: boolean; status: number; json: () => Promise<unknown> } | Promise<never>,
) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/auth/csrf/')) {
        return Promise.resolve(jsonResponse({ csrfToken: 'csrf-test' }))
      }
      if (url.includes('/auth/session/')) {
        return Promise.resolve(
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
        )
      }
      return Promise.resolve(health())
    }),
  )
}

describe('API connection screen', () => {
  it('starts by checking the API', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)))
    render(<App />)
    expect(screen.getByText('Checking the API…')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Rent It HQ' }),
    ).toBeInTheDocument()
  })

  it('shows that the API is reachable', async () => {
    installFetch(() =>
      jsonResponse({ status: 'ok', service: 'rentithq-api' }),
    )
    render(<App />)
    expect(await screen.findByText('The API is reachable.')).toBeInTheDocument()
    expect(screen.getByText(/rentithq-api/)).toBeInTheDocument()
  })

  it('shows a warning when the API is not healthy', async () => {
    installFetch(() =>
      jsonResponse({ status: 'degraded', service: 'rentithq-api' }),
    )
    render(<App />)
    expect(
      await screen.findByText(
        'The API responded, but it is not reporting a healthy status.',
      ),
    ).toBeInTheDocument()
  })

  it('shows a failure when the API cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))
    render(<App />)
    expect(await screen.findByText('The API could not be reached.')).toBeInTheDocument()
  })

  it('does not show an unexpected payload as a success', async () => {
    installFetch(() => jsonResponse({ status: 1, detail: 'secret-trace' }))
    render(<App />)
    expect(await screen.findByText('The API could not be reached.')).toBeInTheDocument()
    expect(screen.queryByText(/secret-trace/)).not.toBeInTheDocument()
  })
})
