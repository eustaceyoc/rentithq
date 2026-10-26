import { Alert, Button, Checkbox, Form, Input, Select, Typography } from 'antd'
import { useEffect, useState } from 'react'
import {
  allocatePayment,
  createInvoice,
  listArrears,
  listInvoices,
  listPayments,
  recordPayment,
  refundPayment,
  reverseAllocation,
  voidInvoice,
  voidPayment,
  type InvoiceRecord,
  type PaymentRecord,
} from './api/billing'
import { listResidents, listTenancies, type ResidentRecord, type TenancyRecord } from './api/occupancy'
import { errorText } from './api/session'
import { useCatalogRevision } from './catalog'
import { formatMoney } from './money'

const SECTIONS = [
  { id: 'invoices', label: 'Invoices' },
  { id: 'payments', label: 'Payments' },
  { id: 'arrears', label: 'Arrears' },
] as const

type SectionId = (typeof SECTIONS)[number]['id']

const METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'bank_transfer', label: 'Bank transfer' },
  { value: 'mobile_money', label: 'Mobile money' },
  { value: 'card', label: 'Card' },
  { value: 'other', label: 'Other' },
]

const METHOD_LABELS: Record<string, string> = Object.fromEntries(
  METHODS.map((method) => [method.value, method.label]),
)

type DraftLine = {
  description: string
  quantity: string
  unit_amount: string
}

type InvoiceValues = {
  resident_id: string
  issued_on: string
  due_on: string
  from_tenancy?: boolean
  tenancy_id?: string
  include_deposit?: boolean
  lines?: DraftLine[]
}

type PaymentValues = {
  resident_id: string
  amount: string
  paid_on: string
  method: string
  external_reference?: string
}

type AllocateValues = {
  invoice_id: string
  amount: string
}

type ReasonValues = {
  reason: string
  on: string
}

type RefundValues = {
  amount: string
  refunded_on: string
  reason: string
}

function canWrite(role: string): boolean {
  return role === 'owner' || role === 'finance'
}

function money(amount: string, currency: string): string {
  return formatMoney(amount, currency)
}

function methodLabel(method: string): string {
  return METHOD_LABELS[method] ?? method
}

function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function useBillingLists(workspaceId: string, loadDirectories: boolean, enabled: boolean) {
  const [invoices, setInvoices] = useState<InvoiceRecord[] | null>(null)
  const [payments, setPayments] = useState<PaymentRecord[] | null>(null)
  const [residents, setResidents] = useState<ResidentRecord[] | null>(null)
  const [tenancies, setTenancies] = useState<TenancyRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const catalogRevision = useCatalogRevision()

  useEffect(() => {
    if (!enabled) {
      return
    }
    const controller = new AbortController()
    const directories = loadDirectories
      ? Promise.all([
          listResidents(workspaceId, controller.signal),
          listTenancies(workspaceId, controller.signal),
        ])
      : Promise.resolve([[] as ResidentRecord[], [] as TenancyRecord[]] as const)
    Promise.all([
      listInvoices(workspaceId, controller.signal),
      listPayments(workspaceId, controller.signal),
      directories,
    ])
      .then(([nextInvoices, nextPayments, [nextResidents, nextTenancies]]) => {
        if (!controller.signal.aborted) {
          setInvoices(nextInvoices)
          setPayments(nextPayments)
          setResidents(nextResidents)
          setTenancies(nextTenancies)
          setMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage(errorText(error))
        }
      })
    return () => {
      controller.abort()
    }
  }, [workspaceId, loadDirectories, reloadKey, enabled, catalogRevision])

  async function refreshDirectories() {
    if (!loadDirectories) {
      return
    }
    try {
      const [nextResidents, nextTenancies] = await Promise.all([
        listResidents(workspaceId),
        listTenancies(workspaceId),
      ])
      setResidents(nextResidents)
      setTenancies(nextTenancies)
    } catch (error: unknown) {
      setMessage(errorText(error))
    }
  }

  return {
    invoices,
    payments,
    residents,
    tenancies,
    message,
    refreshDirectories,
    reload: () => {
      setMessage(null)
      setInvoices(null)
      setPayments(null)
      setReloadKey((key) => key + 1)
    },
  }
}

