import { Alert, Button, Typography } from 'antd'
import { useEffect, useState } from 'react'
import {
  downloadReport,
  loadArrearsReport,
  loadCollectionsReport,
  loadMaintenanceReport,
  loadOccupancyReport,
  type ArrearsReport,
  type CollectionsReport,
  type MaintenanceReport,
  type OccupancyReport,
} from './api/reports'
import { errorText } from './api/session'
import { formatMoney } from './money'

function today(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function moneyReports(role: string): boolean {
  return role === 'owner' || role === 'finance' || role === 'property_manager'
}

export function ReportsScreen({
  workspaceId,
  role,
}: {
  workspaceId: string
  role: string
}) {
  const showMoney = moneyReports(role)
  const staff = showMoney || role === 'maintenance'
  const [on, setOn] = useState(today)
  const [from, setFrom] = useState(today)
  const [to, setTo] = useState(today)
  const [phase, setPhase] = useState<'loading' | 'ready' | 'error'>('loading')
  const [message, setMessage] = useState<string | null>(null)
  const [occupancy, setOccupancy] = useState<OccupancyReport | null>(null)
  const [arrears, setArrears] = useState<ArrearsReport | null>(null)
  const [collections, setCollections] = useState<CollectionsReport | null>(null)
  const [maintenance, setMaintenance] = useState<MaintenanceReport | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!staff) {
      return
    }
    const controller = new AbortController()
    setPhase('loading')
    setMessage(null)
    const occupancyPromise = loadOccupancyReport(workspaceId, on, controller.signal)
    const maintenancePromise = loadMaintenanceReport(workspaceId, controller.signal)
    const arrearsPromise = showMoney
      ? loadArrearsReport(workspaceId, on, controller.signal)
      : Promise.resolve(null)
    const collectionsPromise = showMoney
      ? loadCollectionsReport(workspaceId, from, to, controller.signal)
      : Promise.resolve(null)
    Promise.all([occupancyPromise, maintenancePromise, arrearsPromise, collectionsPromise])
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
  }, [workspaceId, staff, showMoney, on, from, to, attempt])

  if (!staff) {
    return (
      <section id="reports">
        <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
          Reports
        </Typography.Title>
        <Typography.Paragraph>
          Reports stay with the staff who run this workspace. Your invoices are in billing.
        </Typography.Paragraph>
      </section>
    )
  }

  async function exportCsv(path: string, filename: string) {
    try {
      await downloadReport(workspaceId, path, filename)
    } catch (error: unknown) {
      setMessage(errorText(error))
      setPhase('error')
    }
  }

  return (
    <section id="reports">
      <Typography.Title level={3} style={{ fontSize: '1.15rem' }}>
        Reports
      </Typography.Title>
      <Typography.Paragraph>
        Totals are for this workspace only. Amounts use the currency&apos;s normal decimal places.
        Stored amounts keep four decimal places.
      </Typography.Paragraph>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
        <label>
          On
          <input
            id="report-on"
            type="date"
            value={on}
            onChange={(event) => setOn(event.target.value)}
            style={{ display: 'block' }}
          />
        </label>
        {showMoney ? (
          <>
            <label>
              Collections from
              <input
                id="report-from"
                type="date"
                value={from}
                onChange={(event) => setFrom(event.target.value)}
                style={{ display: 'block' }}
              />
            </label>
            <label>
              Collections to
              <input
                id="report-to"
                type="date"
                value={to}
                onChange={(event) => setTo(event.target.value)}
                style={{ display: 'block' }}
              />
            </label>
          </>
        ) : null}
      </div>
      {phase === 'loading' ? <Typography.Paragraph>Loading reports…</Typography.Paragraph> : null}
      {phase === 'error' ? (
        <Alert
          type="error"
          showIcon
          title="Reports could not be loaded"
          description={message}
          action={
            <Button size="small" onClick={() => setAttempt((value) => value + 1)}>
              Try again
            </Button>
          }
        />
      ) : null}
      {phase === 'ready' && occupancy ? (
        <div>
          <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
            Occupancy on {occupancy.on}
          </Typography.Title>
          <Typography.Paragraph>
            Rooms occupied {occupancy.spaces.room.occupied ?? 0}, free{' '}
            {occupancy.spaces.room.free ?? 0}, partly occupied{' '}
            {occupancy.spaces.room.partly_occupied ?? 0}, unavailable{' '}
            {occupancy.spaces.room.unavailable ?? 0}. Units occupied{' '}
            {occupancy.spaces.unit.occupied ?? 0}, free {occupancy.spaces.unit.free ?? 0}. Beds
            occupied {occupancy.beds.occupied ?? 0}, free {occupancy.beds.free ?? 0}. Active
            agreements {occupancy.active_tenancies}. Active residents {occupancy.active_residents}.
          </Typography.Paragraph>
          {occupancy.properties.length === 0 ? (
            <Typography.Paragraph>No properties are recorded.</Typography.Paragraph>
          ) : (
            <ul style={{ paddingInlineStart: 18 }}>
              {occupancy.properties.map((property) => (
                <li key={property.property_id}>
                  {property.property_name}: occupied {property.occupied}, free {property.free},
                  unavailable {property.unavailable}.
                </li>
              ))}
            </ul>
          )}
          <Typography.Paragraph>
            Upcoming move-outs in {occupancy.within_days} days: {occupancy.upcoming_count}.
            {occupancy.upcoming_truncated ? ' The list shows the first 100.' : ''}
          </Typography.Paragraph>
          <ul style={{ paddingInlineStart: 18 }}>
            {occupancy.upcoming_move_outs.map((row) => (
              <li key={`${row.kind}-${row.resident_name}-${row.end_date}`}>
                {row.resident_name} · {row.label} · {row.end_date}
              </li>
            ))}
          </ul>
          <Button
            className="no-print"
            onClick={() => {
              void exportCsv(
                `/api/v1/reports/occupancy/?on=${encodeURIComponent(on)}&export=csv`,
                'occupancy.csv',
              )
            }}
          >
            Download occupancy CSV
          </Button>
        </div>
      ) : null}
      {phase === 'ready' && arrears ? (
        <div>
          <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
            Arrears on {arrears.on}
          </Typography.Title>
          <Typography.Paragraph>
            {arrears.invoice_count} invoices,{' '}
            {formatMoney(arrears.outstanding_amount, arrears.currency_code)} outstanding.
          </Typography.Paragraph>
          {arrears.residents.length === 0 ? (
            <Typography.Paragraph>No one is in arrears on this date.</Typography.Paragraph>
          ) : (
            <ul style={{ paddingInlineStart: 18 }}>
              {arrears.residents.map((row) => (
                <li key={row.resident_id}>
                  {row.resident_name}: {row.invoice_count} invoices,{' '}
                  {formatMoney(row.outstanding_amount, arrears.currency_code)}.
                </li>
              ))}
            </ul>
          )}
          <Button
            className="no-print"
            onClick={() => {
              void exportCsv(
                `/api/v1/reports/arrears/?on=${encodeURIComponent(on)}&export=csv`,
                'arrears.csv',
              )
            }}
          >
            Download arrears CSV
          </Button>
        </div>
      ) : null}
      {phase === 'ready' && collections ? (
        <div>
          <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
            Collections {collections.from} to {collections.to}
          </Typography.Title>
          <Typography.Paragraph>
            Collected {formatMoney(collections.collected_amount, collections.currency_code)} from{' '}
            {collections.payment_count} payments. Refunded{' '}
            {formatMoney(collections.refunded_amount, collections.currency_code)}. Net{' '}
            {formatMoney(collections.net_amount, collections.currency_code)}. Net is collected
            minus refunds in this range. It is not an editable balance.
          </Typography.Paragraph>
          <Button
            className="no-print"
            onClick={() => {
              void exportCsv(
                `/api/v1/reports/collections/?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&export=csv`,
                'collections.csv',
              )
            }}
          >
            Download collections CSV
          </Button>
        </div>
      ) : null}
      {phase === 'ready' && maintenance ? (
        <div>
          <Typography.Title level={4} style={{ fontSize: '1.05rem' }}>
            Open maintenance
          </Typography.Title>
          <Typography.Paragraph>
            {maintenance.scope === 'assigned'
              ? 'These counts are only the requests you can see, not the whole workspace.'
              : 'These counts cover every request in this workspace.'}{' '}
            Open work {maintenance.open_count}. Open {maintenance.counts.open ?? 0}, assigned{' '}
            {maintenance.counts.assigned ?? 0}, in progress {maintenance.counts.in_progress ?? 0},
            completed {maintenance.counts.completed ?? 0}, cancelled{' '}
            {maintenance.counts.cancelled ?? 0}.
          </Typography.Paragraph>
          <Button
            className="no-print"
            onClick={() => {
              void exportCsv('/api/v1/reports/maintenance/?export=csv', 'maintenance.csv')
            }}
          >
            Download maintenance CSV
          </Button>
        </div>
      ) : null}
    </section>
  )
}
