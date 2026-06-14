import { ReactNode, useState } from 'react'
import { APICallResult, Device } from '../types'

const STATE_COLOR: Record<string, string> = {
  healthy: '#22c55e',
  degraded: '#f59e0b',
  failed: '#ef4444',
  unreachable: '#6b7280',
  recovering: '#a855f7',
  rebooting: '#3b82f6',
  maintenance: '#64748b',
}

const API_PROTOCOL_COLOR: Record<string, string> = {
  ios_xe_restconf: '#1d4ed8',
  nxos_rest: '#1d4ed8',
  meraki_dashboard: '#059669',
  aruba_central: '#b45309',
  aruba_os_cx: '#92400e',
  netconf_xml: '#7c3aed',
  pan_os_xml: '#dc2626',
  forti_os_rest: '#0369a1',
  dell_redfish: '#475569',
  hpe_redfish: '#64748b',
  snmp_v2c: '#374151',
  snmp_v3: '#374151',
  ssh_cli: '#374151',
  none: '#111827',
}

function Meter({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 10, color: '#9ca3af' }}>{label}</span>
        <span style={{ fontSize: 10, color, fontWeight: 600 }}>{value.toFixed(1)}%</span>
      </div>
      <div style={{ background: '#1e293b', borderRadius: 3, height: 6, overflow: 'hidden' }}>
        <div style={{
          width: `${Math.min(100, value)}%`,
          height: '100%',
          background: value > 90 ? '#ef4444' : value > 70 ? '#f59e0b' : color,
          borderRadius: 3,
          transition: 'width 0.3s',
        }} />
      </div>
    </div>
  )
}

interface Props {
  device: Device | null
  onClose: () => void
  onReboot: (id: string) => void
  onMaintenance: (id: string, enable: boolean) => void
  onInjectFailure: (id: string, failureModeId: string) => void
  onApiCall: (id: string, action: string) => Promise<APICallResult>
  inline?: boolean  // true = renders in flow (inside BottomSheet), false = fixed sidebar
}

