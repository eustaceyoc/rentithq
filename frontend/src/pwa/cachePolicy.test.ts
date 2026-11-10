import { describe, expect, it } from 'vitest'
import { shouldCacheRequest } from './cachePolicy'

describe('installed web cache', () => {
  it('does not keep private API or admin responses', () => {
    expect(shouldCacheRequest('GET', '/api/v1/invoices/')).toBe(false)
    expect(shouldCacheRequest('GET', '/api/v1/auth/session/')).toBe(false)
    expect(shouldCacheRequest('GET', '/admin/')).toBe(false)
    expect(shouldCacheRequest('POST', '/assets/app.js')).toBe(false)
  })

  it('may keep hashed static files and the public icon', () => {
    expect(shouldCacheRequest('GET', '/assets/index-abc.js')).toBe(true)
    expect(shouldCacheRequest('GET', '/icons/icon-192.png')).toBe(true)
    expect(shouldCacheRequest('GET', '/manifest.webmanifest')).toBe(true)
  })
})