function ReceiptBody({ payment }: { payment: PaymentRecord }) {
  return (
    <div>
      <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
        Receipt {payment.reference}
      </Typography.Title>
      <Typography.Paragraph>
        {payment.resident_name}. Paid {payment.paid_on}. {methodLabel(payment.method)}.
        Amount {money(payment.amount, payment.currency_code)}. Status {payment.status}.
      </Typography.Paragraph>
      {payment.external_reference ? (
        <Typography.Paragraph>External reference {payment.external_reference}.</Typography.Paragraph>
      ) : null}
      {payment.provider ? (
        <Typography.Paragraph>
          Provider {payment.provider}. Reference {payment.provider_reference}. Status{' '}
          {payment.provider_status ?? 'not reported'}.
        </Typography.Paragraph>
      ) : null}
      <Typography.Paragraph>
        Allocated {money(payment.allocated_amount, payment.currency_code)}. Refunded{' '}
        {money(payment.refunded_amount, payment.currency_code)}. Unallocated{' '}
        {money(payment.unallocated_amount, payment.currency_code)}.
      </Typography.Paragraph>
      {payment.allocations.map((allocation) => (
        <Typography.Paragraph key={allocation.id}>
          {allocation.invoice_reference}: {money(allocation.amount, payment.currency_code)}
          {allocation.reversed ? ' · reversed' : ''}
        </Typography.Paragraph>
      ))}
      {payment.refunds.map((refund) => (
        <Typography.Paragraph key={refund.id}>
          Refund {money(refund.amount, payment.currency_code)} on {refund.refunded_on}.{' '}
          {refund.reason}.
        </Typography.Paragraph>
      ))}
      {payment.recorded_by_email ? (
        <Typography.Paragraph>Recorded by {payment.recorded_by_email}.</Typography.Paragraph>
      ) : null}
    </div>
  )
}

function ReasonForm({
  submitLabel,
  reasonLabel,
  dateLabel,
  onSubmit,
}: {
  submitLabel: string
  reasonLabel: string
  dateLabel: string
  onSubmit: (values: ReasonValues) => Promise<void>
}) {
  return (
    <Form<ReasonValues>
      layout="vertical"
      requiredMark={false}
      onFinish={onSubmit}
      style={{ marginTop: 8 }}
    >
      <Form.Item
        label={reasonLabel}
        name="reason"
        rules={[{ required: true, message: 'Enter a reason.' }]}
      >
        <Input />
      </Form.Item>
      <Form.Item
        label={dateLabel}
        name="on"
        rules={[{ required: true, message: 'Choose a date.' }]}
      >
        <Input type="date" />
      </Form.Item>
      <Button htmlType="submit">{submitLabel}</Button>
    </Form>
  )
}

function InvoiceList({
  invoices,
  write,
  workspaceId,
  onChanged,
  onError,
}: {
  invoices: InvoiceRecord[]
  write: boolean
  workspaceId: string
  onChanged: () => void
  onError: (message: string) => void
}) {
  const [printId, setPrintId] = useState<string | null>(null)
  const [printToken, setPrintToken] = useState(0)

  useEffect(() => {
    if (printToken === 0) {
      return
    }
    window.print()
  }, [printToken])

  if (invoices.length === 0) {
    return (
      <Typography.Paragraph>
        No invoices yet. Issue one when a resident owes a charge.
      </Typography.Paragraph>
    )
  }
  return (
    <>
      {invoices.map((invoice) => (
        <article
          key={invoice.id}
          className={printId === invoice.id ? 'billing-print' : undefined}
          style={{ marginBottom: 16 }}
        >
          <Typography.Paragraph>
            {invoice.reference} · {invoice.resident_name} · {invoice.status}. Issued{' '}
            {invoice.issued_on}, due {invoice.due_on}. Total{' '}
            {money(invoice.total_amount, invoice.currency_code)}. Outstanding{' '}
            {money(invoice.outstanding_amount, invoice.currency_code)}.
          </Typography.Paragraph>
          {invoice.lines.map((line, index) => (
            <Typography.Paragraph key={`${invoice.id}-${index}`}>
              {line.description}: {line.quantity} × {money(line.unit_amount, invoice.currency_code)}{' '}
              = {money(line.line_total, invoice.currency_code)}
            </Typography.Paragraph>
          ))}
          {invoice.void_reason ? (
            <Typography.Paragraph>Void reason: {invoice.void_reason}.</Typography.Paragraph>
          ) : null}
          <Button
            className="no-print"
            onClick={() => {
              setPrintId(invoice.id)
              setPrintToken((token) => token + 1)
            }}
          >
            Print invoice {invoice.reference}
          </Button>
          {write && invoice.status === 'issued' ? (
            <ReasonForm
              submitLabel={`Void ${invoice.reference}`}
              reasonLabel={`Void reason for ${invoice.reference}`}
              dateLabel={`Void date for ${invoice.reference}`}
              onSubmit={async (values) => {
                try {
                  await voidInvoice(workspaceId, invoice.id, {
                    reason: values.reason.trim(),
                    voided_on: values.on,
                  })
                  onChanged()
                } catch (error: unknown) {
                  onError(errorText(error))
                }
              }}
            />
          ) : null}
        </article>
      ))}
    </>
  )
}

