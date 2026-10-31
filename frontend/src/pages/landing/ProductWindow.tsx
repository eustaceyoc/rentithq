import type { ReactNode } from 'react'

const NAV = ['Dashboard', 'Properties', 'Residents', 'Billing', 'Maintenance', 'Reports']

export function ProductWindow({
  workspace,
  active,
  label,
  children,
}: {
  workspace: string
  active: string
  label: string
  children: ReactNode
}) {
  return (
    <figure className="window">
      <div className="window-app" aria-hidden="true">
        <aside className="window-side">
          <strong>Rent It HQ</strong>
          <em>{workspace}</em>
          {NAV.map((item) => (
            <span key={item} className={item === active ? 'on' : undefined}>
              {item}
            </span>
          ))}
        </aside>
        <div className="window-main">{children}</div>
      </div>
      <figcaption>{label}</figcaption>
    </figure>
  )
}
