import cytoscape, { Core, ElementDefinition } from 'cytoscape'
import { useEffect, useRef } from 'react'
import { Device, DeviceCategory, DeviceState, TopologyData } from '../types'

// Color by state
const STATE_COLOR: Record<DeviceState, string> = {
  healthy: '#22c55e',
  degraded: '#f59e0b',
  failed: '#ef4444',
  unreachable: '#6b7280',
  recovering: '#a855f7',
  rebooting: '#3b82f6',
  maintenance: '#64748b',
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

function ZoomButton({ label, onClick, title }: { label: string; onClick: () => void; title?: string }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        width: 32, height: 32,
        background: 'rgba(17,24,39,0.9)',
        border: '1px solid #374151',
        borderRadius: 6,
        color: '#d1d5db',
        fontSize: 18,
        lineHeight: 1,
        cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      {label}
    </button>
  )
}

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
        label: `${node.label}\n${badge}`,
        category: node.category,
        state: node.state,
        vendor,
        site_id: node.site_id,
        is_consumer: isConsumer,
      },
      style: {
        'background-color': STATE_COLOR[node.state as DeviceState] ?? '#6b7280',
        'shape': CATEGORY_SHAPE[node.category as DeviceCategory] ?? 'ellipse',
        'border-color': isConsumer ? '#f97316' : '#374151',
        'border-width': isConsumer ? 3 : 1,
      },
    })
  }

  for (const edge of topology.edges) {
    elements.push({
      group: 'edges',
      data: {
        id: `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
      },
    })
  }

  return elements
}

interface Props {
  topology: TopologyData | null
  devices: Record<string, Device>
  selectedSiteId: string | null
  onDeviceClick: (deviceId: string) => void
  isMobile?: boolean
}

// Scale UI up on large / high-DPI displays so a 4K canvas isn't full of
// tiny nodes. 1.0 at ~1800px logical width, capped at 2.2 for very wide displays.
function computeUiScale(isMobile: boolean): number {
  if (isMobile) return 1
  if (typeof window === 'undefined') return 1
  return Math.min(2.2, Math.max(1, window.innerWidth / 1800))
}

export function TopologyView({ topology, devices, selectedSiteId, onDeviceClick, isMobile = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  useEffect(() => {
    if (!containerRef.current || !topology) return

    const filteredTopology = selectedSiteId
      ? {
          nodes: topology.nodes.filter(n => n.site_id === selectedSiteId),
          edges: topology.edges.filter(e => {
            const srcNode = topology.nodes.find(n => n.id === e.source)
            const tgtNode = topology.nodes.find(n => n.id === e.target)
            return srcNode?.site_id === selectedSiteId && tgtNode?.site_id === selectedSiteId
          }),
        }
      : topology

    const elements = buildElements(filteredTopology, devices)

    if (cyRef.current) {
      cyRef.current.destroy()
    }

    const uiScale = computeUiScale(isMobile)
    const nodeSize = Math.round((isMobile ? 44 : 34) * uiScale)
    const fontSize = `${Math.round((isMobile ? 11 : 10) * uiScale)}px`

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
            'color': '#d1d5db',
            'font-size': fontSize,
            'font-family': 'Courier New, monospace',
            'text-wrap': 'wrap',
            'text-max-width': `${Math.round((isMobile ? 100 : 90) * uiScale)}px`,
            'text-margin-y': Math.round((isMobile ? 6 : 4) * uiScale),
          },
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#374151',
            'width': 1.5 * uiScale,
            'target-arrow-shape': 'none',
            'curve-style': 'bezier',
            'opacity': 0.7,
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#f9fafb',
            'border-width': 3,
            'width': nodeSize * 1.25,
            'height': nodeSize * 1.25,
          },
        },
        {
          selector: 'node[state="failed"]',
          style: { 'border-color': '#ef4444', 'border-width': 2 },
        },
        {
          selector: 'node[state="unreachable"]',
          style: { 'opacity': 0.5 },
        },
      ],
      layout: {
        name: 'breadthfirst',
        directed: true,
        padding: 20,
        spacingFactor: 1.4 * uiScale,
        avoidOverlap: true,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      wheelSensitivity: 0.3,
      minZoom: 0.1,
      maxZoom: 4,
      touchTapThreshold: 8,
      desktopTapThreshold: 4,
    })

    // Once the layout settles, fit the graph to fill the canvas so a narrow
    // tree doesn't leave most of a wide 4K viewport empty.
    cy.one('layoutstop', () => cy.fit(undefined, Math.round(40 * uiScale)))

    cy.on('tap', 'node', (evt) => {
      onDeviceClick(evt.target.id())
    })

    cyRef.current = cy

    // Keep the graph filling the canvas when the window is resized.
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
  }, [topology, selectedSiteId]) // eslint-disable-line react-hooks/exhaustive-deps

  // Live-update node colors without full re-render
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().forEach(node => {
      const device = devices[node.id()]
      if (device) {
        node.style('background-color', STATE_COLOR[device.state] ?? '#6b7280')
        node.data('state', device.state)
      }
    })
  }, [devices])

  const zoomBy = (factor: number) => {
    const cy = cyRef.current
    if (!cy) return
    cy.zoom({ level: cy.zoom() * factor, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } })
  }

  const fitView = () => {
    const cy = cyRef.current
    if (!cy) return
    cy.fit(undefined, 40)
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: '#111827' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Zoom controls */}
      <div style={{
        position: 'absolute', bottom: 12, right: 12,
        display: 'flex', flexDirection: 'column', gap: 6, zIndex: 10,
      }}>
        <ZoomButton label="+" onClick={() => zoomBy(1.3)} />
        <ZoomButton label="−" onClick={() => zoomBy(1 / 1.3)} />
        <ZoomButton label="⤢" onClick={fitView} title="Fit to view" />
      </div>

      <div style={{
        position: 'absolute', top: 8, right: 8,
        background: 'rgba(17,24,39,0.9)',
        border: '1px solid #374151',
        borderRadius: 6,
        padding: '8px 12px',
        fontSize: 11,
        color: '#9ca3af',
      }}>
        {Object.entries(STATE_COLOR).map(([state, color]) => (
          <div key={state} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
            <span>{state}</span>
          </div>
        ))}
        <div style={{ marginTop: 6, borderTop: '1px solid #374151', paddingTop: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, border: '2px solid #f97316', borderRadius: 2 }} />
            <span>shadow IT</span>
          </div>
        </div>
      </div>
    </div>
  )
}
