import { MoreOutlined } from '@ant-design/icons'
import { Button, Dropdown } from 'antd'
import type { ReactNode } from 'react'

export type ActionItem = {
  key: string
  label: string
  danger?: boolean
  onClick: () => void
}

export function ActionMenu({ label, items }: { label: string; items: ActionItem[] }) {
  return (
    <Dropdown
      menu={{
        items: items.map((item) => ({
          key: item.key,
          danger: item.danger,
          label: item.label,
          onClick: item.onClick,
        })),
      }}
    >
      <Button type="text" aria-label={label} icon={<MoreOutlined />} />
    </Dropdown>
  )
}

export function MoneyCell({ children }: { children: ReactNode }) {
  return <span className="money">{children}</span>
}
