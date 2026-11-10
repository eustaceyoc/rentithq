import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BillingScreen } from './BillingScreen'
import { resetApiState } from './api/session'

afterEach(() => {
  resetApiState()
  vi.unstubAllGlobals()
})

function page(results: unknown[]) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ count: results.length, next: null, previous: null, results }),
  }
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
  lines: [],
  total_amount: '80.0000',
  allocated_amount: '0.0000',
  outstanding_amount: '80.0000',
  void_reason: null,
}

describe('Paystack checkout', () => {
  it('tells the resident the charge is confirmed only after Paystack notifies us', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url.includes('/auth/csrf/')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ csrfToken: 'csrf-test' }),
          })
        }
        if (url.includes('/paystack/initialize/')) {
          expect(init?.method).toBe('POST')
          return Promise.resolve({
            ok: true,
            status: 201,
            json: async () => ({
              authorization_url: 'https://checkout.paystack.test/ok',
              reference: 'psk_test',
              status: 'pending',
            }),
          })
        }
        if (url.includes('/invoices/')) {
          return Promise.resolve(page([invoice]))
        }
        return Promise.resolve(page([]))
      }),
    )
    render(<BillingScreen workspaceId="ws-ada" role="resident" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Pay INV-0001 with Paystack' }))
    expect(
      await screen.findByText(/recorded only after Paystack notifies Rent It HQ/),
    ).toBeInTheDocument()
    expect(screen.getByText(/https:\/\/checkout.paystack.test\/ok/)).toBeInTheDocument()
  })
})
