import { describe, expect, it } from 'vitest'
import { filterRows, pageOf } from './filterRows'

const rows = [
  { name: 'Ama Mensah', status: 'active' },
  { name: 'Kojo Boateng', status: 'confirmed' },
  { name: 'Efua Owusu', status: 'active' },
]

describe('filterRows', () => {
  it('searches by the visible text', () => {
    const found = filterRows(rows, 'kojo', (row) => row.name, 'all', (row) => row.status)
    expect(found.map((row) => row.name)).toEqual(['Kojo Boateng'])
  })

  it('filters by status and still searches', () => {
    const found = filterRows(rows, 'ama', (row) => row.name, 'active', (row) => row.status)
    expect(found.map((row) => row.name)).toEqual(['Ama Mensah'])
  })
})

describe('pageOf', () => {
  it('returns one page and leaves the rest', () => {
    expect(pageOf([1, 2, 3, 4, 5], 2, 2)).toEqual([3, 4])
    expect(pageOf([1, 2], 1, 8)).toEqual([1, 2])
  })
})
