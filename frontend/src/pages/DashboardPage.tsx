import { Alert, Empty, Table, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { PageHeader } from '../ui/PageHeader'
import {
  loadArrearsReport,
  loadCollectionsReport,
  loadMaintenanceReport,
  loadOccupancyReport,
  type ArrearsReport,
  type CollectionsReport,
  type MaintenanceReport,
  type OccupancyReport,
} from '../api/reports'
import { errorText } from '../api/session'
import { Link } from 'react-router-dom'
import { listBookings, type BookingRecord } from '../api/occupancy'
import { listPayments, type PaymentRecord } from '../api/billing'
import { formatDate, formatMoney } from '../money'

function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function monthStart(day: string): string {
  return `${day.slice(0, 8)}01`
}

function canSeeMoney(role: string): boolean {
  return role === 'owner' || role === 'finance' || role === 'property_manager'
}

function countOf(map: Record<string, number> | undefined, key: string): number {
  return map?.[key] ?? 0
}

export function DashboardPage({
  workspaceId,
  role,
  currency,
}: {
  workspaceId: string
  role: string
  currency: string
}) {
  const money = canSeeMoney(role)
  const staff = money || role === 'maintenance'
  const [occupancy, setOccupancy] = useState<OccupancyReport | null>(null)
  const [maintenance, setMaintenance] = useState<MaintenanceReport | null>(null)
  const [arrears, setArrears] = useState<ArrearsReport | null>(null)
  const [collections, setCollections] = useState<CollectionsReport | null>(null)
  const [payments, setPayments] = useState<PaymentRecord[]>([])
  const [bookings, setBookings] = useState<BookingRecord[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>(staff ? 'loading' : 'ready')

  useEffect(() => {
    if (!staff) {
      return
    }
    const controller = new AbortController()
    const on = today()
    Promise.all([
      loadOccupancyReport(workspaceId, on, controller.signal),
      loadMaintenanceReport(workspaceId, controller.signal),
      money ? loadArrearsReport(workspaceId, on, controller.signal) : Promise.resolve(null),
      money
        ? loadCollectionsReport(workspaceId, monthStart(on), on, controller.signal)
        : Promise.resolve(null),
    ])
      .then(([occupancyRow, maintenanceRow, arrearsRow, collectionsRow]) => {
        if (controller.signal.aborted) {
          return
        }
        setOccupancy(occupancyRow)
        setMaintenance(maintenanceRow)
        setArrears(arrearsRow)
        setCollections(collectionsRow)
        setPhase('ready')
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return
        }
        setPhase('error')
        setMessage(errorText(error))
      })
    return () => {
      controller.abort()
    }
  }, [money, staff, workspaceId])

  useEffect(() => {
    if (!staff) {
      return
    }
    const controller = new AbortController()
    const bookingLoad = listBookings(workspaceId, controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) {
          setBookings(
            rows
              .slice()
              .sort((left, right) => right.start_date.localeCompare(left.start_date))
              .slice(0, 5),
          )
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setBookings([])
        }
      })
    const paymentLoad = money
      ? listPayments(workspaceId, controller.signal)
          .then((rows) => {
            if (!controller.signal.aborted) {
              setPayments(
                rows
                  .slice()
                  .sort((left, right) => right.paid_on.localeCompare(left.paid_on))
                  .slice(0, 5),
              )
            }
          })
          .catch(() => {
            if (!controller.signal.aborted) {
              setPayments([])
            }
          })
      : Promise.resolve()
    void Promise.all([bookingLoad, paymentLoad])
    return () => {
      controller.abort()
    }
  }, [money, staff, workspaceId])

  if (!staff) {
    return (
      <PageHeader
        title="Dashboard"
        description="Your stay, invoices, and maintenance requests are in the menu. Workspace reports stay with the staff who run this place."
      />
    )
  }

  const unitsOccupied = countOf(occupancy?.spaces.unit, 'occupied')
  const unitsFree = countOf(occupancy?.spaces.unit, 'free')
  const roomsOccupied = countOf(occupancy?.spaces.room, 'occupied')
  const roomsFree = countOf(occupancy?.spaces.room, 'free')
  const bedsOccupied = countOf(occupancy?.beds, 'occupied')
  const bedsFree = countOf(occupancy?.beds, 'free')
  const moveOuts = occupancy?.upcoming_move_outs ?? []
  const urgent = countOf(maintenance?.by_priority, 'urgent') + countOf(maintenance?.by_priority, 'high')

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Occupancy today, money still due, collections this month, and work that is still open."
      />
      {phase === 'loading' ? <Typography.Paragraph>Loading the workspace summary…</Typography.Paragraph> : null}
      {phase === 'error' ? (
        <Alert type="error" showIcon title="The summary could not be loaded" description={message} />
      ) : null}
      {phase === 'ready' && occupancy && maintenance ? (
        <>
          <div className="ledger-strip" aria-label="Workspace summary">
            {money && arrears ? (
              <div className="ledger-lead">
                <span>Outstanding</span>
                <strong className="money">{formatMoney(arrears.outstanding_amount, currency)}</strong>
                <span>{arrears.invoice_count} invoices due today or earlier</span>
              </div>
            ) : null}
            {money && collections ? (
              <div className="ledger-lead">
                <span>Collected this month</span>
                <strong className="money">{formatMoney(collections.collected_amount, currency)}</strong>
                <span>
                  {collections.payment_count} payments · net {formatMoney(collections.net_amount, currency)}
                </span>
              </div>
            ) : null}
            <div>
              <span>Rooms occupied</span>
              <strong>{roomsOccupied}</strong>
              <span>{roomsFree} free</span>
            </div>
            <div>
              <span>Units occupied</span>
              <strong>{unitsOccupied}</strong>
              <span>
                {unitsFree} free · {bedsOccupied} beds taken, {bedsFree} free
              </span>
            </div>
            <div>
              <span>Open maintenance</span>
              <strong>{maintenance.open_count}</strong>
              <span>{urgent > 0 ? `${urgent} high or urgent` : 'None marked high or urgent'}</span>
            </div>
          </div>
          <div className="desk-grid">
            <section className="desk-panel">
              <h2>Properties</h2>
              <Table
                className="data-table"
                size="middle"
                pagination={false}
                rowKey="property_id"
                dataSource={occupancy.properties}
                locale={{ emptyText: <Empty description="No properties yet." /> }}
                columns={[
                  { title: 'Property', dataIndex: 'property_name' },
                  { title: 'Occupied', dataIndex: 'occupied', align: 'right' },
                  { title: 'Free', dataIndex: 'free', align: 'right' },
                ]}
                scroll={{ x: 'max-content' }}
              />
            </section>
            <section className="desk-panel">
              <h2>Move-outs in the next {occupancy.within_days} days</h2>
              <Table
                className="data-table"
                size="middle"
                pagination={false}
                rowKey={(row) => `${row.kind}-${row.resident_name}-${row.end_date}`}
                dataSource={moveOuts.slice(0, 8)}
                locale={{
                  emptyText: <Empty description="No upcoming move-outs in the next 30 days." />,
                }}
                columns={[
                  { title: 'Resident', dataIndex: 'resident_name' },
                  { title: 'Place', dataIndex: 'label' },
                  {
                    title: 'Last day',
                    dataIndex: 'end_date',
                    render: (value: string) => formatDate(value),
                  },
                ]}
                scroll={{ x: 'max-content' }}
              />
              {occupancy.upcoming_truncated ? (
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 8 }}>
                  The list shows the first 100.
                </Typography.Paragraph>
              ) : null}
            </section>
          </div>
          <div className="desk-grid" style={{ marginTop: 16 }}>
            <section className="desk-panel">
              <h2>Recent bookings</h2>
              <Table
                className="data-table"
                size="middle"
                pagination={false}
                rowKey="id"
                dataSource={bookings}
                locale={{ emptyText: <Empty description="No bookings yet." /> }}
                columns={[
                  { title: 'Resident', dataIndex: 'resident_name' },
                  { title: 'Status', dataIndex: 'status', render: (value: string) => value },
                  {
                    title: 'Starts',
                    dataIndex: 'start_date',
                    render: (value: string) => formatDate(value),
                  },
                ]}
              />
              <p style={{ margin: '8px 0 0' }}>
                <Link to="/app/bookings?section=bookings">All bookings</Link>
              </p>
            </section>
            {money ? (
              <section className="desk-panel">
                <h2>Recent payments</h2>
                <Table
                  className="data-table"
                  size="middle"
                  pagination={false}
                  rowKey="id"
                  dataSource={payments}
                  locale={{ emptyText: <Empty description="No payments yet." /> }}
                  columns={[
                    { title: 'Receipt', dataIndex: 'reference' },
                    {
                      title: 'Amount',
                      align: 'right',
                      render: (_value, payment) => (
                        <span className="money">{formatMoney(payment.amount, payment.currency_code)}</span>
                      ),
                    },
                    {
                      title: 'Paid',
                      dataIndex: 'paid_on',
                      render: (value: string) => formatDate(value),
                    },
                  ]}
                />
                <p style={{ margin: '8px 0 0' }}>
                  <Link to="/app/billing?section=payments">All payments</Link>
                </p>
              </section>
            ) : null}
          </div>
          {money && collections && collections.by_method.length > 0 ? (
            <section className="desk-panel" style={{ marginTop: 16 }}>
              <h2>Collections by method</h2>
              <ul className="method-bars">
                {collections.by_method.map((row) => {
                  const max = Math.max(
                    ...collections.by_method.map((item) => Number(item.amount) || 0),
                    1,
                  )
                  const width = Math.max(8, Math.round((Number(row.amount) / max) * 100))
                  return (
                    <li key={row.method}>
                      <span>
                        {row.method.replaceAll('_', ' ')} · {row.count}
                        <span className="method-track" aria-hidden="true">
                          <i style={{ width: `${width}%` }} />
                        </span>
                      </span>
                      <span className="money">{formatMoney(row.amount, currency)}</span>
                    </li>
                  )
                })}
              </ul>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