function IssueInvoiceForm({
  workspaceId,
  residents,
  tenancies,
  onChanged,
  onError,
  onOpenPeople,
}: {
  workspaceId: string
  residents: ResidentRecord[]
  tenancies: TenancyRecord[]
  onChanged: () => void
  onError: (message: string) => void
  onOpenPeople: () => void
}) {
  const [form] = Form.useForm<InvoiceValues>()
  const fromTenancy = Form.useWatch('from_tenancy', form)
  const residentId = Form.useWatch('resident_id', form)
  const residentTenancies = tenancies.filter((tenancy) => tenancy.resident_id === residentId)

  return (
    <Form<InvoiceValues>
      form={form}
      layout="vertical"
      requiredMark={false}
      initialValues={{ lines: [{ description: '', quantity: '1', unit_amount: '' }] }}
      onFinish={async (values) => {
        try {
          if (values.from_tenancy) {
            await createInvoice(workspaceId, {
              resident_id: values.resident_id,
              issued_on: values.issued_on,
              due_on: values.due_on,
              from_tenancy: true,
              tenancy_id: values.tenancy_id,
              include_deposit: Boolean(values.include_deposit),
            })
          } else {
            const lines = (values.lines ?? []).map((line) => ({
              description: line.description.trim(),
              quantity: line.quantity.trim(),
              unit_amount: line.unit_amount.trim(),
            }))
            if (
              lines.length === 0 ||
              lines.some((line) => !line.description || !line.quantity || !line.unit_amount)
            ) {
              onError('Enter a description, quantity, and amount on every line.')
              return
            }
            await createInvoice(workspaceId, {
              resident_id: values.resident_id,
              issued_on: values.issued_on,
              due_on: values.due_on,
              lines,
            })
          }
          form.resetFields()
          onChanged()
        } catch (error: unknown) {
          onError(errorText(error))
        }
      }}
    >
      <Form.Item
        label="Resident"
        name="resident_id"
        rules={[{ required: true, message: 'Choose a resident.' }]}
      >
        <Select
          options={residents.map((resident) => ({
            value: resident.id,
            label: `${resident.first_name} ${resident.last_name}`,
          }))}
          onOpenChange={(open) => {
            if (open) {
              onOpenPeople()
            }
          }}
        />
      </Form.Item>
      <Form.Item
        label="Issued on"
        name="issued_on"
        rules={[{ required: true, message: 'Choose the issue date.' }]}
      >
        <Input type="date" />
      </Form.Item>
      <Form.Item
        label="Due on"
        name="due_on"
        rules={[{ required: true, message: 'Choose the due date.' }]}
      >
        <Input type="date" />
      </Form.Item>
      <Form.Item name="from_tenancy" valuePropName="checked">
        <Checkbox>Use the agreement fee</Checkbox>
      </Form.Item>
      {fromTenancy ? (
        <>
          <Form.Item
            label="Agreement"
            name="tenancy_id"
            rules={[{ required: true, message: 'Choose an agreement.' }]}
          >
            <Select
              options={residentTenancies.map((tenancy) => ({
                value: tenancy.id,
                label: `${tenancy.resident_name} · ${money(tenancy.fee_amount, tenancy.currency_code)} per ${tenancy.fee_period}`,
              }))}
              onOpenChange={(open) => {
                if (open) {
                  onOpenPeople()
                }
              }}
            />
          </Form.Item>
          <Form.Item name="include_deposit" valuePropName="checked">
            <Checkbox>Include the deposit</Checkbox>
          </Form.Item>
        </>
      ) : (
        <Form.List name="lines">
          {(fields, { add, remove }) => (
            <>
              {fields.map((field, index) => (
                <div key={field.key}>
                  <Form.Item
                    label={`Description ${index + 1}`}
                    name={[field.name, 'description']}
                    rules={[{ required: true, message: 'Enter a description.' }]}
                  >
                    <Input />
                  </Form.Item>
                  <Form.Item
                    label={`Quantity ${index + 1}`}
                    name={[field.name, 'quantity']}
                    rules={[{ required: true, message: 'Enter a quantity.' }]}
                  >
                    <Input inputMode="decimal" />
                  </Form.Item>
                  <Form.Item
                    label={`Unit amount ${index + 1}`}
                    name={[field.name, 'unit_amount']}
                    rules={[{ required: true, message: 'Enter an amount.' }]}
                  >
                    <Input inputMode="decimal" />
                  </Form.Item>
                  {fields.length > 1 ? (
                    <Button onClick={() => remove(field.name)}>Remove line {index + 1}</Button>
                  ) : null}
                </div>
              ))}
              <Button
                onClick={() => add({ description: '', quantity: '1', unit_amount: '' })}
                style={{ marginBottom: 12 }}
              >
                Add line
              </Button>
            </>
          )}
        </Form.List>
      )}
      <Button type="primary" htmlType="submit">
        Issue invoice
      </Button>
    </Form>
  )
}

