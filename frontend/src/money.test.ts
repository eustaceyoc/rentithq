import { describe, expect, it } from 'vitest'
import { formatMoney, minorUnits } from './money'

describe('formatMoney', () => {
  it('shows two decimal places for GHS and keeps the code', () => {
    expect(minorUnits('GHS')).toBe(2)
    expect(formatMoney('80.0000', 'GHS')).toBe('GHS 80.00')
    expect(formatMoney('80.0050', 'ghs')).toBe('GHS 80.01')
    expect(formatMoney('1.0040', 'GHS')).toBe('GHS 1.00')
    expect(formatMoney('1925.0000', 'GHS')).toBe('GHS 1,925.00')
  })

  it('uses zero places for yen and three for dinars', () => {
    expect(formatMoney('80.0000', 'JPY')).toBe('JPY 80')
    expect(formatMoney('80.5000', 'JPY')).toBe('JPY 81')
    expect(formatMoney('1.2345', 'KWD')).toBe('KWD 1.235')
  })

  it('rounds a negative amount away from zero at the halfway point', () => {
    expect(formatMoney('-1.0050', 'GHS')).toBe('-GHS 1.01')
  })
})
