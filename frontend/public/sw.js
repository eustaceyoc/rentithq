/* Rent It HQ shell cache. Bump the name when a release must drop old files.
   Never cache /api/ or /admin. Navigations stay on the network. */
const SHELL = 'rentithq-shell-v1'

function shouldCache(request) {
  if (request.method !== 'GET') {
    return false
  }
  const url = new URL(request.url)
  if (url.origin !== self.location.origin) {
    return false
  }
  const path = url.pathname
  if (path.startsWith('/api/') || path.startsWith('/admin')) {
    return false
  }
  return (
    path.startsWith('/assets/') ||
    path.startsWith('/icons/') ||
    path === '/manifest.webmanifest' ||
    path === '/favicon.svg'
  )
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => cache.addAll(['/manifest.webmanifest', '/favicon.svg'])),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== SHELL).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request))
    return
  }
  if (!shouldCache(request)) {
    return
  }
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone()
          caches.open(SHELL).then((cache) => cache.put(request, copy))
        }
        return response
      })
      .catch(() => caches.match(request)),
  )
})

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'clear-caches') {
    event.waitUntil(
      caches.keys().then((keys) => Promise.all(keys.map((key) => caches.delete(key)))),
    )
  }
})