function PaymentCards({
  payments,
  invoices,
  write,
  workspaceId,
  printId,
  onPrint,
  onChanged,
  onError,
}: {
  payments: PaymentRecord[]
  invoices: InvoiceRecord[]
  write: boolean
  workspaceId: string
  printId: string | null
  onPrint: (paymentId: string) => void
  onChanged: () => void
  onError: (message: string) => void
}) {
  if (payments.length === 0) {
    return <Typography.Paragraph>No payments yet.</Typography.Paragraph>
  }
  return (
    <>
      {payments.map((payment) => {
        const openInvoices = invoices.filter(
          (invoice) =>
            invoice.resident_id === payment.resident_id &&
            invoice.status === 'issued' &&
            invoice.outstanding_amount !== '0.0000',
        )
        return (
          <article
            key={payment.id}
            className={printId === payment.id ? 'billing-print' : undefined}
            style={{ marginBottom: 20 }}
          >
            <ReceiptBody payment={payment} />
            <Button className="no-print" onClick={() => onPrint(payment.id)}>
              Print receipt {payment.reference}
            </Button>
            {write && payment.status === 'recorded' ? (
              <div className="no-print">
                <Form<AllocateValues>
                  layout="vertical"
                  requiredMark={false}
                  style={{ marginTop: 8 }}
                  onFinish={async (values) => {
                    try {
                      await allocatePayment(workspaceId, {
                        payment_id: payment.id,
                        invoice_id: values.invoice_id,
                        amount: values.amount.trim(),
                      })
                      onChanged()
                    } catch (error: unknown) {
                      onError(errorText(error))
                    }
                  }}
                >
                  <Form.Item
                    label={`Invoice for ${payment.reference}`}
                    name="invoice_id"
                    rules={[{ required: true, message: 'Choose an invoice.' }]}
                  >
                    <Select
                      options={openInvoices.map((invoice) => ({
                        value: invoice.id,
                        label: `${invoice.reference} · outstanding ${money(invoice.outstanding_amount, invoice.currency_code)}`,
                      }))}
                    />
                  </Form.Item>
                  <Form.Item
                    label={`Amount for ${payment.reference}`}
                    name="amount"
                    rules={[{ required: true, message: 'Enter an amount.' }]}
                  >
                    <Input inputMode="decimal" />
                  </Form.Item>
                  <Button htmlType="submit">Allocate {payment.reference}</Button>
                </Form>
                {payment.allocations
                  .filter((allocation) => !allocation.reversed)
                  .map((allocation) => (
                    <ReasonForm
                      key={allocation.id}
                      submitLabel={`Reverse allocation to ${allocation.invoice_reference}`}
                      reasonLabel={`Reverse reason for ${allocation.invoice_reference}`}
                      dateLabel={`Reverse date for ${allocation.invoice_reference}`}
                      onSubmit={async (values) => {
                        try {
                          await reverseAllocation(workspaceId, allocation.id, {
                            reason: values.reason.trim(),
                            reversed_on: values.on,
                          })
                          onChanged()
                        } catch (error: unknown) {
                          onError(errorText(error))
                        }
                      }}
                    />
                  ))}
                <Form<RefundValues>
                  layout="vertical"
                  requiredMark={false}
                  style={{ marginTop: 8 }}
                  onFinish={async (values) => {
                    try {
                      await refundPayment(workspaceId, payment.id, {
                        amount: values.amount.trim(),
                        refunded_on: values.refunded_on,
                        reason: values.reason.trim(),
                      })
                      onChanged()
                    } catch (error: unknown) {
                      onError(errorText(error))
                    }
                  }}
                >
                  <Form.Item
                    label={`Refund amount for ${payment.reference}`}
                    name="amount"
                    rules={[{ required: true, message: 'Enter an amount.' }]}
                  >
                    <Input inputMode="decimal" />
                  </Form.Item>
                  <Form.Item
                    label={`Refund date for ${payment.reference}`}
                    name="refunded_on"
                    rules={[{ required: true, message: 'Choose a date.' }]}
                  >
                    <Input type="date" />
                  </Form.Item>
                  <Form.Item
                    label={`Refund reason for ${payment.reference}`}
                    name="reason"
                    rules={[{ required: true, message: 'Enter a reason.' }]}
                  >
                    <Input />
                  </Form.Item>
                  <Button htmlType="submit">Refund {payment.reference}</Button>
                </Form>
                <ReasonForm
                  submitLabel={`Void ${payment.reference}`}
                  reasonLabel={`Void reason for ${payment.reference}`}
                  dateLabel={`Void date for ${payment.reference}`}
                  onSubmit={async (values) => {
                    try {
                      await voidPayment(workspaceId, payment.id, {
                        reason: values.reason.trim(),
                        voided_on: values.on,
                      })
                      onChanged()
                    } catch (error: unknown) {
                      onError(errorText(error))
                    }
                  }}
                />
              </div>
            ) : null}
          </article>
        )
      })}
    </>
  )
}

