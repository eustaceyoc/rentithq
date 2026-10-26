import { useEffect, useState } from 'react'

const CATALOG_CHANGED = 'workspace-catalog-changed'

export function notifyCatalogChanged(): void {
  window.dispatchEvent(new Event(CATALOG_CHANGED))
}

export function useCatalogRevision(): number {
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const onChange = () => {
      setRevision((value) => value + 1)
    }
    window.addEventListener(CATALOG_CHANGED, onChange)
    return () => {
      window.removeEventListener(CATALOG_CHANGED, onChange)
    }
  }, [])
  return revision
}
