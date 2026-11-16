import {
  BarChartOutlined,
  CalendarOutlined,
  DashboardOutlined,
  DollarOutlined,
  DownOutlined,
  HomeOutlined,
  MenuOutlined,
  SettingOutlined,
  TeamOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import { Button, Drawer, Dropdown, Grid, Layout, Menu, Typography } from 'antd'
import { useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

const { Header, Sider, Content } = Layout

type Leaf = {
  key: string
  label: string
  icon: ReactNode
}

type Group = {
  label: string
  children: Leaf[]
}

function seesMoney(role: string): boolean {
  return role === 'owner' || role === 'finance' || role === 'property_manager'
}

function groupsFor(role: string): Group[] {
  if (role === 'resident') {
    return [
      {
        label: 'Overview',
        children: [{ key: '/app', label: 'Dashboard', icon: <DashboardOutlined /> }],
      },
      {
        label: 'Your place',
        children: [
          { key: '/app/residents', label: 'Your stay', icon: <TeamOutlined /> },
          {
            key: '/app/billing',
            label: 'Invoices and payments',
            icon: <DollarOutlined />,
          },
          { key: '/app/maintenance', label: 'Maintenance', icon: <ToolOutlined /> },
        ],
      },
      {
        label: 'Workspace',
        children: [{ key: '/app/settings', label: 'Settings', icon: <SettingOutlined /> }],
      },
    ]
  }

  const property: Leaf[] = [
    { key: '/app/properties', label: 'Properties', icon: <HomeOutlined /> },
    { key: '/app/properties#rooms', label: 'Rooms and beds', icon: <HomeOutlined /> },
    { key: '/app/residents', label: 'Residents', icon: <TeamOutlined /> },
    {
      key: '/app/bookings?section=bookings',
      label: 'Bookings',
      icon: <CalendarOutlined />,
    },
    {
      key: '/app/bookings?section=tenancies',
      label: 'Tenancies',
      icon: <CalendarOutlined />,
    },
  ]
  const financial: Leaf[] = [
    { key: '/app/billing?section=invoices', label: 'Invoices', icon: <DollarOutlined /> },
    { key: '/app/billing?section=payments', label: 'Payments', icon: <DollarOutlined /> },
    { key: '/app/billing?section=arrears', label: 'Arrears', icon: <DollarOutlined /> },
  ]
  if (seesMoney(role)) {
    financial.push({
      key: '/app/reports#collections',
      label: 'Collections',
      icon: <BarChartOutlined />,
    })
  }
  const workspace: Leaf[] = []
  if (role === 'owner') {
    workspace.push({
      key: '/app/settings#team',
      label: 'Team members',
      icon: <TeamOutlined />,
    })
  }
  workspace.push({ key: '/app/settings', label: 'Settings', icon: <SettingOutlined /> })

  return [
    {
      label: 'Overview',
      children: [{ key: '/app', label: 'Dashboard', icon: <DashboardOutlined /> }],
    },
    { label: 'Property management', children: property },
    { label: 'Financial', children: financial },
    {
      label: 'Operations',
      children: [{ key: '/app/maintenance', label: 'Maintenance', icon: <ToolOutlined /> }],
    },
    {
      label: 'Reporting',
      children: [{ key: '/app/reports', label: 'Reports', icon: <BarChartOutlined /> }],
    },
    { label: 'Workspace', children: workspace },
  ]
}

function selectedKey(pathname: string, search: string, hash: string): string {
  const full = `${pathname}${search}${hash}`
  if (hash === '#rooms' && pathname === '/app/properties') {
    return '/app/properties#rooms'
  }
  if (hash === '#collections' && pathname === '/app/reports') {
    return '/app/reports#collections'
  }
  if (hash === '#team' && pathname === '/app/settings') {
    return '/app/settings#team'
  }
  if (pathname === '/app/billing') {
    const section = new URLSearchParams(search).get('section')
    if (section === 'payments' || section === 'arrears') {
      return `/app/billing?section=${section}`
    }
    return '/app/billing?section=invoices'
  }
  if (pathname === '/app/bookings') {
    const section = new URLSearchParams(search).get('section')
    if (section === 'tenancies') {
      return '/app/bookings?section=tenancies'
    }
    return '/app/bookings?section=bookings'
  }
  if (pathname === '/app' || pathname === '/app/') {
    return '/app'
  }
  return full.startsWith('/app/') ? pathname : '/app'
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
  const groups = groupsFor(role)
  const current = selectedKey(location.pathname, location.search, location.hash)

  const menu = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[current]}
      onClick={() => {
        setDrawerOpen(false)
      }}
      style={{ borderInlineEnd: 0 }}
      items={groups.map((group) => ({
        type: 'group' as const,
        label: group.label,
        children: group.children.map((item) => ({
          key: item.key,
          icon: item.icon,
          label: <Link to={item.key}>{item.label}</Link>,
        })),
      }))}
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
          styles={{ body: { padding: 0, background: '#1b1612' }, header: { background: '#1b1612', color: '#f8e7c4' } }}
          closeIcon={<span style={{ color: '#f8e7c4' }}>Close</span>}
        >
          {menu}
        </Drawer>
      ) : (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={248}
          theme="dark"
          style={{ position: 'sticky', top: 0, height: '100vh', overflow: 'auto' }}
        >
          <div
            className="sider-brand"
            style={{
              paddingInline: collapsed ? 8 : 16,
              justifyContent: collapsed ? 'center' : 'flex-start',
            }}
          >
            <span className="brand-mark" aria-hidden="true">
              R
            </span>
            {collapsed ? null : (
              <div style={{ minWidth: 0 }}>
                <Typography.Text
                  style={{ color: '#f8e7c4', display: 'block', fontWeight: 700, lineHeight: 1.2 }}
                >
                  Rent It HQ
                </Typography.Text>
                <Typography.Text style={{ color: '#c8b7a4', fontSize: 12 }} ellipsis>
                  {workspaceName}
                </Typography.Text>
              </div>
            )}
          </div>
          {menu}
        </Sider>
      )}
      <Layout>
        <Header className="app-header">
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
              <Typography.Text strong ellipsis style={{ display: 'block', lineHeight: 1.2 }}>
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
                  ? [{ key: 'switch', label: 'Switch workspace', onClick: onSwitch }]
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
        <Content className="app-content">{children}</Content>
      </Layout>
    </Layout>
  )
}
