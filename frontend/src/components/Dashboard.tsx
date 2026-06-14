import { Site, WorldSummary } from '../types'

const S = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '8px 16px',
    background: '#1f2937',
    borderBottom: '1px solid #374151',
    flexShrink: 0,
    flexWrap: 'wrap' as const,
    minHeight: 52,
  },
  chip: (color: string) => ({
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    background: '#111827',
    border: `1px solid ${color}`,
    borderRadius: 6,
    padding: '4px 12px',
    minWidth: 80,
  }),
  chipLabel: { fontSize: 9, color: '#9ca3af', textTransform: 'uppercase' as const, letterSpacing: 1 },
  chipValue: (color: string) => ({ fontSize: 18, fontWeight: 700, color, fontFamily: 'Courier New, monospace' }),
  simTime: {
    fontSize: 12,
    color: '#6b7280',
    fontFamily: 'Courier New, monospace',
    marginLeft: 'auto',
  },
  dot: (color: string) => ({
    display: 'inline-block',
    width: 8,
    height: 8,
    borderRadius: '50%',
    background: color,
    marginRight: 4,
  }),
}

interface Props {
  summary: WorldSummary | null
  sites: Record<string, Site>
  selectedSiteId: string | null
  onSiteChange: (id: string | null) => void
  onSimControl: (action: string, speed?: number) => void
}

export function Dashboard({ summary, sites, selectedSiteId, onSiteChange, onSimControl }: Props) {
  if (!summary) {
    return (
      <div style={S.bar}>
        <span style={{ color: '#6b7280', fontSize: 12 }}>Connecting to simulation...</span>
      </div>
    )
  }

  const healthPct = summary.total_devices > 0
    ? Math.round((summary.healthy_count / summary.total_devices) * 100)
    : 0

  const healthColor = healthPct > 95 ? '#22c55e' : healthPct > 80 ? '#f59e0b' : '#ef4444'

  const simDate = new Date(summary.sim_time)
  const simTimeStr = isNaN(simDate.getTime())
    ? 'N/A'
    : simDate.toLocaleString()

  return (
    <div style={S.bar}>
      {/* Org / title */}
      <div style={{ marginRight: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#f9fafb' }}>net-runner</div>
        <div style={{ fontSize: 10, color: '#6b7280' }}>{summary.org_name}</div>
      </div>

      {/* KPI chips */}
      <div style={S.chip('#374151')}>
        <span style={S.chipLabel}>devices</span>
        <span style={S.chipValue('#f9fafb')}>{summary.total_devices}</span>
      </div>

      <div style={S.chip(healthColor)}>
        <span style={S.chipLabel}>healthy</span>
        <span style={S.chipValue(healthColor)}>{healthPct}%</span>
      </div>

      <div style={S.chip('#f59e0b')}>
        <span style={S.chipLabel}>degraded</span>
        <span style={S.chipValue('#f59e0b')}>{summary.degraded_count}</span>
      </div>

      <div style={S.chip('#ef4444')}>
        <span style={S.chipLabel}>failed</span>
        <span style={S.chipValue('#ef4444')}>{summary.failed_count + summary.unreachable_count}</span>
      </div>

      <div style={S.chip('#f97316')}>
        <span style={S.chipLabel}>alerts</span>
        <span style={S.chipValue('#f97316')}>{summary.active_alerts}</span>
      </div>

      <div style={S.chip('#374151')}>
        <span style={S.chipLabel}>sites</span>
        <span style={S.chipValue('#f9fafb')}>{summary.total_sites}</span>
      </div>

      {/* Site filter */}
      <select
        value={selectedSiteId ?? ''}
        onChange={e => onSiteChange(e.target.value || null)}
        style={{
          background: '#111827',
          border: '1px solid #374151',
          borderRadius: 6,
          color: '#d1d5db',
          fontSize: 11,
          padding: '4px 8px',
          fontFamily: 'Courier New, monospace',
        }}
      >
        <option value=''>All sites</option>
        {Object.values(sites).map(s => (
          <option key={s.id} value={s.id}>
            {s.name} ({s.site_type})
          </option>
        ))}
      </select>

      {/* Sim controls */}
      <div style={{ display: 'flex', gap: 6, marginLeft: 4 }}>
        <button
          onClick={() => onSimControl(summary.is_running ? 'pause' : 'play')}
          style={{
            background: summary.is_running ? '#065f46' : '#374151',
            border: `1px solid ${summary.is_running ? '#22c55e' : '#6b7280'}`,
            borderRadius: 4,
            color: '#f9fafb',
            fontSize: 11,
            padding: '4px 10px',
            cursor: 'pointer',
          }}
        >
          {summary.is_running ? '⏸ Pause' : '▶ Play'}
        </button>
        {[1, 10, 60, 300].map(speed => (
          <button
            key={speed}
            onClick={() => onSimControl('set_speed', speed)}
            style={{
              background: summary.sim_speed === speed ? '#1d4ed8' : '#111827',
              border: `1px solid ${summary.sim_speed === speed ? '#3b82f6' : '#374151'}`,
              borderRadius: 4,
              color: '#f9fafb',
              fontSize: 10,
              padding: '4px 8px',
              cursor: 'pointer',
            }}
          >
            {speed}×
          </button>
        ))}
      </div>

      {/* Sim time + status */}
      <div style={S.simTime}>
        <span style={S.dot(summary.is_running ? '#22c55e' : '#6b7280')} />
        {simTimeStr}
        <span style={{ marginLeft: 8, color: '#4b5563' }}>
          seed:{summary.seed} tick:{summary.tick_count}
        </span>
      </div>
    </div>
  )
}
