import { Alert, Card, Col, Empty, Row, Typography } from 'antd'
import { useEffect, useState } from 'react'
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
      <Card>
        <Typography.Title level={2} style={{ marginTop: 0 }}>
          Your workspace
        </Typography.Title>
        <Typography.Paragraph style={{ marginBottom: 0 }}>
          Your stay, invoices, and maintenance requests are in the menu. Workspace reports stay
          with the staff who run this place.
        </Typography.Paragraph>
      </Card>
    )
  }

  const roomsOccupied = occupancy?.spaces.room.occupied ?? 0
  const roomsFree = occupancy?.spaces.room.free ?? 0
  const moveOuts = occupancy?.upcoming_move_outs ?? []

  return (
    <div>
      <Typography.Title level={2} style={{ marginTop: 0 }}>
        Dashboard
      </Typography.Title>
      <Typography.Paragraph type="secondary">
        Today’s occupancy, money still due, collections this month, and open maintenance.
      </Typography.Paragraph>
      {phase === 'loading' ? <Typography.Paragraph>Loading the workspace summary…</Typography.Paragraph> : null}
      {phase === 'error' ? (
        <Alert type="error" showIcon title="The summary could not be loaded" description={message} />
      ) : null}
      {phase === 'ready' ? (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} xl={6}>
              <Card>
                <Typography.Text type="secondary">Rooms occupied</Typography.Text>
                <Typography.Title level={3} style={{ margin: '8px 0 0' }}>
                  {roomsOccupied}
                </Typography.Title>
                <Typography.Text type="secondary">{roomsFree} free</Typography.Text>
              </Card>
            </Col>
            {money ? (
              <Col xs={24} sm={12} xl={6}>
                <Card>
                  <Typography.Text type="secondary">Outstanding</Typography.Text>
                  <Typography.Title level={3} style={{ margin: '8px 0 0' }}>
                    {formatMoney(outstanding ?? '0.0000', currency)}
                  </Typography.Title>
                  <Typography.Text type="secondary">Due today or earlier</Typography.Text>
                </Card>
              </Col>
            ) : null}
            {money ? (
              <Col xs={24} sm={12} xl={6}>
                <Card>
                  <Typography.Text type="secondary">Collected this month</Typography.Text>
                  <Typography.Title level={3} style={{ margin: '8px 0 0' }}>
                    {formatMoney(collected ?? '0.0000', currency)}
                  </Typography.Title>
                  <Typography.Text type="secondary">Recorded payments</Typography.Text>
                </Card>
              </Col>
            ) : null}
            <Col xs={24} sm={12} xl={6}>
              <Card>
                <Typography.Text type="secondary">Open maintenance</Typography.Text>
                <Typography.Title level={3} style={{ margin: '8px 0 0' }}>
                  {openWork ?? 0}
                </Typography.Title>
                <Typography.Text type="secondary">Not completed or cancelled</Typography.Text>
              </Card>
            </Col>
          </Row>
          <Card style={{ marginTop: 16 }} title="Upcoming move-outs">
            {moveOuts.length === 0 ? (
              <Empty description="No upcoming move-outs in the next 30 days." />
            ) : (
              <ul style={{ margin: 0, paddingInlineStart: 18 }}>
                {moveOuts.slice(0, 8).map((row) => (
                  <li key={`${row.kind}-${row.resident_name}-${row.end_date}`}>
                    {row.resident_name} · {row.label} · {row.end_date}
                  </li>
                ))}
              </ul>
            )}
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
