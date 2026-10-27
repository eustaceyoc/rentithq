import { Alert, Card, Empty, Table, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { PageHeader } from '../ui/PageHeader'
import {
  loadArrearsReport,
  loadCollectionsReport,
  loadMaintenanceReport,
  loadOccupancyReport,
  type MaintenanceReport,
  type OccupancyReport,
} from '../api/reports'
import { errorText } from '../api/session'
import { formatMoney } from '../money'

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
  const [openWork, setOpenWork] = useState<number | null>(null)
  const [outstanding, setOutstanding] = useState<string | null>(null)
  const [collected, setCollected] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>(staff ? 'loading' : 'ready')

  useEffect(() => {
    if (!staff) {
      return
    }
    const controller = new AbortController()
    const on = today()
    const occupancyPromise = loadOccupancyReport(workspaceId, on, controller.signal)
    const maintenancePromise = loadMaintenanceReport(workspaceId, controller.signal)
    const arrearsPromise = money
      ? loadArrearsReport(workspaceId, on, controller.signal)
      : Promise.resolve(null)
    const collectionsPromise = money
      ? loadCollectionsReport(workspaceId, monthStart(on), on, controller.signal)
      : Promise.resolve(null)
    Promise.all([occupancyPromise, maintenancePromise, arrearsPromise, collectionsPromise])
      .then(([occupancyRow, maintenanceRow, arrearsRow, collectionsRow]) => {
        if (controller.signal.aborted) {
          return
        }
        setOccupancy(occupancyRow)
        setOpenWork((maintenanceRow as MaintenanceReport).open_count)
        setOutstanding(arrearsRow?.outstanding_amount ?? null)
        setCollected(collectionsRow?.collected_amount ?? null)
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

  if (!staff) {
    return (
      <PageHeader
        title="Your workspace"
        description="Your stay, invoices, and maintenance requests are in the menu. Workspace reports stay with the staff who run this place."
      />
    )
  }

  const roomsOccupied = occupancy?.spaces.room.occupied ?? 0
  const roomsFree = occupancy?.spaces.room.free ?? 0
  const moveOuts = occupancy?.upcoming_move_outs ?? []

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Today’s occupancy, money still due, collections this month, and open maintenance."
      />
      {phase === 'loading' ? <Typography.Paragraph>Loading the workspace summary…</Typography.Paragraph> : null}
      {phase === 'error' ? (
        <Alert type="error" showIcon title="The summary could not be loaded" description={message} />
      ) : null}
      {phase === 'ready' ? (
        <>
          <div className="kpi-grid">
            <article className="kpi kpi-lead">
              <span className="kpi-label">Rooms occupied</span>
              <p className="kpi-value">{roomsOccupied}</p>
              <span className="kpi-note">{roomsFree} free</span>
            </article>
            {money ? (
              <article className="kpi">
                <span className="kpi-label">Outstanding</span>
                <p className="kpi-value">{formatMoney(outstanding ?? '0.0000', currency)}</p>
                <span className="kpi-note">Due today or earlier</span>
              </article>
            ) : null}
            {money ? (
              <article className="kpi">
                <span className="kpi-label">Collected this month</span>
                <p className="kpi-value">{formatMoney(collected ?? '0.0000', currency)}</p>
                <span className="kpi-note">Recorded payments</span>
              </article>
            ) : null}
            <article className="kpi">
              <span className="kpi-label">Open maintenance</span>
              <p className="kpi-value">{openWork ?? 0}</p>
              <span className="kpi-note">Not completed or cancelled</span>
            </article>
          </div>
          <Card style={{ marginTop: 16 }} title="Upcoming move-outs">
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
                { title: 'Last day', dataIndex: 'end_date' },
              ]}
              scroll={{ x: 'max-content' }}
            />
            {occupancy?.upcoming_truncated ? (
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 8 }}>
                The list shows the first 100.
              </Typography.Paragraph>
            ) : null}
          </Card>
        </>
      ) : null}
    </div>
  )
}
