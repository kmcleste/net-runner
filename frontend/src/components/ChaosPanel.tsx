import { useState } from 'react'
import { Site } from '../types'
import { c, font, radius, sevColor, tint } from '../theme'
import { Led } from './Led'

const PATTERNS = [
  {
    id: 'thundering_herd',
    name: 'Thundering Herd',
    description: 'Morning login storm hits auth + core infrastructure. CPU spikes, DHCP exhaustion on WAPs.',
    severity: 'high',
  },
  {
    id: 'rack_outage',
    name: 'Rack Outage',
    description: 'PDU trips a breaker. Access switch loses power, cascades to WAPs and endpoints below it.',
    severity: 'critical',
  },
  {
    id: 'wan_flap',
    name: 'WAN Flap',
    description: "WAN interface oscillates on a site's edge router. BGP reconverges, traffic black-holes briefly.",
    severity: 'high',
  },
  {
    id: 'bad_firmware',
    name: 'Bad Firmware OTA',
    description: 'Botched OTA firmware update hits a batch of WAPs. Some brick, some boot-loop.',
    severity: 'critical',
  },
  {
    id: 'rolling_reboot',
    name: 'Rolling Reboot Storm',
    description: 'Memory leak triggers cascading reboots across access layer. Multiple sites affected simultaneously.',
    severity: 'high',
  },
]

const VENDORS = ['Cisco', 'Cisco Meraki', 'Aruba', 'Juniper', 'Palo Alto', 'Fortinet', 'Dell', 'HPE', 'Netgear', 'TP-Link']

interface Props {
  sites: Record<string, Site>
  onTriggerPattern: (pattern: string, siteId?: string, vendor?: string) => void
  onSetMultiplier: (v: number) => void
  failureMultiplier: number
  onChangeSeed: (seed: number) => void
  currentSeed: number
  inline?: boolean
}

