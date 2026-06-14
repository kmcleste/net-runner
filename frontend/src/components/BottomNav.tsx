type Tab = 'topology' | 'alerts' | 'chaos'

interface Props {
  active: Tab
  onChange: (tab: Tab) => void
  alertCount: number
}

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: 'topology', icon: '🗺', label: 'Map' },
  { id: 'alerts', icon: '🔔', label: 'Alerts' },
  { id: 'chaos', icon: '⚡', label: 'Chaos' },
]

export function BottomNav({ active, onChange, alertCount }: Props) {
  return (
    <nav style={{
      display: 'flex',
      background: '#1f2937',
      borderTop: '1px solid #374151',
      flexShrink: 0,
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      {TABS.map(tab => {
        const isActive = tab.id === active
        const showBadge = tab.id === 'alerts' && alertCount > 0
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
              padding: '10px 0 8px',
              background: 'none',
              border: 'none',
              borderTop: isActive ? '2px solid #3b82f6' : '2px solid transparent',
              cursor: 'pointer',
              position: 'relative',
            }}
          >
            <span style={{ fontSize: 20 }}>{tab.icon}</span>
            <span style={{
              fontSize: 10,
              fontWeight: isActive ? 700 : 400,
              color: isActive ? '#f9fafb' : '#6b7280',
              fontFamily: 'Courier New, monospace',
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            }}>
              {tab.label}
            </span>
            {showBadge && (
              <span style={{
                position: 'absolute',
                top: 6,
                right: '50%',
                marginRight: -20,
                background: '#ef4444',
                color: '#fff',
                fontSize: 9,
                fontWeight: 700,
                borderRadius: 8,
                padding: '1px 5px',
                minWidth: 16,
                textAlign: 'center',
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
