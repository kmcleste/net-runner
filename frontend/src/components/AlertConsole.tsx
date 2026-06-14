import { Alert } from '../types'
import { c, font, radius, sevColor, tint } from '../theme'
import { Led } from './Led'

const EVENT_LABEL: Record<string, string> = {
  failure: 'FAIL',
  cascade: 'CASCADE',
  manual_injection: 'INJECT',
  recovery: 'RECOVER',
  reboot: 'REBOOT',
  maintenance: 'MAINT',
}

interface Props {
  alerts: Alert[]
  onDeviceClick: (deviceId: string) => void
}

export function AlertConsole({ alerts, onDeviceClick }: Props) {
  return (
    <div style={{
      width: 304,
      minWidth: 304,
      background: c.panel,
      borderLeft: `1px solid ${c.line}`,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '11px 14px',
        borderBottom: `1px solid ${c.line}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: c.text, letterSpacing: 1.5, textTransform: 'uppercase' }}>
          Alert Console
        </span>
        <span className="mono" style={{
          background: c.raised,
          border: `1px solid ${c.line}`,
          borderRadius: radius.pill,
          padding: '1px 9px',
          fontSize: 10,
          color: c.dim,
          fontFamily: font.mono,
        }}>
          {alerts.length}
        </span>
      </div>

      {/* Feed */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        {alerts.length === 0 && (
          <div style={{ textAlign: 'center', color: c.faint, fontSize: 11, marginTop: 28, lineHeight: 1.7 }}>
            <div style={{ marginBottom: 8 }}><Led color={c.ok} size={10} /></div>
            All clear.<br />No active alerts.
          </div>
        )}

        {alerts.map(alert => {
          const sev = sevColor[alert.severity] ?? c.accent
          const label = EVENT_LABEL[alert.event_type] ?? alert.event_type.toUpperCase()
          const ts = new Date(alert.sim_time)
          const timeStr = isNaN(ts.getTime()) ? '' : ts.toLocaleTimeString()
          const isDown = alert.new_state === 'failed' || alert.new_state === 'unreachable'

          return (
            <div
              key={alert.id}
              onClick={() => onDeviceClick(alert.device_id)}
              style={{
                position: 'relative',
                background: c.raised,
                border: `1px solid ${c.line}`,
                borderLeft: `2px solid ${sev}`,
                borderRadius: radius.md,
                padding: '8px 10px 8px 11px',
                marginBottom: 6,
                cursor: 'pointer',
                transition: 'background 0.12s, border-color 0.12s',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = '#1a2332' }}
              onMouseLeave={e => { e.currentTarget.style.background = c.raised }}
            >
              {/* Row 1: LED + severity + tags + time */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                <Led color={sev} size={8} pulse={isDown} />
                <span style={{ fontSize: 9, fontWeight: 700, color: sev, textTransform: 'uppercase', letterSpacing: 0.6 }}>
                  {alert.severity}
                </span>
                <Tag text={label} color={c.dim} />
                {alert.is_manual && <Tag text="MANUAL" color={c.human} />}
                {alert.cascade_from_device_id && <Tag text="CASCADE" color={c.accent} />}
                <span className="mono" style={{ marginLeft: 'auto', fontSize: 9, color: c.faint, fontFamily: font.mono }}>
                  {timeStr}
                </span>
              </div>

              {/* Row 2: hostname + vendor */}
              <div className="mono" style={{ fontSize: 12, color: c.text, fontWeight: 600, fontFamily: font.mono }}>
                {alert.hostname}
                <span style={{ fontWeight: 400, color: c.dim, marginLeft: 6, fontSize: 10, fontFamily: font.sans }}>
                  {alert.vendor}
                </span>
              </div>

              {/* Row 3: site */}
              <div style={{ fontSize: 9, color: c.faint, margin: '1px 0 4px' }}>{alert.site_name}</div>

              {/* Row 4: failure mode → new state */}
              <div className="mono" style={{ fontSize: 10, lineHeight: 1.4, fontFamily: font.mono, wordBreak: 'break-word' }}>
                {alert.failure_mode_id && (
                  <span style={{ color: sev }}>{alert.failure_mode_id}</span>
                )}
                {alert.new_state && (
                  <span style={{ color: c.dim }}> → {alert.new_state}</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Tag({ text, color }: { text: string; color: string }) {
  return (
    <span style={{
      fontSize: 8,
      fontWeight: 700,
      letterSpacing: 0.5,
      color,
      background: tint(color, 0.13),
      border: `1px solid ${tint(color, 0.35)}`,
      borderRadius: 3,
      padding: '1px 4px',
    }}>
      {text}
    </span>
  )
}
