import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from 'react-simple-maps'
import { Device, Site } from '../types'
import { c, font, radius, tint } from '../theme'
import { healthColor, siteStats } from '../utils/siteHealth'
import { Led } from './Led'

// ---------------------------------------------------------------------------
// Geo data
// ---------------------------------------------------------------------------

// FIPS code → two-letter state abbreviation (us-atlas uses FIPS ids)
const FIPS_TO_STATE: Record<string, string> = {
  '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA',
  '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC', '12': 'FL',
  '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN',
  '19': 'IA', '20': 'KS', '21': 'KY', '22': 'LA', '23': 'ME',
  '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS',
  '29': 'MO', '30': 'MT', '31': 'NE', '32': 'NV', '33': 'NH',
  '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND',
  '39': 'OH', '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI',
  '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT',
  '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI',
  '56': 'WY', '72': 'PR',
}

// [longitude, latitude] for each city in the simulation
const CITY_COORDS: Record<string, [number, number]> = {
  'Chicago':        [-87.629_8,  41.878_1],
  'New York':       [-74.005_9,  40.712_8],
  'Dallas':         [-96.797_0,  32.776_7],
  'Atlanta':        [-84.388_0,  33.749_0],
  'Phoenix':        [-112.074_0, 33.448_4],
  'Denver':         [-104.990_3, 39.739_2],
  'Seattle':        [-122.332_1, 47.606_2],
  'Boston':         [-71.058_9,  42.360_1],
  'Miami':          [-80.191_8,  25.761_7],
  'Minneapolis':    [-93.265_0,  44.977_8],
  'Detroit':        [-83.045_8,  42.331_4],
  'Kansas City':    [-94.578_6,  39.099_7],
  'Nashville':      [-86.781_6,  36.162_7],
  'Portland':       [-122.675_0, 45.505_1],
  'Salt Lake City': [-111.891_0, 40.760_8],
  'Omaha':          [-95.934_5,  41.256_5],
  'Richmond':       [-77.436_0,  37.540_7],
  'Louisville':     [-85.758_5,  38.252_7],
  'Albuquerque':    [-106.650_4, 35.084_4],
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface SiteInfo {
  site: Site
  color: string
  coords: [number, number] | null
  failed: number
  impaired: number
  total: number
}

function buildSiteInfos(
  sites: Record<string, Site>,
  devices: Record<string, Device>,
): SiteInfo[] {
  return Object.values(sites).map(site => {
    const stats = siteStats(site.device_ids, devices)
    const coords = CITY_COORDS[site.city] ?? null
    return {
      site,
      color: healthColor(stats),
      coords,
      failed: stats.failed,
      impaired: stats.impaired,
      total: stats.total,
    }
  })
}

// Worst-case health color per state
function stateColorMap(siteInfos: SiteInfo[]): Record<string, string> {
  const result: Record<string, string> = {}
  for (const info of siteInfos) {
    const sc = info.site.state_code
    const existing = result[sc]
    if (!existing) {
      result[sc] = info.color
    } else if (existing === c.ok || (existing === c.warn && info.color === c.crit)) {
      result[sc] = info.color
    }
  }
  return result
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  sites: Record<string, Site>
  devices: Record<string, Device>
  selectedSiteId: string | null
  onSiteSelect: (siteId: string | null) => void
  onDrillIntoTopo: (siteId: string) => void
  isMobile?: boolean
  onSwitchToTopo?: () => void
}

export function ChoroplethView({
  sites, devices, selectedSiteId, onSiteSelect, onDrillIntoTopo, isMobile = false, onSwitchToTopo,
}: Props) {
  const siteInfos = buildSiteInfos(sites, devices)
  const stateColors = stateColorMap(siteInfos)

  const stateToSite: Record<string, string> = {}
  for (const info of siteInfos) {
    stateToSite[info.site.state_code] = info.site.id
  }

  const handleStateClick = (stateCode: string) => {
    const siteId = stateToSite[stateCode]
    if (!siteId) return
    onSiteSelect(siteId === selectedSiteId ? null : siteId)
  }

  const activeSiteInfo = selectedSiteId ? siteInfos.find(i => i.site.id === selectedSiteId) : null

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: isMobile ? '8px 12px' : '10px 16px',
        borderBottom: `1px solid ${c.line}`,
        flexShrink: 0,
        gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {selectedSiteId && (
            <button
              onClick={() => onSiteSelect(null)}
              style={{
                background: 'none', border: 'none', color: c.accent,
                fontSize: 11, fontFamily: font.sans, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 4, padding: 0,
              }}
            >
              ← All sites
            </button>
          )}
          <span style={{ fontSize: 11, color: c.faint, fontFamily: font.mono, letterSpacing: 1 }}>
            GEO / US IMPACT MAP
          </span>
          {onSwitchToTopo && (
            <>
              <span style={{ color: c.line, fontSize: 11 }}>|</span>
              <button
                onClick={onSwitchToTopo}
                style={{
                  background: 'none', border: 'none', color: c.accent,
                  fontSize: 11, fontFamily: font.sans, cursor: 'pointer',
                  padding: 0, fontWeight: 600,
                }}
              >
                ◈ Topo
              </button>
            </>
          )}
        </div>
        <Legend />
      </div>

      {/* Map — fills remaining height; site panel overlays bottom so map doesn't shrink */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <ComposableMap
          projection="geoAlbersUsa"
          projectionConfig={{ scale: isMobile ? 520 : 820 }}
          style={{ width: '100%', height: '100%' }}
        >
          <ZoomableGroup zoom={1}>
            <Geographies geography="/us-states.json">
              {({ geographies }) =>
                geographies.map(geo => {
                  const stateCode = FIPS_TO_STATE[geo.id as string] ?? ''
                  const siteId = stateToSite[stateCode]
                  const fillColor = stateColors[stateCode]
                  const isSelected = !!(siteId && siteId === selectedSiteId)
                  const hasData = !!fillColor
                  return (
                    <Geography
                      key={geo.rsmKey}
                      geography={geo}
                      onClick={() => handleStateClick(stateCode)}
                      style={{
                        default: {
                          fill: isSelected
                            ? tint(fillColor ?? c.accent, 0.45)
                            : hasData ? tint(fillColor, 0.22) : c.raised,
                          stroke: isSelected ? (fillColor ?? c.accent) : c.line,
                          strokeWidth: isSelected ? 2 : 0.5,
                          outline: 'none',
                          cursor: hasData ? 'pointer' : 'default',
                          transition: 'fill 0.15s',
                        },
                        hover: {
                          fill: hasData ? tint(fillColor, 0.38) : c.raised,
                          stroke: hasData ? fillColor : c.line,
                          strokeWidth: hasData ? 1 : 0.5,
                          outline: 'none',
                          cursor: hasData ? 'pointer' : 'default',
                        },
                        pressed: {
                          fill: hasData ? tint(fillColor, 0.55) : c.raised,
                          outline: 'none',
                        },
                      }}
                    />
                  )
                })
              }
            </Geographies>

            {/* Site markers */}
            {siteInfos.map(info => {
              if (!info.coords) return null
              const isSelected = info.site.id === selectedSiteId
              const markerSize = info.site.site_type === 'hq' ? 10
                : info.site.site_type === 'regional' ? 8 : 6

              return (
                <Marker
                  key={info.site.id}
                  coordinates={info.coords}
                  onClick={() => onSiteSelect(info.site.id === selectedSiteId ? null : info.site.id)}
                  style={{ cursor: 'pointer' }}
                >
                  {/* Outer pulse ring for impaired / selected */}
                  {(info.impaired > 0 || isSelected) && (
                    <circle
                      r={markerSize * (isSelected ? 2.4 : 1.8)}
                      fill="none"
                      stroke={info.color}
                      strokeWidth={isSelected ? 1.5 : 1}
                      opacity={isSelected ? 0.6 : 0.35}
                      className={info.failed > 0 ? 'led-pulse' : undefined}
                    />
                  )}
                  {/* Core dot */}
                  <circle
                    r={markerSize}
                    fill={info.color}
                    stroke={isSelected ? '#fff' : c.panel}
                    strokeWidth={isSelected ? 2 : 1.5}
                    style={{ filter: `drop-shadow(0 0 ${markerSize * 0.8}px ${info.color})` }}
                  />
                  {/* Diamond accent for HQ */}
                  {info.site.site_type === 'hq' && (
                    <rect
                      x={-markerSize * 0.7} y={-markerSize * 0.7}
                      width={markerSize * 1.4} height={markerSize * 1.4}
                      fill="none" stroke="#fff" strokeWidth={1} opacity={0.5}
                      transform="rotate(45)"
                    />
                  )}
                </Marker>
              )
            })}
          </ZoomableGroup>
        </ComposableMap>

        {/* Selected-site panel — overlays the map bottom so the map keeps full height */}
        {activeSiteInfo && (
          <SitePanel
            info={activeSiteInfo}
            onClose={() => onSiteSelect(null)}
            onViewTopo={() => onDrillIntoTopo(activeSiteInfo.site.id)}
          />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Legend() {
  const items = [
    { color: c.ok,   label: 'Healthy' },
    { color: c.warn, label: 'Degraded' },
    { color: c.crit, label: 'Failing' },
  ]
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
      {items.map(({ color, label }) => (
        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <Led color={color} size={7} />
          <span style={{ fontSize: 9, color: c.faint, fontFamily: font.sans, letterSpacing: 0.5, textTransform: 'uppercase' }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  )
}

interface SitePanelProps {
  info: SiteInfo
  onClose: () => void
  onViewTopo: () => void
}

function SitePanel({ info, onClose, onViewTopo }: SitePanelProps) {
  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      background: `${c.panel}f0`,
      backdropFilter: 'blur(12px)',
      borderTop: `1px solid ${info.color}60`,
      padding: '14px 16px',
      display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      {/* Top row: LED + name + close */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Led color={info.color} size={11} pulse={info.failed > 0} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: c.text, fontFamily: font.sans }}>
            {info.site.name}
          </div>
          <div style={{ fontSize: 10, color: c.dim, marginTop: 1 }}>
            {info.site.city}, {info.site.state_code} · {info.site.site_type} · {info.site.employee_count.toLocaleString()} employees
          </div>
        </div>
        <button
          onClick={onClose}
          style={{ background: 'none', border: 'none', color: c.faint, cursor: 'pointer', fontSize: 20, lineHeight: 1, padding: 4 }}
        >
          ×
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 0, borderTop: `1px solid ${c.line}`, paddingTop: 10 }}>
        <StatCell value={info.total - info.impaired} label="OK" color={c.ok} />
        <StatCell value={info.failed} label="FAILED" color={c.crit} />
        <StatCell value={info.impaired - info.failed} label="DEGRADED" color={c.warn} />
        <StatCell value={info.total} label="TOTAL" color={c.faint} />
      </div>

      {/* Action: drill into topology */}
      <button
        onClick={onViewTopo}
        style={{
          background: tint(c.accent, 0.12),
          border: `1px solid ${c.accent}`,
          borderRadius: radius.md,
          color: c.accent,
          fontSize: 12,
          fontWeight: 700,
          fontFamily: font.sans,
          padding: '9px 14px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          letterSpacing: 0.5,
        }}
      >
        ◈ View device topology
      </button>
    </div>
  )
}

function StatCell({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{ flex: 1, textAlign: 'center', padding: '0 4px' }}>
      <div style={{ fontSize: 20, fontWeight: 700, color, fontFamily: font.mono }}>{value}</div>
      <div style={{ fontSize: 8, color: c.faint, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 2 }}>{label}</div>
    </div>
  )
}
