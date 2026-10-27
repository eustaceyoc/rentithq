import { Tag } from 'antd'

const TONE: Record<string, string> = {
  active: 'success',
  confirmed: 'processing',
  issued: 'processing',
  recorded: 'processing',
  paid: 'success',
  completed: 'success',
  open: 'warning',
  assigned: 'processing',
  in_progress: 'processing',
  high: 'warning',
  urgent: 'error',
  low: 'default',
  normal: 'default',
  cancelled: 'default',
  void: 'default',
  voided: 'default',
}

export function StatusTag({ value }: { value: string }) {
  const tone = TONE[value] ?? 'default'
  return <Tag color={tone === 'default' ? undefined : tone}>{value.replaceAll('_', ' ')}</Tag>
}
