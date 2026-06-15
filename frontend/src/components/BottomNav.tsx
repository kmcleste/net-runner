import { c, font, tint } from '../theme'

type Tab = 'topology' | 'geo' | 'alerts' | 'chaos'

interface Props {
  active: Tab
  onChange: (tab: Tab) => void
  alertCount: number
}

const TABS: { id: Tab; glyph: string; label: string }[] = [
  { id: 'topology', glyph: '◈', label: 'Topo' },
  { id: 'geo',      glyph: '◎', label: 'Geo' },
  { id: 'alerts',   glyph: '◉', label: 'Alerts' },
  { id: 'chaos',    glyph: '⚡', label: 'Chaos' },
]

export function BottomNav({ active, onChange, alertCount }: Props) {
  return (
    <nav style={{
      display: 'flex',
      background: c.panel,
      borderTop: `1px solid ${c.line}`,
      flexShrink: 0,
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      {TABS.map(tab => {
        const isActive = tab.id === active
        const showBadge = tab.id === 'alerts' && alertCount > 0
        const tone = tab.id === 'chaos' ? c.crit : tab.id === 'geo' ? '#9b7dff' : c.accent
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 3,
              padding: '10px 0 9px',
              background: isActive ? tint(tone, 0.08) : 'transparent',
              border: 'none',
              borderTop: `2px solid ${isActive ? tone : 'transparent'}`,
              cursor: 'pointer',
              position: 'relative',
            }}
          >
            <span style={{
              fontSize: 18,
              color: isActive ? tone : c.faint,
              textShadow: isActive ? `0 0 10px ${tint(tone, 0.7)}` : 'none',
              lineHeight: 1,
            }}>
              {tab.glyph}
            </span>
            <span style={{
              fontSize: 10,
              fontWeight: isActive ? 700 : 500,
              color: isActive ? c.text : c.faint,
              fontFamily: font.sans,
              textTransform: 'uppercase',
              letterSpacing: 0.6,
            }}>
              {tab.label}
            </span>
            {showBadge && (
              <span className="mono" style={{
                position: 'absolute',
                top: 6,
                right: '50%',
                marginRight: -22,
                background: c.crit,
                color: '#fff',
                fontSize: 9,
                fontWeight: 700,
                borderRadius: 8,
                padding: '1px 5px',
                minWidth: 16,
                textAlign: 'center',
                fontFamily: font.mono,
                boxShadow: `0 0 8px ${tint(c.crit, 0.7)}`,
              }}>
                {alertCount > 99 ? '99+' : alertCount}
              </span>
            )}
          </button>
        )
      })}
    </nav>
  )
}
