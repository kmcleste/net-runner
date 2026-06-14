import { useState } from 'react'
import { Site } from '../types'

const PATTERNS = [
  {
    id: 'thundering_herd',
    name: 'Thundering Herd',
    icon: '🌩',
    description: 'Morning login storm hits auth + core infrastructure. CPU spikes, DHCP exhaustion on WAPs.',
    severity: 'high',
  },
  {
    id: 'rack_outage',
    name: 'Rack Outage',
    icon: '🔌',
    description: 'PDU trips a breaker. Access switch loses power, cascades to WAPs and endpoints below it.',
    severity: 'critical',
  },
  {
    id: 'wan_flap',
    name: 'WAN Flap',
    icon: '🌐',
    description: 'WAN interface oscillates on a site\'s edge router. BGP reconverges, traffic black-holes briefly.',
    severity: 'high',
  },
  {
    id: 'bad_firmware',
    name: 'Bad Firmware OTA',
    icon: '💾',
    description: 'Botched OTA firmware update hits a batch of WAPs. Some brick, some boot-loop.',
    severity: 'critical',
  },
  {
    id: 'rolling_reboot',
    name: 'Rolling Reboot Storm',
    icon: '🔄',
    description: 'Memory leak triggers cascading reboots across access layer. Multiple sites affected simultaneously.',
    severity: 'high',
  },
]

const SEVERITY_COLOR: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#f59e0b',
  low: '#3b82f6',
}

interface Props {
  sites: Record<string, Site>
  onTriggerPattern: (pattern: string, siteId?: string, vendor?: string) => void
  onSetMultiplier: (v: number) => void
  failureMultiplier: number
  onChangeSeed: (seed: number) => void
  currentSeed: number
}

