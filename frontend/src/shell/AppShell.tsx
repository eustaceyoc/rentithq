import {
  DashboardOutlined,
  DollarOutlined,
  HomeOutlined,
  MenuOutlined,
  SettingOutlined,
  TeamOutlined,
  ToolOutlined,
  CalendarOutlined,
  BarChartOutlined,
  DownOutlined,
} from '@ant-design/icons'
import { Button, Drawer, Dropdown, Grid, Layout, Menu, Typography } from 'antd'
import { useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

const { Header, Sider, Content } = Layout

type NavItem = {
  to: string
  label: string
  icon: ReactNode
}

function navFor(role: string): NavItem[] {
  const resident = role === 'resident'
  const items: NavItem[] = [
    { to: '/app', label: 'Dashboard', icon: <DashboardOutlined /> },
  ]
  if (!resident) {
    items.push({ to: '/app/properties', label: 'Properties', icon: <HomeOutlined /> })
  }
  items.push({
    to: '/app/residents',
    label: resident ? 'Your stay' : 'Residents',
    icon: <TeamOutlined />,
  })
  if (!resident) {
    items.push({
      to: '/app/bookings',
      label: 'Bookings',
      icon: <CalendarOutlined />,
    })
  }
  items.push(
    { to: '/app/billing', label: 'Billing', icon: <DollarOutlined /> },
    { to: '/app/maintenance', label: 'Maintenance', icon: <ToolOutlined /> },
  )
  if (!resident) {
    items.push({ to: '/app/reports', label: 'Reports', icon: <BarChartOutlined /> })
  }
  items.push({ to: '/app/settings', label: 'Settings', icon: <SettingOutlined /> })
  return items
}

export function AppShell({
  workspaceName,
  role,
  roleName,
  email,
  onSignOut,
  onSwitch,
  children,
}: {
  workspaceName: string
  role: string
  roleName: string
  email: string
  onSignOut: () => void
  onSwitch: (() => void) | null
  children: ReactNode
}) {
  const screens = Grid.useBreakpoint()
  const isMobile = !screens.lg
  const [collapsed, setCollapsed] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()
  const items = navFor(role)
  const selected = items.some((item) => item.to === location.pathname)
    ? location.pathname
    : '/app'

  const menu = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[selected]}
      items={items.map((item) => ({
        key: item.to,
        icon: item.icon,
        label: <Link to={item.to}>{item.label}</Link>,
      }))}
      onClick={() => {
        setDrawerOpen(false)
      }}
      style={{ borderInlineEnd: 0 }}
    />
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {isMobile ? (
        <Drawer
          title="Rent It HQ"
          placement="left"
          open={drawerOpen}
          onClose={() => {
            setDrawerOpen(false)
          }}
          styles={{ body: { padding: 0, background: '#10242b' }, header: { background: '#10242b' } }}
          closeIcon={<span style={{ color: '#fff' }}>Close</span>}
        >
          {menu}
        </Drawer>
      ) : (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={240}
          theme="dark"
          style={{ position: 'sticky', top: 0, height: '100vh' }}
        >
          <div className="sider-brand" style={{ paddingInline: collapsed ? 8 : 16, justifyContent: collapsed ? 'center' : 'flex-start' }}>
            <span className="brand-mark" aria-hidden="true">
              R
            </span>
            {collapsed ? null : (
              <div style={{ minWidth: 0 }}>
                <Typography.Text style={{ color: '#fff', display: 'block', fontWeight: 700, lineHeight: 1.2 }}>
                  Rent It HQ
                </Typography.Text>
                <Typography.Text style={{ color: '#9fb8b4', fontSize: 12 }} ellipsis>
                  {workspaceName}
                </Typography.Text>
              </div>
            )}
          </div>
          {menu}
        </Sider>
      )}
      <Layout>
        <Header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            paddingInline: 16,
            borderBottom: '1px solid #e4e9ee',
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
            {isMobile ? (
              <Button
                aria-label="Open navigation"
                icon={<MenuOutlined />}
                onClick={() => {
                  setDrawerOpen(true)
                }}
              />
            ) : null}
            <div style={{ minWidth: 0 }}>
              <Typography.Text strong style={{ display: 'block', lineHeight: 1.2 }}>
                {workspaceName}
              </Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {roleName}
              </Typography.Text>
            </div>
          </div>
          <Dropdown
            menu={{
              items: [
                ...(onSwitch
                  ? [
                      {
                        key: 'switch',
                        label: 'Switch workspace',
                        onClick: onSwitch,
                      },
                    ]
                  : []),
                { key: 'sign-out', label: 'Sign out', onClick: onSignOut },
              ],
            }}
          >
            <Button
              type="text"
              className="account-menu"
              aria-haspopup="menu"
              aria-label={`Account menu for ${email}`}
              icon={<DownOutlined />}
              iconPlacement="end"
            >
              <span>{email}</span>
            </Button>
          </Dropdown>
        </Header>
        <Content style={{ padding: isMobile ? 16 : 32 }}>{children}</Content>
      </Layout>
    </Layout>
  )
}
