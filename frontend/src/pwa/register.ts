import { SHELL_CACHE } from './cachePolicy'

export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) {
    return
  }
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js')
  })
}

export async function clearInstalledCaches(): Promise<void> {
  if (!('serviceWorker' in navigator)) {
    return
  }
  const registration = await navigator.serviceWorker.getRegistration()
  registration?.active?.postMessage({ type: 'clear-caches' })
  if (!('caches' in window)) {
    return
  }
  const keys = await caches.keys()
  await Promise.all(
    keys
      .filter((key) => key === SHELL_CACHE || key.startsWith('rentithq-'))
      .map((key) => caches.delete(key)),
  )
}
