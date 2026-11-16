import type { ThemeConfig } from 'antd'

export const theme: ThemeConfig = {
  token: {
    colorPrimary: '#1b1612',
    colorInfo: '#b4532a',
    colorLink: '#8a3418',
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
    borderRadius: 2,
    fontFamily: "'Atkinson Hyperlegible', system-ui, sans-serif",
    fontSize: 15,
    controlHeight: 40,
  },
  components: {
    Layout: {
      siderBg: '#1b1612',
      triggerBg: '#1b1612',
      triggerColor: '#f8e7c4',
      headerBg: '#fff9f1',
      bodyBg: '#f4ebdd',
      headerHeight: 64,
      headerPadding: '0 16px',
    },
    Card: {
      borderRadiusLG: 2,
    },
    Button: {
      primaryShadow: 'none',
      defaultShadow: 'none',
      dangerShadow: 'none',
      fontWeight: 600,
    },
    Input: {
      activeBorderColor: '#1b1612',
      hoverBorderColor: '#8a3418',
    },
    Select: {
      optionSelectedBg: '#f4ebdd',
    },
    Pagination: {
      itemActiveBg: '#f4ebdd',
    },
    Modal: {
      titleFontSize: 22,
    },
    Dropdown: {
      paddingBlock: 6,
    },
    Table: {
      headerBg: '#f7f1e6',
      headerColor: '#53463c',
      rowHoverBg: '#f7f1e6',
      headerSplitColor: 'transparent',
      borderColor: '#efe6d8',
      cellPaddingBlock: 14,
      cellPaddingInline: 16,
    },
    Form: {
      itemMarginBottom: 16,
      labelColor: '#1b1612',
    },
    Tag: {
      defaultBg: '#f4ebdd',
      defaultColor: '#1b1612',
    },
    Menu: {
      darkItemBg: '#1b1612',
      darkSubMenuItemBg: '#1b1612',
      darkItemSelectedBg: '#3a2e26',
      darkItemHoverBg: '#2a2420',
      darkItemColor: '#e7d7c4',
      darkItemSelectedColor: '#f8e7c4',
      darkGroupTitleColor: '#c8b7a4',
      itemHeight: 36,
    },
  },
}