function RecordPaymentForm({
  workspaceId,
  residents,
  onChanged,
  onError,
  onOpenPeople,
}: {
  workspaceId: string
  residents: ResidentRecord[]
  onChanged: () => void
  onError: (message: string) => void
  onOpenPeople: () => void
}) {
  const [form] = Form.useForm<PaymentValues>()
  return (
    <Form<PaymentValues>
      form={form}
      layout="vertical"
      requiredMark={false}
      onFinish={async (values) => {
        const external = values.external_reference?.trim() ?? ''
        try {
          await recordPayment(workspaceId, {
            resident_id: values.resident_id,
            amount: values.amount.trim(),
            paid_on: values.paid_on,
            method: values.method,
            ...(external ? { external_reference: external } : {}),
          })
          form.resetFields()
          onChanged()
        } catch (error: unknown) {
          onError(errorText(error))
        }
      }}
    >
      <Form.Item
        label="Resident"
        name="resident_id"
        rules={[{ required: true, message: 'Choose a resident.' }]}
      >
        <Select
          options={residents.map((resident) => ({
            value: resident.id,
            label: `${resident.first_name} ${resident.last_name}`,
          }))}
          onOpenChange={(open) => {
            if (open) {
              onOpenPeople()
            }
          }}
        />
      </Form.Item>
      <Form.Item
        label="Amount"
        name="amount"
        rules={[{ required: true, message: 'Enter an amount.' }]}
      >
        <Input inputMode="decimal" />
      </Form.Item>
      <Form.Item
        label="Paid on"
        name="paid_on"
        rules={[{ required: true, message: 'Choose the payment date.' }]}
      >
        <Input type="date" />
      </Form.Item>
      <Form.Item
        label="Method"
        name="method"
        rules={[{ required: true, message: 'Choose a method.' }]}
      >
        <Select options={METHODS} />
      </Form.Item>
      <Form.Item label="External reference" name="external_reference">
        <Input />
      </Form.Item>
      <Button type="primary" htmlType="submit">
        Record payment
      </Button>
    </Form>
  )
}

