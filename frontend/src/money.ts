const ZERO_DECIMAL = new Set([
  'BIF',
  'CLP',
  'DJF',
  'GNF',
  'ISK',
  'JPY',
  'KMF',
  'KRW',
  'PYG',
  'RWF',
  'UGX',
  'VND',
  'VUV',
  'XAF',
  'XOF',
  'XPF',
])

const THREE_DECIMAL = new Set(['BHD', 'IQD', 'JOD', 'KWD', 'LYD', 'OMR', 'TND'])

export function minorUnits(currency: string): number {
  const code = currency.trim().toUpperCase()
  if (ZERO_DECIMAL.has(code)) {
    return 0
  }
  if (THREE_DECIMAL.has(code)) {
    return 3
  }
  return 2
}

function roundStored(amount: string, places: number): string {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(amount.trim())
  if (match === null) {
    return amount.trim()
  }
  const negative = match[1] === '-'
  const whole = match[2] ?? '0'
  const fraction = (match[3] ?? '').padEnd(4, '0').slice(0, 4)
  let minor = BigInt(whole) * 10000n + BigInt(fraction || '0')
  const drop = 4 - places
  if (drop > 0) {
    const factor = 10n ** BigInt(drop)
    const remainder = minor % factor
    minor /= factor
    if (remainder >= factor / 2n) {
      minor += 1n
    }
  }
  const scale = 10n ** BigInt(places)
  const shownWhole = minor / scale
  const shownFraction = (minor % scale).toString().padStart(places, '0')
  const body = places === 0 ? shownWhole.toString() : `${shownWhole}.${shownFraction}`
  return `${negative ? '-' : ''}${body}`
}

export function formatMoney(amount: string, currency: string): string {
  const code = currency.trim().toUpperCase()
  return `${roundStored(amount, minorUnits(code))} ${code}`
}