export function DevicePanel({ device, onClose, onReboot, onMaintenance, onInjectFailure, onApiCall, inline = false }: Props) {
  const [selectedFailure, setSelectedFailure] = useState('')
  const [apiAction, setApiAction] = useState('get_status')
  const [apiResult, setApiResult] = useState<APICallResult | null>(null)
  const [apiLoading, setApiLoading] = useState(false)

  if (!device) return null

  const stateColor = STATE_COLOR[device.state] ?? '#6b7280'
  const protocolColor = API_PROTOCOL_COLOR[device.api_protocol] ?? '#374151'

  const handleApiCall = async () => {
    setApiLoading(true)
    setApiResult(null)
    try {
      const result = await onApiCall(device.id, apiAction)
      setApiResult(result)
    } finally {
      setApiLoading(false)
    }
  }

  const containerStyle: React.CSSProperties = inline
    ? { display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }
    : { position: 'fixed', right: 310, top: 52, width: 380, bottom: 0, background: '#0f172a', borderLeft: '1px solid #1e293b', borderRight: '1px solid #1e293b', display: 'flex', flexDirection: 'column', zIndex: 100, overflow: 'hidden' }

  return (
    <div style={containerStyle}>
      {/* Header — hidden when inline since BottomSheet renders its own title */}
      {!inline && <div style={{
        padding: '10px 14px',
        borderBottom: '1px solid #1e293b',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#f9fafb' }}>{device.hostname}</div>
          <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 1 }}>
            {device.vendor} {device.product_line} — {device.model}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            color: stateColor,
            border: `1px solid ${stateColor}`,
            borderRadius: 4,
            padding: '2px 8px',
            textTransform: 'uppercase',
          }}>
            {device.state}
          </span>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', fontSize: 16,
          }}>×</button>
        </div>
      </div>}

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 14 }}>

        {/* Location */}
        <Section title="Location">
          <Row label="Site" value={`${device.location.site_name} (${device.location.site_type})`} />
          <Row label="Building" value={device.location.building} />
          <Row label="Floor" value={String(device.location.floor)} />
          {device.location.rack_id && <Row label="Rack" value={`${device.location.rack_id} U${device.location.rack_unit}`} />}
        </Section>

        {/* Device info */}
        <Section title="Device">
          <Row label="Category" value={device.category} />
          <Row label="Firmware" value={device.firmware_version} />
          <Row label="Age" value={`${device.age_years.toFixed(1)} years`} />
          <Row label="IPs" value={device.ip_addresses.join(', ')} />
          <Row label="VLANs" value={device.vlan_ids.join(', ')} />
          {device.is_consumer_grade && (
            <div style={{
              marginTop: 6,
              padding: '4px 8px',
              background: '#431407',
              border: '1px solid #f97316',
              borderRadius: 4,
              fontSize: 10,
              color: '#fed7aa',
            }}>
              ⚠ Consumer-grade / shadow IT device
            </div>
          )}
        </Section>

        {/* API */}
        <Section title="Management API">
          <div style={{
            display: 'inline-block',
            background: protocolColor,
            borderRadius: 4,
            padding: '2px 8px',
            fontSize: 10,
            color: '#f9fafb',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: 0.5,
            marginBottom: 8,
          }}>
            {device.api_protocol.replace(/_/g, ' ')}
          </div>
        </Section>

        {/* Metrics */}
        <Section title="Metrics">
          <Meter value={device.metrics.cpu_utilization} label="CPU" color="#22c55e" />
          <Meter value={device.metrics.memory_utilization} label="Memory" color="#3b82f6" />
          {device.metrics.client_count !== null && (
            <Row label="Clients" value={String(device.metrics.client_count)} />
          )}
          <Row label="Uptime" value={`${device.metrics.uptime_hours.toFixed(1)}h`} />
          <Row label="Errors (24h)" value={String(device.failure_count_24h)} />
        </Section>

        {/* Active failures */}
        {device.active_failure_modes.length > 0 && (
          <Section title="Active Failures">
            {device.active_failure_modes.map(fm => (
              <div key={fm} style={{
                padding: '4px 8px',
                background: '#450a0a',
                border: '1px solid #ef4444',
                borderRadius: 4,
                fontSize: 10,
                color: '#fca5a5',
                marginBottom: 4,
              }}>
                {fm}
                {device.is_manually_failed && (
                  <span style={{ marginLeft: 6, color: '#9ca3af' }}>(manual)</span>
                )}
              </div>
            ))}
          </Section>
        )}

        {/* Actions */}
        <Section title="Actions">
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            <ActionButton
              label="Reboot"
              color="#3b82f6"
              onClick={() => onReboot(device.id)}
            />
            <ActionButton
              label={device.state === 'maintenance' ? 'End Maintenance' : 'Maintenance'}
              color="#64748b"
              onClick={() => onMaintenance(device.id, device.state !== 'maintenance')}
            />
          </div>

          {/* Inject failure */}
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 4 }}>Inject Failure Mode</div>
            <div style={{ display: 'flex', gap: 6 }}>
              <select
                value={selectedFailure}
                onChange={e => setSelectedFailure(e.target.value)}
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
                <option value=''>Select failure mode...</option>
                {device.available_failure_modes.map(fm => (
                  <option key={fm.id} value={fm.id}>
                    [{fm.severity}] {fm.name}
                  </option>
                ))}
              </select>
              <ActionButton
                label="⚡ Inject"
                color="#dc2626"
                onClick={() => {
                  if (selectedFailure) {
                    onInjectFailure(device.id, selectedFailure)
                    setSelectedFailure('')
                  }
                }}
              />
            </div>
            {selectedFailure && (
              <div style={{
                marginTop: 4,
                fontSize: 9,
                color: '#9ca3af',
                lineHeight: 1.4,
              }}>
                {device.available_failure_modes.find(f => f.id === selectedFailure)?.description}
              </div>
            )}
          </div>
        </Section>

        {/* API Simulation */}
        <Section title="API Simulation">
          <div style={{ fontSize: 9, color: '#6b7280', marginBottom: 6 }}>
            Call the vendor API for this device and see the real response schema + integration friction.
          </div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <select
              value={apiAction}
              onChange={e => setApiAction(e.target.value)}
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
              <option value='get_status'>get_status</option>
              <option value='reboot'>reboot</option>
              <option value='get_interfaces'>get_interfaces</option>
              <option value='get_logs'>get_logs</option>
              <option value='get_sessions'>get_sessions</option>
              <option value='get_clients'>get_clients</option>
            </select>
            <ActionButton
              label={apiLoading ? '...' : 'Call'}
              color="#7c3aed"
              onClick={handleApiCall}
            />
          </div>

          {apiResult && (
            <div>
              <div style={{
                display: 'flex',
                gap: 8,
                marginBottom: 6,
                padding: '4px 8px',
                background: apiResult.success ? '#0f4c29' : '#450a0a',
                border: `1px solid ${apiResult.success ? '#22c55e' : '#ef4444'}`,
                borderRadius: 4,
                fontSize: 10,
              }}>
                <span style={{ color: apiResult.success ? '#86efac' : '#fca5a5' }}>
                  {apiResult.success ? '✓ Success' : '✗ Failed'}
                </span>
                <span style={{ color: '#9ca3af' }}>{apiResult.latency_ms.toFixed(0)}ms</span>
                <span style={{ color: '#6b7280' }}>{apiResult.api_protocol}</span>
              </div>
              {apiResult.vendor_quirk_triggered && (
                <div style={{
                  padding: '4px 8px',
                  background: '#422006',
                  border: '1px solid #f59e0b',
                  borderRadius: 4,
                  fontSize: 9,
                  color: '#fde68a',
                  marginBottom: 6,
                  lineHeight: 1.5,
                }}>
                  ⚠ Vendor quirk: {apiResult.vendor_quirk_triggered}
                </div>
              )}
              {apiResult.error && (
                <div style={{
                  fontSize: 10,
                  color: '#fca5a5',
                  marginBottom: 6,
                  padding: '4px 8px',
                  background: '#1c0a0a',
                  borderRadius: 4,
                }}>
                  Error: {apiResult.error}
                </div>
              )}
              <div style={{
                background: '#020617',
                border: '1px solid #1e293b',
                borderRadius: 4,
                padding: 8,
                fontSize: 9,
                color: '#a5f3fc',
                fontFamily: 'Courier New, monospace',
                overflowX: 'auto',
                maxHeight: 200,
                overflowY: 'auto',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}>
                {JSON.stringify(apiResult.response, null, 2)}
              </div>
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        fontSize: 9,
        fontWeight: 700,
        color: '#6b7280',
        textTransform: 'uppercase',
        letterSpacing: 1,
        marginBottom: 8,
        borderBottom: '1px solid #1e293b',
        paddingBottom: 4,
      }}>
        {title}
      </div>
      {children}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
      <span style={{ fontSize: 10, color: '#6b7280' }}>{label}</span>
      <span style={{ fontSize: 10, color: '#d1d5db', textAlign: 'right', maxWidth: '65%', wordBreak: 'break-all' }}>
        {value}
      </span>
    </div>
  )
}

function ActionButton({ label, color, onClick }: { label: string; color: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: color + '22',
        border: `1px solid ${color}`,
        borderRadius: 4,
        color: '#f9fafb',
        fontSize: 10,
        padding: '4px 10px',
        cursor: 'pointer',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )
}