function ArrearsList({ workspaceId }: { workspaceId: string }) {
  const [on, setOn] = useState(today)
  const [rows, setRows] = useState<InvoiceRecord[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!on) {
      return
    }
    const controller = new AbortController()
    listArrears(workspaceId, on, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) {
          setRows(next)
          setMessage(null)
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setMessage(errorText(error))
        }
      })
    return () => {
      controller.abort()
    }
  }, [workspaceId, on])

  return (
    <section>
      <Typography.Paragraph>
        Issued invoices that are due on or before this date and still have an outstanding amount.
      </Typography.Paragraph>
      <div style={{ marginBottom: 16 }}>
        <label htmlFor="arrears-on" style={{ display: 'block', marginBottom: 8 }}>
          Arrears date
        </label>
        <Input
          id="arrears-on"
          type="date"
          value={on}
          onChange={(event) => {
            setRows(null)
            setMessage(null)
            setOn(event.target.value)
          }}
        />
      </div>
      {message ? (
        <Alert type="error" showIcon title="Arrears could not be loaded" description={message} />
      ) : null}
      {rows === null && !message ? (
        <Typography.Paragraph>Loading arrears…</Typography.Paragraph>
      ) : null}
      {rows && rows.length === 0 ? (
        <Typography.Paragraph>No one is in arrears on this date.</Typography.Paragraph>
      ) : null}
      {rows?.map((invoice) => (
        <Typography.Paragraph key={invoice.id}>
          {invoice.reference} · {invoice.resident_name} · due {invoice.due_on} · outstanding{' '}
          {money(invoice.outstanding_amount, invoice.currency_code)}
        </Typography.Paragraph>
      ))}
    </section>
  )
}

function ResidentBilling({ workspaceId }: { workspaceId: string }) {
  const { invoices, payments, message } = useBillingLists(workspaceId, false, true)
  const [printId, setPrintId] = useState<string | null>(null)
  const [printToken, setPrintToken] = useState(0)

  useEffect(() => {
    if (printToken === 0) {
      return
    }
    window.print()
  }, [printToken])

  return (
    <section>
      <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
        Your invoices
      </Typography.Title>
      <Typography.Paragraph>
        You can see your own invoices, payments, and receipts.
      </Typography.Paragraph>
      {message ? (
        <Alert
          type="error"
          showIcon
          title="Your invoices could not be loaded"
          description={message}
        />
      ) : null}
      {invoices === null && !message ? (
        <Typography.Paragraph>Loading your invoices…</Typography.Paragraph>
      ) : null}
      {invoices && invoices.length === 0 ? (
        <Typography.Paragraph>No invoices are recorded for you yet.</Typography.Paragraph>
      ) : null}
      {invoices?.map((invoice) => (
        <article
          key={invoice.id}
          className={printId === `invoice:${invoice.id}` ? 'billing-print' : undefined}
          style={{ marginBottom: 12 }}
        >
          <Typography.Paragraph>
            {invoice.reference} · {invoice.status}. Due {invoice.due_on}. Outstanding{' '}
            {money(invoice.outstanding_amount, invoice.currency_code)}.
          </Typography.Paragraph>
          <Button
            className="no-print"
            onClick={() => {
              setPrintId(`invoice:${invoice.id}`)
              setPrintToken((token) => token + 1)
            }}
          >
            Print invoice {invoice.reference}
          </Button>
        </article>
      ))}
      <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
        Your payments
      </Typography.Title>
      {payments && payments.length === 0 ? (
        <Typography.Paragraph>No payments are recorded for you yet.</Typography.Paragraph>
      ) : null}
      {payments?.map((payment) => (
        <article
          key={payment.id}
          className={printId === `payment:${payment.id}` ? 'billing-print' : undefined}
          style={{ marginBottom: 16 }}
        >
          <ReceiptBody payment={payment} />
          <Button
            className="no-print"
            onClick={() => {
              setPrintId(`payment:${payment.id}`)
              setPrintToken((token) => token + 1)
            }}
          >
            Print receipt {payment.reference}
          </Button>
        </article>
      ))}
    </section>
  )
}

