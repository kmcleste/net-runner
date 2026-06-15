import cytoscape, { Core, ElementDefinition } from 'cytoscape'
import { useEffect, useRef } from 'react'
import { Device, DeviceCategory, DeviceState, Site, TopologyData } from '../types'
import { c, font, radius } from '../theme'
import { healthColor, siteStats } from '../utils/siteHealth'
import { Led } from './Led'

// Color by state — shared LED palette so nodes match the rest of the console
const STATE_COLOR: Record<DeviceState, string> = {
  healthy: c.ok,
  degraded: c.warn,
  failed: c.crit,
  unreachable: c.down,
  recovering: c.recover,
  rebooting: c.reboot,
  maintenance: c.maint,
}

// Shape by category
const CATEGORY_SHAPE: Record<DeviceCategory, string> = {
  wan_edge: 'triangle',
  router: 'triangle',
  switch_core: 'diamond',
  switch_dist: 'rectangle',
  switch_access: 'round-rectangle',
  firewall: 'pentagon',
  wap: 'ellipse',
  wireless_controller: 'ellipse',
  load_balancer: 'barrel',
  server: 'round-rectangle',
  storage: 'barrel',
  endpoint: 'ellipse',
  phone: 'ellipse',
  printer: 'ellipse',
  ups: 'rectangle',
  pdu: 'rectangle',
}

// Short vendor badge
const VENDOR_BADGE: Record<string, string> = {
  'Cisco': 'CSCO',
  'Cisco Meraki': 'MRKI',
  'Aruba': 'ARBA',
  'Juniper': 'JNPR',
  'Palo Alto': 'PANO',
  'Fortinet': 'FRTI',
  'Dell': 'DELL',
  'HPE': 'HPE',
  'Netgear': 'NTGR',
  'TP-Link': 'TPLK',
  'Ubiquiti': 'UBQT',
}

// ---------------------------------------------------------------------------
// Site-level aggregation (the "All sites" overview)
// ---------------------------------------------------------------------------

function buildSiteElements(
  sites: Record<string, Site>,
  devices: Record<string, Device>,
  uiScale: number,
  includeHub: boolean,
): ElementDefinition[] {
  const elements: ElementDefinition[] = []

  // Central WAN core (desktop hub-and-spoke only — on mobile the sites tile
  // into a grid, where spokes would just be visual noise)
  if (includeHub) {
    const allIds = Object.values(sites).flatMap(s => s.device_ids)
    const org = siteStats(allIds, devices)
    elements.push({
      group: 'nodes',
      data: { id: '__wan__', kind: 'core', label: 'WAN\ncore' },
      style: {
        'background-color': healthColor(org),
        'shape': 'hexagon',
        'width': Math.round(64 * uiScale),
        'height': Math.round(64 * uiScale),
        'border-color': c.accent,
        'border-width': 2,
        'font-size': `${Math.round(12 * uiScale)}px`,
        'font-weight': 700,
      },
    })
  }

  for (const site of Object.values(sites)) {
    const st = siteStats(site.device_ids, devices)
    const size = Math.round((40 + Math.sqrt(st.total) * 5) * uiScale)
    const shape = site.site_type === 'hq' ? 'diamond'
      : site.site_type === 'regional' ? 'round-rectangle' : 'ellipse'
    elements.push({
      group: 'nodes',
      data: { id: site.id, kind: 'site', label: `${site.name}\n${st.impaired}/${st.total} impaired` },
      style: {
        'background-color': healthColor(st),
        'shape': shape,
        'width': size,
        'height': size,
        'border-color': st.failed > 0 ? c.crit : '#2a3647',
        'border-width': st.failed > 0 ? 3 : 1,
        'font-size': `${Math.round(11 * uiScale)}px`,
      },
    })
    if (includeHub) {
      elements.push({
        group: 'edges',
        data: { id: `wan-${site.id}`, source: '__wan__', target: site.id },
      })
    }
  }

  return elements
}

// ---------------------------------------------------------------------------
// Device-level elements (within a single site)
// ---------------------------------------------------------------------------

function buildElements(topology: TopologyData, devices: Record<string, Device>): ElementDefinition[] {
  const elements: ElementDefinition[] = []

  for (const node of topology.nodes) {
    const device = devices[node.id]
    const vendor = device?.vendor ?? node.vendor
    const badge = VENDOR_BADGE[vendor] ?? vendor.slice(0, 4).toUpperCase()
    const isConsumer = node.is_consumer_grade

    elements.push({
      group: 'nodes',
      data: {
        id: node.id,
        kind: 'device',
        label: `${node.label}\n${badge}`,
        category: node.category,
        state: node.state,
        vendor,
        site_id: node.site_id,
        is_consumer: isConsumer,
      },
      style: {
        'background-color': STATE_COLOR[node.state as DeviceState] ?? c.down,
        'shape': CATEGORY_SHAPE[node.category as DeviceCategory] ?? 'ellipse',
        'border-color': isConsumer ? '#f97316' : '#2a3647',
        'border-width': isConsumer ? 3 : 1,
      },
    })
  }

  for (const edge of topology.edges) {
    elements.push({
      group: 'edges',
      data: { id: `${edge.source}-${edge.target}`, source: edge.source, target: edge.target },
    })
  }

  return elements
}

