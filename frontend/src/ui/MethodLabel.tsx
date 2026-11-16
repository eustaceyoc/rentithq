import {
  BankOutlined,
  CreditCardOutlined,
  DollarOutlined,
  MobileOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'

const LABELS: Record<string, string> = {
  cash: 'Cash',
  bank_transfer: 'Bank transfer',
  mobile_money: 'Mobile money',
  card: 'Card',
  other: 'Other',
}

const ICONS: Record<string, ReactNode> = {
  cash: <DollarOutlined />,
  bank_transfer: <BankOutlined />,
  mobile_money: <MobileOutlined />,
  card: <CreditCardOutlined />,
}

function methodLabel(method: string): string {
  return LABELS[method] ?? method.replaceAll('_', ' ')
}

export function MethodLabel({ method }: { method: string }) {
  return (
    <span className="method-label">
      {ICONS[method] ?? null}
      {methodLabel(method)}
    </span>
  )
}
