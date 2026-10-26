import { describe, expect, it } from 'vitest'
import { formatMoney, minorUnits } from './money'

describe('formatMoney', () => {
  it('shows two decimal places for GHS and keeps the code', () => {
    expect(minorUnits('GHS')).toBe(2)
    expect(formatMoney('80.0000', 'GHS')).toBe('80.00 GHS')
    expect(formatMoney('80.0050', 'ghs')).toBe('80.01 GHS')
    expect(formatMoney('1.0040', 'GHS')).toBe('1.00 GHS')
  })

  it('uses zero places for yen and three for dinars', () => {
    expect(formatMoney('80.0000', 'JPY')).toBe('80 JPY')
    expect(formatMoney('80.5000', 'JPY')).toBe('81 JPY')
    expect(formatMoney('1.2345', 'KWD')).toBe('1.235 KWD')
  })

  it('rounds a negative amount away from zero at the halfway point', () => {
    expect(formatMoney('-1.0050', 'GHS')).toBe('-1.01 GHS')
  })
})
