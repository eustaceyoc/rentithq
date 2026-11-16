import { Button } from 'antd'

export function SectionSwitch<T extends string>({
  items,
  value,
  onChange,
}: {
  items: ReadonlyArray<{ id: T; label: string }>
  value: T
  onChange: (id: T) => void
}) {
  return (
    <div className="section-switch" role="tablist">
      {items.map((item) => (
        <Button
          key={item.id}
          type={value === item.id ? 'primary' : 'default'}
          aria-pressed={value === item.id}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </Button>
      ))}
    </div>
  )
}