export function BillingScreen({
  workspaceId,
  role,
}: {
  workspaceId: string
  role: string
}) {
  const [section, setSection] = useState<SectionId>('invoices')
  const [actionError, setActionError] = useState<string | null>(null)
  const [printId, setPrintId] = useState<string | null>(null)
  const [printToken, setPrintToken] = useState(0)
  const write = canWrite(role)
  const lists = useBillingLists(
    workspaceId,
    write,
    role !== 'maintenance' && role !== 'resident',
  )

  useEffect(() => {
    if (printToken === 0) {
      return
    }
    window.print()
  }, [printToken])

  if (role === 'maintenance') {
    return (
      <section>
        <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
          Invoices and payments
        </Typography.Title>
        <Alert
          type="warning"
          showIcon
          title="Maintenance cannot view invoices or payments."
          description="Money records stay with the owner and finance."
        />
      </section>
    )
  }

  if (role === 'resident') {
    return <ResidentBilling workspaceId={workspaceId} />
  }

  return (
    <section>
      <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
        Invoices and payments
      </Typography.Title>
      <Typography.Paragraph>
        Outstanding amounts come from invoice lines and allocations. Recording a payment does not
        charge a card or a mobile-money account.
      </Typography.Paragraph>
      {role === 'property_manager' ? (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          title="You can view invoices and payments."
          description="Recording money stays with the owner and finance."
        />
      ) : null}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        {SECTIONS.map((item) => (
          <Button
            key={item.id}
            type={section === item.id ? 'primary' : 'default'}
            onClick={() => {
              setSection(item.id)
              setActionError(null)
            }}
          >
            {item.label}
          </Button>
        ))}
      </div>
      {lists.message ? (
        <>
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
            title="Invoices could not be loaded"
            description={lists.message}
          />
          <Button onClick={lists.reload} style={{ marginBottom: 16 }}>
            Try again
          </Button>
        </>
      ) : null}
      {actionError ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          title="That did not work"
          description={actionError}
        />
      ) : null}
      {lists.invoices === null && !lists.message ? (
        <Typography.Paragraph>Loading invoices…</Typography.Paragraph>
      ) : null}
      {section === 'invoices' && lists.invoices ? (
        <>
          <InvoiceList
            invoices={lists.invoices}
            write={write}
            workspaceId={workspaceId}
            onChanged={() => {
              setActionError(null)
              lists.reload()
            }}
            onError={setActionError}
          />
          {write ? (
            <IssueInvoiceForm
              workspaceId={workspaceId}
              residents={lists.residents ?? []}
              tenancies={lists.tenancies ?? []}
              onChanged={() => {
                setActionError(null)
                lists.reload()
              }}
              onError={setActionError}
              onOpenPeople={() => {
                void lists.refreshDirectories()
              }}
            />
          ) : null}
        </>
      ) : null}
      {section === 'payments' && lists.payments && lists.invoices ? (
        <>
          <PaymentCards
            payments={lists.payments}
            invoices={lists.invoices}
            write={write}
            workspaceId={workspaceId}
            printId={printId}
            onPrint={(paymentId) => {
              setPrintId(paymentId)
              setPrintToken((token) => token + 1)
            }}
            onChanged={() => {
              setActionError(null)
              lists.reload()
            }}
            onError={setActionError}
          />
          {write ? (
            <RecordPaymentForm
              workspaceId={workspaceId}
              residents={lists.residents ?? []}
              onChanged={() => {
                setActionError(null)
                lists.reload()
              }}
              onError={setActionError}
              onOpenPeople={() => {
                void lists.refreshDirectories()
              }}
            />
          ) : null}
        </>
      ) : null}
      {section === 'arrears' ? <ArrearsList workspaceId={workspaceId} /> : null}
    </section>
  )
}
