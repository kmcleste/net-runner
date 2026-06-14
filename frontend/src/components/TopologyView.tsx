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
}

export function TopologyView({ topology, devices, selectedSiteId, onDeviceClick }: Props) {
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

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'width': 32,
            'height': 32,
            'label': 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'color': '#d1d5db',
            'font-size': '9px',
            'font-family': 'Courier New, monospace',
            'text-wrap': 'wrap',
            'text-max-width': '80px',
            'text-margin-y': 4,
          },
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#374151',
            'width': 1.5,
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
            'width': 40,
            'height': 40,
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
        spacingFactor: 1.4,
        avoidOverlap: true,
      },
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      wheelSensitivity: 0.3,
    })

    cy.on('tap', 'node', (evt) => {
      onDeviceClick(evt.target.id())
    })

    cyRef.current = cy

    return () => {
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

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: '#111827' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
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
