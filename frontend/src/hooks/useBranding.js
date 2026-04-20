import { useEffect } from 'react'
import { useAuth } from '../context/AuthContext'

function lighten(hex, amount = 0.95) {
  if (!hex || hex.length < 7) return '#f5f7fa'
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgb(${Math.round(r + (255 - r) * amount)}, ${Math.round(g + (255 - g) * amount)}, ${Math.round(b + (255 - b) * amount)})`
}

function darken(hex, amount = 0.35) {
  if (!hex || hex.length < 7) return '#1a1a2e'
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgb(${Math.round(r * (1 - amount))}, ${Math.round(g * (1 - amount))}, ${Math.round(b * (1 - amount))})`
}

export function useBranding() {
  const { tenantConfig } = useAuth()

  useEffect(() => {
    if (!tenantConfig) return
    const root = document.documentElement
    const primary = tenantConfig.primary_colour || '#1E4078'

    root.style.setProperty('--brand-primary', primary)
    root.style.setProperty('--brand-accent', lighten(primary, 0.6))
    root.style.setProperty('--brand-bg', lighten(primary, 0.95))
    root.style.setProperty('--brand-text', darken(primary, 0.35))

    if (tenantConfig.favicon_url) {
      const link = document.querySelector("link[rel='icon']")
      if (link) link.href = `${import.meta.env.VITE_API_URL}${tenantConfig.favicon_url}`
    }
  }, [tenantConfig])
}