export function ChaosPanel({
  sites,
  onTriggerPattern,
  onSetMultiplier,
  failureMultiplier,
  onChangeSeed,
  currentSeed,
}: Props) {
  const [open, setOpen] = useState(false)
  const [selectedSite, setSelectedSite] = useState('')
  const [selectedVendor, setSelectedVendor] = useState('')
  const [seedInput, setSeedInput] = useState(String(currentSeed))
  const [multiplier, setMultiplier] = useState(failureMultiplier)

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: 'fixed',
          left: 12,
          bottom: 12,
          background: '#dc2626',
          border: '1px solid #ef4444',
          borderRadius: 8,
          color: '#f9fafb',
          fontSize: 12,
          fontWeight: 700,
          padding: '8px 14px',
          cursor: 'pointer',
          zIndex: 50,
          fontFamily: 'Courier New, monospace',
          letterSpacing: 1,
        }}
      >
        ⚡ CHAOS
      </button>
    )
  }

  return (
    <div style={{
      position: 'fixed',
      left: 12,
      bottom: 12,
      width: 320,
      background: '#0f172a',
      border: '1px solid #374151',
      borderRadius: 10,
      zIndex: 50,
      boxShadow: '0 20px 40px rgba(0,0,0,0.7)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '10px 14px',
        background: '#1e293b',
        borderBottom: '1px solid #374151',
      }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: '#ef4444', letterSpacing: 1 }}>
          ⚡ CHAOS ENGINE
        </span>
        <button
          onClick={() => setOpen(false)}
          style={{ background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', fontSize: 16 }}
        >
          ×
        </button>
      </div>

      <div style={{ padding: 12, maxHeight: 480, overflowY: 'auto' }}>

        {/* Failure multiplier */}
        <div style={{ marginBottom: 14 }}>
          <div style={{
            fontSize: 9, color: '#6b7280', textTransform: 'uppercase',
            letterSpacing: 1, marginBottom: 6, fontWeight: 700,
          }}>
            Global Failure Rate
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type='range'
              min={0.1}
              max={10}
              step={0.1}
              value={multiplier}
              onChange={e => setMultiplier(parseFloat(e.target.value))}
              onMouseUp={() => onSetMultiplier(multiplier)}
              style={{ flex: 1, accentColor: '#ef4444' }}
            />
            <span style={{
              fontSize: 13,
              fontWeight: 700,
              color: multiplier > 3 ? '#ef4444' : multiplier > 1.5 ? '#f97316' : '#22c55e',
              minWidth: 40,
              textAlign: 'right',
            }}>
              {multiplier.toFixed(1)}×
            </span>
          </div>
          <div style={{ fontSize: 9, color: '#4b5563', marginTop: 2 }}>
            1.0 = baseline probability · 5.0 = 5× more failures · 0.1 = quiet
          </div>
        </div>

        {/* World seed */}
        <div style={{ marginBottom: 14 }}>
          <div style={{
            fontSize: 9, color: '#6b7280', textTransform: 'uppercase',
            letterSpacing: 1, marginBottom: 6, fontWeight: 700,
          }}>
            World Seed
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              type='number'
              value={seedInput}
              onChange={e => setSeedInput(e.target.value)}
              style={{
                flex: 1,
                background: '#111827',
                border: '1px solid #374151',
                borderRadius: 4,
                color: '#d1d5db',
                fontSize: 12,
                padding: '4px 8px',
                fontFamily: 'Courier New, monospace',
              }}
            />
            <button
              onClick={() => {
                const n = parseInt(seedInput)
                if (!isNaN(n)) onChangeSeed(n)
              }}
              style={{
                background: '#1d4ed8',
                border: '1px solid #3b82f6',
                borderRadius: 4,
                color: '#f9fafb',
                fontSize: 10,
                padding: '4px 10px',
                cursor: 'pointer',
              }}
            >
              Regenerate
            </button>
          </div>
        </div>

        {/* Scope selectors */}
        <div style={{ marginBottom: 14 }}>
          <div style={{
            fontSize: 9, color: '#6b7280', textTransform: 'uppercase',
            letterSpacing: 1, marginBottom: 6, fontWeight: 700,
          }}>
            Scope (optional)
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <select
              value={selectedSite}
              onChange={e => setSelectedSite(e.target.value)}
              style={{
                flex: 1,
                background: '#111827',
                border: '1px solid #374151',
                borderRadius: 4,
                color: '#d1d5db',
                fontSize: 10,
                padding: '4px 6px',
              }}
            >
              <option value=''>All sites</option>
              {Object.values(sites).map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <select
              value={selectedVendor}
              onChange={e => setSelectedVendor(e.target.value)}
              style={{
                flex: 1,
                background: '#111827',
                border: '1px solid #374151',
                borderRadius: 4,
                color: '#d1d5db',
                fontSize: 10,
                padding: '4px 6px',
              }}
            >
              <option value=''>All vendors</option>
              {['Cisco', 'Cisco Meraki', 'Aruba', 'Juniper', 'Palo Alto', 'Fortinet', 'Dell', 'HPE', 'Netgear', 'TP-Link'].map(v => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Patterns */}
        <div>
          <div style={{
            fontSize: 9, color: '#6b7280', textTransform: 'uppercase',
            letterSpacing: 1, marginBottom: 8, fontWeight: 700,
          }}>
            Chaos Patterns
          </div>
          {PATTERNS.map(p => (
            <div
              key={p.id}
              style={{
                padding: '8px 10px',
                background: '#111827',
                border: `1px solid ${SEVERITY_COLOR[p.severity]}33`,
                borderRadius: 6,
                marginBottom: 6,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <div style={{ fontSize: 12, color: '#f9fafb', fontWeight: 600 }}>
                  {p.icon} {p.name}
                </div>
                <button
                  onClick={() => onTriggerPattern(
                    p.id,
                    selectedSite || undefined,
                    selectedVendor || undefined,
                  )}
                  style={{
                    background: SEVERITY_COLOR[p.severity] + '22',
                    border: `1px solid ${SEVERITY_COLOR[p.severity]}`,
                    borderRadius: 4,
                    color: SEVERITY_COLOR[p.severity],
                    fontSize: 9,
                    fontWeight: 700,
                    padding: '3px 8px',
                    cursor: 'pointer',
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}
                >
                  TRIGGER
                </button>
              </div>
              <div style={{ fontSize: 9, color: '#6b7280', lineHeight: 1.5 }}>
                {p.description}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
