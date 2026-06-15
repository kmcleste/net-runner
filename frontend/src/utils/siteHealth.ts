import { Device } from '../types'
import { c } from '../theme'

export interface SiteStats {
  total: number
  healthy: number
  impaired: number
  failed: number
}

export function siteStats(deviceIds: string[], devices: Record<string, Device>): SiteStats {
  let total = 0, healthy = 0, failed = 0
  for (const id of deviceIds) {
    const d = devices[id]
    if (!d) continue
    total++
    if (d.state === 'healthy') healthy++
    else if (d.state === 'failed' || d.state === 'unreachable') failed++
  }
  return { total, healthy, impaired: total - healthy, failed }
}

export function healthColor(s: SiteStats): string {
  if (s.total === 0) return c.down
  const pct = s.healthy / s.total
  if (pct >= 0.98) return c.ok
  if (pct >= 0.85) return c.warn
  return c.crit
}
