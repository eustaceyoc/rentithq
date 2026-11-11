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
          expect(JSON.parse(String(init?.body))).toEqual({ invoice_id: 'inv-1', channel: 'card' })
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
    fireEvent.change(screen.getByRole('combobox', { name: 'Payment method' }), { target: { value: 'card' } })
    fireEvent.click(await screen.findByRole('button', { name: 'Pay INV-0001 with Paystack' }))
    expect(
      await screen.findByText(/recorded only after Paystack notifies Rent It HQ/),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Continue to Paystack checkout' })).toHaveAttribute(
      'href', 'https://checkout.paystack.test/ok',
    )
  })
})


it('shows a Paystack initialization failure without offering a checkout link', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/auth/csrf/')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ csrfToken: 'csrf-test' }) })
    }
    if (url.includes('/paystack/initialize/')) {
      return Promise.resolve({
        ok: false, status: 400,
        json: async () => ({ error: { code: 'paystack_error', message: 'Paystack did not accept the charge.', details: {} } }),
      })
    }
    return Promise.resolve(page(url.includes('/invoices/') ? [invoice] : []))
  }))
  render(<BillingScreen workspaceId="ws-ada" role="resident" />)
  fireEvent.click(await screen.findByRole('button', { name: 'Pay INV-0001 with Paystack' }))
  expect(await screen.findByText('Paystack did not accept the charge.')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Continue to Paystack checkout' })).not.toBeInTheDocument()
})

it('does not offer payment for an invoice with no outstanding balance', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => Promise.resolve(
    page(String(input).includes('/invoices/') ? [{ ...invoice, outstanding_amount: '0.0000' }] : []),
  )))
  render(<BillingScreen workspaceId="ws-ada" role="resident" />)
  expect(await screen.findByRole('button', { name: 'Print invoice INV-0001' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Pay INV-0001 with Paystack' })).not.toBeInTheDocument()
})


it('refreshes the balance after returning from checkout', async () => {
  let outstanding = '80.0000'
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => Promise.resolve(
    page(String(input).includes('/invoices/') ? [{ ...invoice, outstanding_amount: outstanding }] : []),
  )))
  render(<BillingScreen workspaceId="ws-ada" role="resident" />)
  expect(await screen.findByRole('button', { name: 'Pay INV-0001 with Paystack' })).toBeInTheDocument()
  outstanding = '0.0000'
  fireEvent.click(screen.getByRole('button', { name: 'Refresh invoices and payments' }))
  expect(await screen.findByRole('button', { name: 'Print invoice INV-0001' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Pay INV-0001 with Paystack' })).not.toBeInTheDocument()
})