function ZoomButton({ label, onClick, title }: { label: string; onClick: () => void; title?: string }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        width: 34, height: 34,
        background: 'rgba(15,21,32,0.92)',
        border: `1px solid ${c.line}`,
        borderRadius: radius.md,
        color: c.dim,
        fontSize: 18,
        lineHeight: 1,
        cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backdropFilter: 'blur(4px)',
      }}
    >
      {label}
    </button>
  )
}

interface Props {
  topology: TopologyData | null
  devices: Record<string, Device>
  sites: Record<string, Site>
  selectedSiteId: string | null
  onDeviceClick: (deviceId: string) => void
  onSiteSelect: (siteId: string | null) => void
  isMobile?: boolean
}

// Scale UI up on large / high-DPI displays so a 4K canvas isn't full of
// tiny nodes. 1.0 at ~1800px logical width, capped at 2.2 for very wide displays.
function computeUiScale(isMobile: boolean): number {
  if (isMobile) return 1
  if (typeof window === 'undefined') return 1
  return Math.min(2.2, Math.max(1, window.innerWidth / 1800))
}

export function TopologyView({
  topology, devices, sites, selectedSiteId, onDeviceClick, onSiteSelect, isMobile = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const siteMode = !selectedSiteId

  useEffect(() => {
    if (!containerRef.current || !topology) return

    const uiScale = computeUiScale(isMobile)
    const nodeSize = Math.round((isMobile ? 44 : 34) * uiScale)
    const fontSize = `${Math.round((isMobile ? 11 : 10) * uiScale)}px`

    // Build either the site overview or the in-site device graph
    let elements: ElementDefinition[]
    let layout: cytoscape.LayoutOptions
    if (siteMode) {
      elements = buildSiteElements(sites, devices, uiScale, !isMobile)
      layout = isMobile
        ? {
            // Tile the sites into a grid — fills a tall phone screen far better
            // than a wide ring and keeps every label readable.
            name: 'grid',
            avoidOverlap: true,
            nodeDimensionsIncludeLabels: true,
            padding: 24,
            condense: false,
          } as cytoscape.LayoutOptions
        : {
            name: 'concentric',
            concentric: (n: cytoscape.NodeSingular) => (n.data('kind') === 'core' ? 10 : 1),
            levelWidth: () => 1,
            minNodeSpacing: Math.round(48 * uiScale),
            nodeDimensionsIncludeLabels: true,
            padding: 30,
            avoidOverlap: true,
          } as cytoscape.LayoutOptions
    } else {
      const filtered = {
        nodes: topology.nodes.filter(n => n.site_id === selectedSiteId),
        edges: topology.edges.filter(e => {
          const src = topology.nodes.find(n => n.id === e.source)
          const tgt = topology.nodes.find(n => n.id === e.target)
          return src?.site_id === selectedSiteId && tgt?.site_id === selectedSiteId
        }),
      }
      elements = buildElements(filtered, devices)
      layout = {
        name: 'breadthfirst',
        directed: true,
        padding: 20,
        spacingFactor: 1.4 * uiScale,
        avoidOverlap: true,
        nodeDimensionsIncludeLabels: true,
      } as cytoscape.LayoutOptions
    }

    if (cyRef.current) cyRef.current.destroy()

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'width': nodeSize,
            'height': nodeSize,
            'label': 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'color': c.dim,
            'font-size': fontSize,
            'font-family': 'IBM Plex Mono, monospace',
            'text-wrap': 'wrap',
            'text-max-width': `${Math.round((isMobile ? 100 : 96) * uiScale)}px`,
            'text-margin-y': Math.round((isMobile ? 6 : 4) * uiScale),
          },
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#2a3647',
            'width': 1.5 * uiScale,
            'target-arrow-shape': 'none',
            'curve-style': 'bezier',
            'opacity': 0.6,
          },
        },
        {
          selector: 'node[kind="site"], node[kind="core"]',
          style: { 'color': c.text, 'text-margin-y': Math.round(6 * uiScale) },
        },
        {
          selector: 'node:selected',
          style: { 'border-color': c.accent, 'border-width': 3 },
        },
        {
          selector: 'node[state="failed"]',
          style: { 'border-color': c.crit, 'border-width': 2 },
        },
        {
          selector: 'node[state="unreachable"]',
          style: { 'opacity': 0.5 },
        },
      ],
      layout,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      wheelSensitivity: 0.3,
      minZoom: 0.1,
      maxZoom: 4,
      touchTapThreshold: 8,
      desktopTapThreshold: 4,
    })

    cy.one('layoutstop', () => cy.fit(undefined, Math.round(40 * uiScale)))

    cy.on('tap', 'node', (evt) => {
      const kind = evt.target.data('kind')
      if (kind === 'site') onSiteSelect(evt.target.id())
      else if (kind === 'device') onDeviceClick(evt.target.id())
      // core node: no-op
    })

    cyRef.current = cy

    const handleResize = () => {
      cy.resize()
      cy.fit(undefined, Math.round(40 * uiScale))
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      cy.destroy()
      cyRef.current = null
    }
  }, [topology, selectedSiteId, sites]) // eslint-disable-line react-hooks/exhaustive-deps

  // Live-update colors/labels without a full rebuild
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().forEach(node => {
      const kind = node.data('kind')
      if (kind === 'site') {
        const site = sites[node.id()]
        if (!site) return
        const st = siteStats(site.device_ids, devices)
        node.style('background-color', healthColor(st))
        node.style('border-color', st.failed > 0 ? c.crit : '#2a3647')
        node.style('border-width', st.failed > 0 ? 3 : 1)
        node.data('label', `${site.name}\n${st.impaired}/${st.total} impaired`)
      } else if (kind === 'core') {
        const allIds = Object.values(sites).flatMap(s => s.device_ids)
        node.style('background-color', healthColor(siteStats(allIds, devices)))
      } else {
        const device = devices[node.id()]
        if (device) {
          node.style('background-color', STATE_COLOR[device.state] ?? c.down)
          node.data('state', device.state)
        }
      }
    })
  }, [devices, sites])

  const zoomBy = (factor: number) => {
    const cy = cyRef.current
    if (!cy) return
    cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } })
  }

  const fitView = () => cyRef.current?.fit(undefined, 40)

  const selectedSite = selectedSiteId ? sites[selectedSiteId] : null

  return (
    // transparent so the body's blueprint grid shows behind the graph —
    // a network diagram on graph paper
    <div style={{ position: 'relative', width: '100%', height: '100%', background: 'transparent' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Breadcrumb / scope */}
      <div style={{
        position: 'absolute', top: 10, left: 10,
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'rgba(15,21,32,0.9)',
        border: `1px solid ${c.line}`,
        borderRadius: radius.md,
        padding: '6px 11px',
        backdropFilter: 'blur(4px)',
        fontSize: 12,
      }}>
        {siteMode ? (
          <span style={{ color: c.dim }}>
            <span style={{ color: c.text, fontWeight: 600 }}>All sites</span>
            <span style={{ color: c.faint, marginLeft: 8, fontSize: 11 }}>· tap a site to drill in</span>
          </span>
        ) : (
          <>
            <button
              onClick={() => onSiteSelect(null)}
              style={{
                background: 'transparent', border: 'none', color: c.accent,
                cursor: 'pointer', fontSize: 12, padding: 0, fontWeight: 600,
              }}
            >
              ← All sites
            </button>
            <span style={{ color: c.faint }}>/</span>
            <span style={{ color: c.text, fontWeight: 600 }}>{selectedSite?.name ?? selectedSiteId}</span>
          </>
        )}
      </div>

      {/* Zoom controls */}
      <div style={{
        position: 'absolute', bottom: 12, right: 12,
        display: 'flex', flexDirection: 'column', gap: 6, zIndex: 10,
      }}>
        <ZoomButton label="+" onClick={() => zoomBy(1.3)} />
        <ZoomButton label="−" onClick={() => zoomBy(1 / 1.3)} />
        <ZoomButton label="⤢" onClick={fitView} title="Fit to view" />
      </div>

      {/* Legend */}
      <div style={{
        position: 'absolute', top: 10, right: 10,
        background: 'rgba(15,21,32,0.9)',
        border: `1px solid ${c.line}`,
        borderRadius: radius.md,
        padding: '9px 12px',
        fontSize: 11,
        color: c.dim,
        fontFamily: font.sans,
        backdropFilter: 'blur(4px)',
      }}>
        {siteMode ? (
          <>
            <LegendRow color={c.ok} label="Healthy site" />
            <LegendRow color={c.warn} label="Some impaired" />
            <LegendRow color={c.crit} label="Major outage" pulse />
            <div style={{ marginTop: 6, fontSize: 10, color: c.faint }}>node size = device count</div>
          </>
        ) : (
          <>
            {Object.entries(STATE_COLOR).map(([state, color]) => (
              <LegendRow key={state} color={color} label={state} pulse={state === 'failed'} cap />
            ))}
            <div style={{ marginTop: 7, borderTop: `1px solid ${c.line}`, paddingTop: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 9, height: 9, border: '2px solid #f97316', borderRadius: 2 }} />
                <span>shadow IT</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function LegendRow({ color, label, pulse, cap }: { color: string; label: string; pulse?: boolean; cap?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
      <Led color={color} size={9} pulse={pulse} />
      <span style={{ textTransform: cap ? 'capitalize' : 'none' }}>{label}</span>
    </div>
  )
}
