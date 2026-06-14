// Design tokens for net-runner — "Console" direction.
// A NOC read like a wall of rack gear: deep ops-room ink, signal-LED status
// colors, fiber-cyan accent, and the IBM Plex superfamily for type.

export const c = {
  ink: '#0a0e15',          // page background (darkened ops room)
  panel: '#0f1520',        // panel surface
  raised: '#151d2a',       // raised surface / inputs
  line: '#202b3b',         // hairline borders
  lineSoft: '#18212e',     // quieter divider

  text: '#e7edf4',         // primary text
  dim: '#8b98ab',          // secondary text
  faint: '#586577',        // tertiary / captions

  // Status — gear front-panel LEDs
  ok: '#34d39e',           // link/healthy (teal-green)
  warn: '#f5b73e',         // degraded (amber)
  crit: '#ff5d61',         // failed (red)
  down: '#5b687c',         // unreachable (dark, dimmed)
  recover: '#a98bff',      // recovering (violet)
  reboot: '#48a9f0',       // rebooting (blue)
  maint: '#6b7a90',        // maintenance (slate)

  accent: '#3fd0dd',       // fiber-cyan — interaction / selection
  human: '#9b7dff',        // human/manual actions
} as const

export const font = {
  sans: "'IBM Plex Sans', system-ui, -apple-system, sans-serif",
  mono: "'IBM Plex Mono', ui-monospace, 'SFMono-Regular', Menlo, monospace",
} as const

export const radius = { sm: 4, md: 7, lg: 11, pill: 999 } as const

export const stateColor: Record<string, string> = {
  healthy: c.ok,
  degraded: c.warn,
  failed: c.crit,
  unreachable: c.down,
  recovering: c.recover,
  rebooting: c.reboot,
  maintenance: c.maint,
}

export const sevColor: Record<string, string> = {
  critical: c.crit,
  high: '#ff8b42',
  medium: c.warn,
  low: c.accent,
}

// translucent fill from a hex color (for badge backgrounds)
export const tint = (hex: string, alpha = 0.14): string => {
  const a = Math.round(alpha * 255).toString(16).padStart(2, '0')
  return `${hex}${a}`
}
