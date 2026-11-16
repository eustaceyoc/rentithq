import { Input, Select } from 'antd'

export function ListBar({
  query,
  onQuery,
  status,
  onStatus,
  statuses,
  placeholder,
}: {
  query: string
  onQuery: (value: string) => void
  status?: string
  onStatus?: (value: string) => void
  statuses?: Array<{ value: string; label: string }>
  placeholder: string
}) {
  return (
    <div className="filter-bar">
      <label className="filter-field">
        Search
        <Input
          aria-label={placeholder}
          value={query}
          allowClear
          onChange={(event) => onQuery(event.target.value)}
        />
      </label>
      {statuses && onStatus && status !== undefined ? (
        <label className="filter-field">
          Status
          <Select
            aria-label="Status"
            value={status}
            style={{ minWidth: 160 }}
            onChange={onStatus}
            options={[{ value: 'all', label: 'All statuses' }, ...statuses]}
          />
        </label>
      ) : null}
    </div>
  )
}
