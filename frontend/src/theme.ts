import type { ThemeConfig } from 'antd'

export const theme: ThemeConfig = {
  token: {
    colorPrimary: '#1b1612',
    colorInfo: '#8f4328',
    colorLink: '#8f4328',
    colorSuccess: '#216846',
    colorWarning: '#9a6412',
    colorError: '#9e342e',
    colorText: '#1b1612',
    colorTextSecondary: '#53463c',
    colorBgLayout: '#f4ebdd',
    colorBgContainer: '#fff9f1',
    colorBgElevated: '#fff9f1',
    colorBorder: '#d5c4ae',
    colorPrimaryHover: '#3a312a',
    colorPrimaryActive: '#1b1612',
    controlOutline: 'rgba(143, 67, 40, 0.35)',
    controlOutlineWidth: 3,
    borderRadius: 6,
    fontFamily: "'Atkinson Hyperlegible', system-ui, sans-serif",
    fontSize: 15,
    controlHeight: 40,
  },
  components: {
    Layout: {
      siderBg: '#1b1612',
      headerBg: '#fff9f1',
      bodyBg: '#f4ebdd',
      headerHeight: 64,
    },
    Menu: {
      darkItemBg: '#1b1612',
      darkSubMenuItemBg: '#1b1612',
      darkItemSelectedBg: '#3a2e26',
      darkItemHoverBg: '#2a2420',
      darkItemColor: '#e7d7c4',
      darkItemSelectedColor: '#f8e7c4',
    },
    Card: {
      borderRadiusLG: 8,
    },
    Button: {
      primaryShadow: 'none',
      defaultShadow: 'none',
      dangerShadow: 'none',
    },
    Table: {
      headerBg: '#f4ebdd',
      headerColor: '#53463c',
      rowHoverBg: '#f4ebdd',
      headerSplitColor: '#d5c4ae',
    },
  },
}
