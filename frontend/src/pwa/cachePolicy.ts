/** What the service worker is allowed to keep. Private API data is never cached. */

export const SHELL_CACHE = 'rentithq-shell-v1'

export function shouldCacheRequest(method: string, pathname: string): boolean {
  if (method !== 'GET') {
    return false
  }
  if (pathname.startsWith('/api/') || pathname.startsWith('/admin')) {
    return false
  }
  return (
    pathname.startsWith('/assets/') ||
    pathname.startsWith('/icons/') ||
    pathname === '/manifest.webmanifest' ||
    pathname === '/favicon.svg'
  )
}
