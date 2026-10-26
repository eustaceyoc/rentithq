import { Typography } from 'antd'
import { lazy, Suspense, type ReactNode } from 'react'
import { Route, Routes } from 'react-router-dom'
import { DashboardPage } from './DashboardPage'

const PropertiesScreen = lazy(() =>
  import('../PropertiesScreen').then((module) => ({ default: module.PropertiesScreen })),
)
const OccupancyScreen = lazy(() =>
  import('../OccupancyScreen').then((module) => ({ default: module.OccupancyScreen })),
)
const BillingScreen = lazy(() =>
  import('../BillingScreen').then((module) => ({ default: module.BillingScreen })),
)
const MaintenanceScreen = lazy(() =>
  import('../MaintenanceScreen').then((module) => ({ default: module.MaintenanceScreen })),
)
const ReportsScreen = lazy(() =>
  import('../ReportsScreen').then((module) => ({ default: module.ReportsScreen })),
)

export function WorkspaceRoutes({
  workspaceId,
  role,
  currency,
  available,
  settings,
}: {
  workspaceId: string
  role: string
  currency: string
  available: boolean
  settings: ReactNode
}) {
  if (!available) {
    return (
      <Typography.Paragraph>
        This workspace is not available until a platform operator restores it.
      </Typography.Paragraph>
    )
  }
  return (
    <Suspense fallback={<Typography.Paragraph>Loading…</Typography.Paragraph>}>
      <Routes>
        <Route
          index
          element={<DashboardPage workspaceId={workspaceId} role={role} currency={currency} />}
        />
        <Route path="properties" element={<PropertiesScreen workspaceId={workspaceId} role={role} />} />
        <Route
          path="residents"
          element={
            <OccupancyScreen
              workspaceId={workspaceId}
              role={role}
              initialSection="residents"
              showSections={false}
            />
          }
        />
        <Route
          path="bookings"
          element={
            <OccupancyScreen
              workspaceId={workspaceId}
              role={role}
              initialSection="bookings"
              heading="Bookings and tenancies"
            />
          }
        />
        <Route path="billing" element={<BillingScreen workspaceId={workspaceId} role={role} />} />
        <Route
          path="maintenance"
          element={<MaintenanceScreen workspaceId={workspaceId} role={role} />}
        />
        <Route path="reports" element={<ReportsScreen workspaceId={workspaceId} role={role} />} />
        <Route path="settings" element={settings} />
      </Routes>
    </Suspense>
  )
}
