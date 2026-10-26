import type { ThemeConfig } from 'antd'

export const theme: ThemeConfig = {
  token: {
    colorPrimary: '#0f766e',
    colorInfo: '#0f766e',
    colorSuccess: '#3d7a4a',
    colorWarning: '#b86e2a',
    colorError: '#b42318',
    colorText: '#1c2430',
    colorTextSecondary: '#5c6b7a',
    colorBgLayout: '#f3f5f7',
    colorBorder: '#e4e9ee',
    borderRadius: 10,
    fontFamily: "system-ui, 'Segoe UI', sans-serif",
    fontSize: 15,
    controlHeight: 40,
  },
  components: {
    Layout: {
      siderBg: '#10242b',
      headerBg: '#ffffff',
      bodyBg: '#f3f5f7',
      headerHeight: 64,
    },
    Menu: {
      darkItemBg: '#10242b',
      darkSubMenuItemBg: '#10242b',
      darkItemSelectedBg: '#1c4f4c',
      darkItemHoverBg: '#17383a',
      darkItemColor: '#d5e4e2',
      darkItemSelectedColor: '#ffffff',
    },
    Card: {
      borderRadiusLG: 14,
    },
    Table: {
      headerBg: '#f7f9fa',
      headerColor: '#3d4d5c',
    },
  },
}
