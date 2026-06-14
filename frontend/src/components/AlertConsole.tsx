import { Alert } from '../types'

const SEVERITY_COLOR: Record<string, { bg: string; text: string; border: string }> = {
  critical: { bg: '#450a0a', text: '#fca5a5', border: '#ef4444' },
  high:     { bg: '#431407', text: '#fed7aa', border: '#f97316' },
  medium:   { bg: '#422006', text: '#fde68a', border: '#f59e0b' },
  low:      { bg: '#0f172a', text: '#93c5fd', border: '#3b82f6' },
}

const EVENT_ICON: Record<string, string> = {
  failure: '💥',
  cascade: '🌊',
  manual_injection: '⚡',
  recovery: '✅',
  reboot: '🔄',
  maintenance: '🔧',
}

interface Props {
  alerts: Alert[]
  onDeviceClick: (deviceId: string) => void
}

export function AlertConsole({ alerts, onDeviceClick }: Props) {
  return (
    <div style={{
      width: 300,
      minWidth: 300,
      background: '#0f172a',
      borderLeft: '1px solid #1e293b',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#f9fafb', letterSpacing: 1, textTransform: 'uppercase' }}>
          Alert Console
        </span>
        <span style={{
          background: '#1e293b',
          border: '1px solid #374151',
          borderRadius: 10,
          padding: '1px 7px',
          fontSize: 10,
          color: '#9ca3af',
        }}>
          {alerts.length}
        </span>
      </div>

      {/* Alert feed */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 6 }}>
        {alerts.length === 0 && (
          <div style={{
            textAlign: 'center',
            color: '#4b5563',
            fontSize: 11,
            marginTop: 24,
          }}>
            No alerts yet.<br />Simulation is starting up.
          </div>
        )}
        {alerts.map(alert => {
          const colors = SEVERITY_COLOR[alert.severity] ?? SEVERITY_COLOR.low
          const icon = EVENT_ICON[alert.event_type] ?? '•'
          const ts = new Date(alert.sim_time)
          const timeStr = isNaN(ts.getTime()) ? '' : ts.toLocaleTimeString()

          return (
            <div
              key={alert.id}
              onClick={() => onDeviceClick(alert.device_id)}
              style={{
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                borderRadius: 5,
                padding: '6px 8px',
                marginBottom: 5,
                cursor: 'pointer',
                transition: 'opacity 0.1s',
              }}
              onMouseEnter={e => (e.currentTarget.style.opacity = '0.8')}
              onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
            >
              {/* Row 1: severity badge + hostname */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 3 }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{
                    fontSize: 9,
                    fontWeight: 700,
                    color: colors.border,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}>
                    {icon} {alert.severity}
                  </span>
                  {alert.is_manual && (
                    <span style={{
                      fontSize: 8,
                      background: '#7c3aed',
                      color: '#e9d5ff',
                      borderRadius: 3,
                      padding: '1px 4px',
                    }}>
                      MANUAL
                    </span>
                  )}
                  {alert.cascade_from_device_id && (
                    <span style={{
                      fontSize: 8,
                      background: '#164e63',
                      color: '#67e8f9',
                      borderRadius: 3,
                      padding: '1px 4px',
                    }}>
                      CASCADE
                    </span>
                  )}
                </div>
                <span style={{ fontSize: 9, color: '#6b7280' }}>{timeStr}</span>
              </div>

              {/* Row 2: hostname + vendor */}
              <div style={{ fontSize: 11, color: colors.text, fontWeight: 600, marginBottom: 2 }}>
                {alert.hostname}
                <span style={{ fontWeight: 400, color: '#9ca3af', marginLeft: 6, fontSize: 10 }}>
                  {alert.vendor}
                </span>
              </div>

              {/* Row 3: site */}
              <div style={{ fontSize: 9, color: '#6b7280', marginBottom: 3 }}>{alert.site_name}</div>

              {/* Row 4: message */}
              <div style={{
                fontSize: 10,
                color: '#d1d5db',
                lineHeight: 1.4,
                wordBreak: 'break-word',
              }}>
                {alert.failure_mode_id && (
                  <span style={{ color: colors.text, marginRight: 4 }}>
                    [{alert.failure_mode_id}]
                  </span>
                )}
                {alert.new_state && (
                  <span style={{ color: '#9ca3af' }}>
                    → {alert.new_state}
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
