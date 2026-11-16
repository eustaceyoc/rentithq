const TONE: Record<string, string> = {
  active: 'neutral',
  confirmed: 'info',
  issued: 'info',
  recorded: 'info',
  paid: 'good',
  overdue: 'bad',
  partial: 'warn',
  outstanding: 'info',
  completed: 'good',
  open: 'warn',
  assigned: 'info',
  in_progress: 'info',
  high: 'warn',
  urgent: 'bad',
  low: 'neutral',
  normal: 'neutral',
  cancelled: 'neutral',
  unavailable: 'warn',
  inactive: 'neutral',
  void: 'neutral',
  voided: 'neutral',
}

const MONEY_LABEL: Record<string, string> = {
  paid: 'Paid',
  partial: 'Partially paid',
  overdue: 'Overdue',
  outstanding: 'Outstanding',
  void: 'Void',
}

export function StatusTag({ value }: { value: string }) {
  const tone = TONE[value] ?? 'neutral'
  const label = value.replaceAll('_', ' ')
  return (
    <span className={`status-tag status-${tone}`}>
      <i aria-hidden="true" />
      {label}
    </span>
  )
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
  const label = MONEY_LABEL[state] ?? state
  const tone = TONE[state] ?? 'neutral'
  return (
    <span className={`status-tag status-${tone}`}>
      <i aria-hidden="true" />
      {label}
    </span>
  )
}
