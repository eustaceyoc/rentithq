import { Table } from 'antd'
import type { TableProps } from 'antd'

export function DataTable<T extends object>({
  className,
  pagination,
  scroll,
  ...props
}: TableProps<T>) {
  return (
    <Table<T>
      size="middle"
      pagination={pagination ?? { pageSize: 25, hideOnSinglePage: true, showSizeChanger: false }}
      scroll={scroll ?? { x: 'max-content' }}
      {...props}
      className={className ? `data-table ${className}` : 'data-table'}
    />
  )
}
