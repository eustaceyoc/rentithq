import { MoreOutlined } from '@ant-design/icons'
import { Button, Dropdown } from 'antd'
import { useState, type ReactNode } from 'react'

export type ActionItem = {
  key: string
  label: string
  danger?: boolean
  onClick: () => void
}

export function ActionMenu({ label, items }: { label: string; items: ActionItem[] }) {
  const [open, setOpen] = useState(false)
  return (
    <Dropdown
      open={open}
      onOpenChange={setOpen}
      menu={{
        items: items.map((item) => ({
          key: item.key,
          danger: item.danger,
          label: item.label,
          onClick: () => {
            setOpen(false)
            item.onClick()
          },
        })),
      }}
    >
      <Button
        type="text"
        aria-label={label}
        aria-expanded={open}
        icon={<MoreOutlined />}
        onClick={() => setOpen((value) => !value)}
      />
    </Dropdown>
  )
}

export function MoneyCell({ children }: { children: ReactNode }) {
  return <span className="money">{children}</span>
}
