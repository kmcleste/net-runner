import { Site, WorldSummary } from '../types'

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
        <span style={{ color: '#6b7280', fontSize: 12 }}>Connecting...</span>
      </div>
    )
  }

  const healthPct = summary.total_devices > 0
    ? Math.round((summary.healthy_count / summary.total_devices) * 100)
    : 0
  const healthColor = healthPct > 95 ? '#22c55e' : healthPct > 80 ? '#f59e0b' : '#ef4444'
  const simDate = new Date(summary.sim_time)
  const timeStr = isNaN(simDate.getTime()) ? '' : simDate.toLocaleTimeString()

  if (isMobile) {
    return (
      <div style={{ ...styles.bar, flexDirection: 'column', gap: 6, padding: '6px 12px', minHeight: 'auto' }}>
        {/* Row 1: title + play/pause + speed */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: '#f9fafb', flex: 1 }}>
            ◈ net-runner
          </span>
          <button
            onClick={() => onSimControl(summary.is_running ? 'pause' : 'play')}
            style={btnStyle(summary.is_running ? '#22c55e' : '#6b7280')}
          >
            {summary.is_running ? '⏸' : '▶'}
          </button>
          {[10, 60, 300].map(s => (
            <button key={s} onClick={() => onSimControl('set_speed', s)}
              style={btnStyle(summary.sim_speed === s ? '#3b82f6' : '#374151', summary.sim_speed === s)}>
              {s}×
            </button>
          ))}
          <span style={{ fontSize: 9, color: '#4b5563', marginLeft: 4 }}>{timeStr}</span>
        </div>

        {/* Row 2: KPI pills + site filter */}
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', width: '100%', overflowX: 'auto' }}>
          <Pill label={`${healthPct}%`} color={healthColor} sublabel="ok" />
          <Pill label={String(summary.degraded_count)} color="#f59e0b" sublabel="deg" />
          <Pill label={String(summary.failed_count + summary.unreachable_count)} color="#ef4444" sublabel="down" />
          <Pill label={String(summary.active_alerts)} color="#f97316" sublabel="alerts" />
          <select
            value={selectedSiteId ?? ''}
            onChange={e => onSiteChange(e.target.value || null)}
            style={selectStyle}
          >
            <option value=''>All sites</option>
            {Object.values(sites).map(s => (
              <option key={s.id} value={s.id}>{s.city} ({s.site_type})</option>
            ))}
          </select>
        </div>
      </div>
    )
  }

  // Desktop layout
  return (
    <div style={styles.bar}>
      <div style={{ marginRight: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#f9fafb' }}>◈ net-runner</div>
        <div style={{ fontSize: 10, color: '#6b7280' }}>{summary.org_name}</div>
      </div>

      <Chip label="devices" value={summary.total_devices} color="#f9fafb" />
      <Chip label="healthy" value={`${healthPct}%`} color={healthColor} />
      <Chip label="degraded" value={summary.degraded_count} color="#f59e0b" />
      <Chip label="failed" value={summary.failed_count + summary.unreachable_count} color="#ef4444" />
      <Chip label="alerts" value={summary.active_alerts} color="#f97316" />
      <Chip label="sites" value={summary.total_sites} color="#f9fafb" />

      <select value={selectedSiteId ?? ''} onChange={e => onSiteChange(e.target.value || null)} style={selectStyle}>
        <option value=''>All sites</option>
        {Object.values(sites).map(s => (
          <option key={s.id} value={s.id}>{s.name} ({s.site_type})</option>
        ))}
      </select>

      <div style={{ display: 'flex', gap: 6 }}>
        <button onClick={() => onSimControl(summary.is_running ? 'pause' : 'play')}
          style={btnStyle(summary.is_running ? '#22c55e' : '#6b7280')}>
          {summary.is_running ? '⏸ Pause' : '▶ Play'}
        </button>
        {[1, 10, 60, 300].map(s => (
          <button key={s} onClick={() => onSimControl('set_speed', s)}
            style={btnStyle(summary.sim_speed === s ? '#3b82f6' : '#374151', summary.sim_speed === s)}>
            {s}×
          </button>
        ))}
      </div>

      <div style={{ marginLeft: 'auto', fontSize: 11, color: '#6b7280', fontFamily: 'Courier New, monospace' }}>
        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: summary.is_running ? '#22c55e' : '#6b7280', marginRight: 4 }} />
        {new Date(summary.sim_time).toLocaleString()}
        <span style={{ marginLeft: 8, color: '#374151' }}>seed:{summary.seed}</span>
      </div>
    </div>
  )
}

function Chip({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', background: '#111827', border: '1px solid #374151', borderRadius: 6, padding: '4px 12px', minWidth: 70 }}>
      <span style={{ fontSize: 9, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 1 }}>{label}</span>
      <span style={{ fontSize: 18, fontWeight: 700, color, fontFamily: 'Courier New, monospace' }}>{value}</span>
    </div>
  )
}

function Pill({ label, color, sublabel }: { label: string; color: string; sublabel: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 3, background: color + '22', border: `1px solid ${color}`, borderRadius: 12, padding: '2px 8px', whiteSpace: 'nowrap' }}>
      <span style={{ fontSize: 12, fontWeight: 700, color }}>{label}</span>
      <span style={{ fontSize: 9, color: '#6b7280' }}>{sublabel}</span>
    </div>
  )
}

const styles = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 16px',
    background: '#1f2937',
    borderBottom: '1px solid #374151',
    flexShrink: 0,
    flexWrap: 'wrap' as const,
    minHeight: 52,
  },
}

const selectStyle: React.CSSProperties = {
  background: '#111827',
  border: '1px solid #374151',
  borderRadius: 6,
  color: '#d1d5db',
  fontSize: 11,
  padding: '4px 8px',
  fontFamily: 'Courier New, monospace',
  maxWidth: 160,
}

function btnStyle(borderColor: string, active = false): React.CSSProperties {
  return {
    background: active ? borderColor + '33' : '#111827',
    border: `1px solid ${borderColor}`,
    borderRadius: 4,
    color: '#f9fafb',
    fontSize: 11,
    padding: '4px 10px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  }
}
