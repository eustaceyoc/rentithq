import { Tag } from 'antd'

const TONE: Record<string, string> = {
  active: 'success',
  confirmed: 'processing',
  issued: 'processing',
  recorded: 'processing',
  paid: 'success',
  overdue: 'error',
  partial: 'warning',
  outstanding: 'processing',
  completed: 'success',
  open: 'warning',
  assigned: 'processing',
  in_progress: 'processing',
  high: 'warning',
  urgent: 'error',
  low: 'default',
  normal: 'default',
  cancelled: 'default',
  unavailable: 'warning',
  inactive: 'default',
  void: 'default',
  voided: 'default',
}

export function StatusTag({ value }: { value: string }) {
  const tone = TONE[value] ?? 'default'
  return <Tag color={tone === 'default' ? undefined : tone}>{value.replaceAll('_', ' ')}</Tag>
}

const MONEY_LABEL: Record<string, string> = {
  paid: 'Paid',
  partial: 'Partially paid',
  overdue: 'Overdue',
  outstanding: 'Outstanding',
  void: 'Void',
}

function moneyState(invoice: {
  status: string
  due_on: string
  total_amount: string
  outstanding_amount: string
}): string {
  if (invoice.status === 'void') {
    return 'void'
  }
  const outstanding = Number(invoice.outstanding_amount)
  const total = Number(invoice.total_amount)
  if (!Number.isFinite(outstanding) || outstanding <= 0) {
    return 'paid'
  }
  const today = new Date()
  const day = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  if (invoice.due_on < day) {
    return 'overdue'
  }
  if (Number.isFinite(total) && outstanding < total) {
    return 'partial'
  }
  return 'outstanding'
}

export function MoneyTag({
  invoice,
}: {
  invoice: {
    status: string
    due_on: string
    total_amount: string
    outstanding_amount: string
  }
}) {
  const state = moneyState(invoice)
  const tone = TONE[state] ?? 'default'
  return <Tag color={tone === 'default' ? undefined : tone}>{MONEY_LABEL[state] ?? state}</Tag>
}
