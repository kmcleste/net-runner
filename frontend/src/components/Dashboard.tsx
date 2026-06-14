import { Site, WorldSummary } from '../types'
import { c, font, radius, tint } from '../theme'
import { Led } from './Led'

interface Props {
  summary: WorldSummary | null
  sites: Record<string, Site>
  selectedSiteId: string | null
  onSiteChange: (id: string | null) => void
  onSimControl: (action: string, speed?: number) => void
  isMobile: boolean
}

export function Dashboard({ summary, sites, selectedSiteId, onSiteChange, onSimControl, isMobile }: Props) {
  if (!summary) {
    return (
      <div style={styles.bar}>
        <span style={{ color: c.faint, fontSize: 12 }}>Connecting…</span>
      </div>
    )
  }

  const down = summary.failed_count + summary.unreachable_count
  const healthPct = summary.total_devices > 0
    ? Math.round((summary.healthy_count / summary.total_devices) * 100)
    : 0
  const healthColor = healthPct > 95 ? c.ok : healthPct > 80 ? c.warn : c.crit
  const simDate = new Date(summary.sim_time)
  const timeStr = isNaN(simDate.getTime()) ? '' : simDate.toLocaleTimeString()

  // ---- Mobile -----------------------------------------------------------
  if (isMobile) {
    return (
      <div style={{ ...styles.bar, flexDirection: 'column', gap: 7, padding: '8px 12px', minHeight: 'auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
          <Brand compact />
          <div style={{ flex: 1 }} />
          <TransportButton
            label={summary.is_running ? '❚❚' : '▶'}
            active={summary.is_running}
            onClick={() => onSimControl(summary.is_running ? 'pause' : 'play')}
          />
          {[10, 60, 300].map(s => (
            <TransportButton key={s} label={`${s}×`} active={summary.sim_speed === s}
              onClick={() => onSimControl('set_speed', s)} />
          ))}
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center', width: '100%', overflowX: 'auto' }}>
          <Pill led={healthColor} value={`${healthPct}%`} label="ok" />
          <Pill led={c.warn} value={summary.degraded_count} label="deg" />
          <Pill led={c.crit} value={down} label="down" pulse={down > 0} />
          <Pill led={summary.active_alerts > 0 ? c.warn : c.faint} value={summary.active_alerts} label="alerts" />
          <select value={selectedSiteId ?? ''} onChange={e => onSiteChange(e.target.value || null)} style={selectStyle}>
            <option value=''>All sites</option>
            {Object.values(sites).map(s => (
              <option key={s.id} value={s.id}>{s.city} ({s.site_type})</option>
            ))}
          </select>
        </div>
      </div>
    )
  }

  // ---- Desktop ----------------------------------------------------------
  return (
    <div style={styles.bar}>
      <Brand org={summary.org_name} />

      <div style={styles.divider} />

      <Kpi led={healthColor} value={`${healthPct}%`} label="healthy" />
      <Kpi led={c.warn} value={summary.degraded_count} label="degraded" />
      <Kpi led={c.crit} value={down} label="down" pulse={down > 0} />
      <Kpi led={summary.active_alerts > 0 ? c.warn : c.faint} value={summary.active_alerts} label="alerts" />
      <Kpi led={c.accent} value={summary.total_devices} label="devices" mutedLed />
      <Kpi led={c.accent} value={summary.total_sites} label="sites" mutedLed />

      <div style={styles.divider} />

      <select value={selectedSiteId ?? ''} onChange={e => onSiteChange(e.target.value || null)} style={selectStyle}>
        <option value=''>All sites</option>
        {Object.values(sites).map(s => (
          <option key={s.id} value={s.id}>{s.name} ({s.site_type})</option>
        ))}
      </select>

      <div style={{ display: 'flex', gap: 5 }}>
        <TransportButton
          label={summary.is_running ? '❚❚ Pause' : '▶ Run'}
          active={summary.is_running}
          onClick={() => onSimControl(summary.is_running ? 'pause' : 'play')}
        />
        {[1, 10, 60, 300].map(s => (
          <TransportButton key={s} label={`${s}×`} active={summary.sim_speed === s}
            onClick={() => onSimControl('set_speed', s)} />
        ))}
      </div>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: c.dim, fontFamily: font.mono }}
          className="mono">
          <Led color={summary.is_running ? c.ok : c.faint} size={8} pulse={summary.is_running} />
          {timeStr}
        </span>
        <span style={{ fontSize: 11, color: c.faint, fontFamily: font.mono, letterSpacing: 0.5 }}>
          seed&nbsp;{summary.seed}
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------

function Brand({ org, compact }: { org?: string; compact?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{
        fontSize: 17,
        color: c.accent,
        textShadow: `0 0 10px ${tint(c.accent, 0.7)}`,
        lineHeight: 1,
      }}>◈</span>
      <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.15 }}>
        <span style={{ fontSize: compact ? 13 : 14, fontWeight: 700, color: c.text, letterSpacing: 0.3 }}>
          net&#8209;runner
        </span>
        {!compact && org && (
          <span style={{ fontSize: 10, color: c.faint, letterSpacing: 0.2 }}>{org}</span>
        )}
      </div>
    </div>
  )
}

function Kpi({ led, value, label, pulse, mutedLed }: {
  led: string; value: string | number; label: string; pulse?: boolean; mutedLed?: boolean
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 4px' }}>
      <Led color={led} size={mutedLed ? 7 : 9} pulse={pulse} />
      <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.05 }}>
        <span className="mono" style={{ fontSize: 18, fontWeight: 600, color: c.text, fontFamily: font.mono }}>
          {value}
        </span>
        <span style={{ fontSize: 9, color: c.faint, textTransform: 'uppercase', letterSpacing: 1.2 }}>
          {label}
        </span>
      </div>
    </div>
  )
}

function Pill({ led, value, label, pulse }: { led: string; value: string | number; label: string; pulse?: boolean }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 5,
      background: c.raised, border: `1px solid ${c.line}`,
      borderRadius: radius.pill, padding: '3px 9px 3px 7px', whiteSpace: 'nowrap',
    }}>
      <Led color={led} size={8} pulse={pulse} />
      <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: c.text, fontFamily: font.mono }}>{value}</span>
      <span style={{ fontSize: 9, color: c.faint, textTransform: 'uppercase', letterSpacing: 0.6 }}>{label}</span>
    </div>
  )
}

function TransportButton({ label, active, onClick }: { label: string; active?: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? tint(c.accent, 0.16) : 'transparent',
        border: `1px solid ${active ? c.accent : c.line}`,
        borderRadius: radius.sm,
        color: active ? c.accent : c.dim,
        fontSize: 11,
        fontWeight: 600,
        padding: '5px 10px',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
        fontFamily: font.mono,
        transition: 'border-color 0.15s, color 0.15s',
      }}
    >
      {label}
    </button>
  )
}

const styles: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '0 16px',
    background: `linear-gradient(180deg, ${c.raised}, ${c.panel})`,
    borderBottom: `1px solid ${c.line}`,
    boxShadow: '0 1px 0 rgba(0,0,0,0.4)',
    flexShrink: 0,
    flexWrap: 'wrap',
    minHeight: 56,
  },
  divider: {
    width: 1,
    alignSelf: 'stretch',
    margin: '12px 2px',
    background: c.line,
  },
}

const selectStyle: React.CSSProperties = {
  background: c.raised,
  border: `1px solid ${c.line}`,
  borderRadius: radius.sm,
  color: c.dim,
  fontSize: 11,
  padding: '5px 8px',
  fontFamily: font.mono,
  maxWidth: 170,
  cursor: 'pointer',
}
