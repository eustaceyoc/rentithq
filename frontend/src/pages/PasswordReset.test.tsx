import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { resetApiState } from '../api/session'
import { ForgotPasswordPage, ResetPasswordPage } from './PasswordPages'
import { LoginPage } from './LoginPage'

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

describe('Password reset', () => {
  it('asks for an email from sign-in and shows the same confirmation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/auth/csrf/')) {
          return jsonResponse({ csrfToken: 'csrf-test' })
        }
        if (url.includes('/auth/session/')) {
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
        }
        if (url.includes('/auth/password/reset/')) {
          return jsonResponse({
            detail: 'If an account exists for that email, a reset link is on its way.',
          })
        }
        return jsonResponse({})
      }),
    )
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        </Routes>
      </MemoryRouter>,
    )
    fireEvent.click(await screen.findByRole('link', { name: 'Forgot password?' }))
    fireEvent.change(await screen.findByLabelText('Email'), {
      target: { value: 'ada@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }))
    expect(
      await screen.findByText(
        'If an account exists for that email, a reset link is on its way.',
      ),
    ).toBeInTheDocument()
  })

  it('submits a new password from the reset page', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/auth/csrf/')) {
          return jsonResponse({ csrfToken: 'csrf-test' })
        }
        if (url.includes('/auth/password/reset/confirm/')) {
          return jsonResponse({ detail: 'Your password has been updated.' })
        }
        return jsonResponse({})
      }),
    )
    render(
      <MemoryRouter initialEntries={['/reset-password?uid=abc&token=def']}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
        </Routes>
      </MemoryRouter>,
    )
    fireEvent.change(screen.getByLabelText('New password'), {
      target: { value: 'fresh-stable-lantern' },
    })
    fireEvent.change(screen.getByLabelText('Confirm password'), {
      target: { value: 'fresh-stable-lantern' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))
    expect(await screen.findByText('Your password has been updated.')).toBeInTheDocument()
  })
})