export function ChaosPanel({
  sites, onTriggerPattern, onSetMultiplier, failureMultiplier, onChangeSeed, currentSeed, inline = false,
}: Props) {
  const [open, setOpen] = useState(false)
  const [selectedSite, setSelectedSite] = useState('')
  const [selectedVendor, setSelectedVendor] = useState('')
  const [seedInput, setSeedInput] = useState(String(currentSeed))
  const [multiplier, setMultiplier] = useState(failureMultiplier)

  const content = (
    <ChaosContent
      sites={sites}
      onTriggerPattern={onTriggerPattern}
      onSetMultiplier={onSetMultiplier}
      multiplier={multiplier}
      setMultiplier={setMultiplier}
      seedInput={seedInput}
      setSeedInput={setSeedInput}
      selectedSite={selectedSite}
      setSelectedSite={setSelectedSite}
      selectedVendor={selectedVendor}
      setSelectedVendor={setSelectedVendor}
      onChangeSeed={onChangeSeed}
    />
  )

  // Mobile: render content directly inside the chaos tab
  if (inline) return content

  // Desktop: floating launcher → panel
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: 'fixed', left: 14, bottom: 14,
          display: 'flex', alignItems: 'center', gap: 7,
          background: tint(c.crit, 0.14),
          border: `1px solid ${c.crit}`,
          borderRadius: radius.lg,
          color: c.crit,
          fontSize: 12,
          fontWeight: 700,
          padding: '9px 15px',
          cursor: 'pointer',
          zIndex: 50,
          letterSpacing: 1.5,
          boxShadow: '0 6px 20px rgba(0,0,0,0.4)',
        }}
      >
        <Led color={c.crit} size={9} pulse /> CHAOS
      </button>
    )
  }

  return (
    <div style={{
      position: 'fixed', left: 14, bottom: 14, width: 330,
      background: c.panel,
      border: `1px solid ${c.line}`,
      borderRadius: radius.lg,
      zIndex: 50,
      boxShadow: '0 24px 48px rgba(0,0,0,0.7)',
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '11px 14px',
        background: `linear-gradient(180deg, ${c.raised}, ${c.panel})`,
        borderBottom: `1px solid ${c.line}`,
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 700, color: c.crit, letterSpacing: 1.5 }}>
          <Led color={c.crit} size={9} pulse /> CHAOS ENGINE
        </span>
        <button
          onClick={() => setOpen(false)}
          style={{ background: 'none', border: 'none', color: c.faint, cursor: 'pointer', fontSize: 18, lineHeight: 1 }}
        >
          ×
        </button>
      </div>
      <div style={{ maxHeight: 'min(70vh, 540px)', overflowY: 'auto', WebkitOverflowScrolling: 'touch' } as React.CSSProperties}>
        {content}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------

interface ContentProps {
  sites: Record<string, Site>
  onTriggerPattern: (pattern: string, siteId?: string, vendor?: string) => void
  onSetMultiplier: (v: number) => void
  multiplier: number
  setMultiplier: (v: number) => void
  seedInput: string
  setSeedInput: (v: string) => void
  selectedSite: string
  setSelectedSite: (v: string) => void
  selectedVendor: string
  setSelectedVendor: (v: string) => void
  onChangeSeed: (seed: number) => void
}

function ChaosContent({
  sites, onTriggerPattern, onSetMultiplier, multiplier, setMultiplier,
  seedInput, setSeedInput, selectedSite, setSelectedSite, selectedVendor, setSelectedVendor, onChangeSeed,
}: ContentProps) {
  const multColor = multiplier > 3 ? c.crit : multiplier > 1.5 ? c.warn : c.ok
  return (
    <div style={{ padding: 13 }}>
      {/* Global failure rate */}
      <Field label="Global failure rate">
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            type="range" min={0.1} max={10} step={0.1} value={multiplier}
            onChange={e => setMultiplier(parseFloat(e.target.value))}
            onMouseUp={() => onSetMultiplier(multiplier)}
            onTouchEnd={() => onSetMultiplier(multiplier)}
            style={{ flex: 1, accentColor: c.crit }}
          />
          <span className="mono" style={{ fontSize: 14, fontWeight: 700, color: multColor, minWidth: 44, textAlign: 'right', fontFamily: font.mono }}>
            {multiplier.toFixed(1)}×
          </span>
        </div>
        <Hint>1.0 = baseline · 5.0 = 5× more failures · 0.1 = quiet</Hint>
      </Field>

      {/* World seed */}
      <Field label="World seed">
        <div style={{ display: 'flex', gap: 7 }}>
          <input
            type="number" value={seedInput} onChange={e => setSeedInput(e.target.value)}
            style={{ ...inputStyle, flex: 1, fontFamily: font.mono }}
          />
          <button
            onClick={() => { const n = parseInt(seedInput); if (!isNaN(n)) onChangeSeed(n) }}
            style={primaryBtn}
          >
            Regenerate
          </button>
        </div>
        <Hint>Regenerating builds a brand-new world from this seed.</Hint>
      </Field>

      {/* Scope */}
      <Field label="Scope (optional)">
        <div style={{ display: 'flex', gap: 7 }}>
          <select value={selectedSite} onChange={e => setSelectedSite(e.target.value)} style={{ ...inputStyle, flex: 1 }}>
            <option value="">All sites</option>
            {Object.values(sites).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select value={selectedVendor} onChange={e => setSelectedVendor(e.target.value)} style={{ ...inputStyle, flex: 1 }}>
            <option value="">All vendors</option>
            {VENDORS.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
      </Field>

      {/* Patterns */}
      <Field label="Chaos patterns">
        {PATTERNS.map(p => {
          const sev = sevColor[p.severity] ?? c.warn
          return (
            <div key={p.id} style={{
              padding: '9px 11px',
              background: c.raised,
              border: `1px solid ${c.line}`,
              borderLeft: `2px solid ${sev}`,
              borderRadius: radius.md,
              marginBottom: 7,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, gap: 8 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: c.text, fontWeight: 600 }}>
                  <Led color={sev} size={8} /> {p.name}
                </span>
                <button
                  onClick={() => onTriggerPattern(p.id, selectedSite || undefined, selectedVendor || undefined)}
                  style={{
                    background: tint(sev, 0.14),
                    border: `1px solid ${sev}`,
                    borderRadius: radius.sm,
                    color: sev,
                    fontSize: 9,
                    fontWeight: 700,
                    padding: '4px 11px',
                    cursor: 'pointer',
                    textTransform: 'uppercase',
                    letterSpacing: 0.6,
                    whiteSpace: 'nowrap',
                  }}
                >
                  Trigger
                </button>
              </div>
              <div style={{ fontSize: 10, color: c.faint, lineHeight: 1.5 }}>{p.description}</div>
            </div>
          )
        })}
      </Field>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 15 }}>
      <div style={{
        fontSize: 9, color: c.faint, textTransform: 'uppercase',
        letterSpacing: 1.2, marginBottom: 7, fontWeight: 700,
      }}>
        {label}
      </div>
      {children}
    </div>
  )
}

function Hint({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 9, color: c.faint, marginTop: 4 }}>{children}</div>
}

const inputStyle: React.CSSProperties = {
  background: c.raised,
  border: `1px solid ${c.line}`,
  borderRadius: radius.sm,
  color: c.dim,
  fontSize: 11,
  padding: '5px 8px',
}

const primaryBtn: React.CSSProperties = {
  background: tint(c.accent, 0.14),
  border: `1px solid ${c.accent}`,
  borderRadius: radius.sm,
  color: c.accent,
  fontSize: 10,
  fontWeight: 600,
  padding: '5px 11px',
  cursor: 'pointer',
  whiteSpace: 'nowrap',
}
