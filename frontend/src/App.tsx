import { useState } from 'react'
import { AlertConsole } from './components/AlertConsole'
import { ChaosPanel } from './components/ChaosPanel'
import { Dashboard } from './components/Dashboard'
import { DevicePanel } from './components/DevicePanel'
import { TopologyView } from './components/TopologyView'
import { useSimulation } from './hooks/useSimulation'
import { APICallResult } from './types'

export default function App() {
  const sim = useSimulation()
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null)

  const selectedDevice = selectedDeviceId ? sim.devices[selectedDeviceId] ?? null : null

  const handleApiCall = async (deviceId: string, action: string): Promise<APICallResult> => {
    return sim.callDeviceAPI(deviceId, action)
  }

  if (sim.loading) {
    return (
      <div style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#111827',
        fontFamily: 'Courier New, monospace',
        color: '#22c55e',
        fontSize: 14,
        flexDirection: 'column',
        gap: 12,
      }}>
        <div style={{ fontSize: 24 }}>◈ net-runner</div>
        <div style={{ color: '#6b7280' }}>Connecting to simulation engine...</div>
        <div style={{
          width: 200,
          height: 2,
          background: '#1e293b',
          borderRadius: 2,
          overflow: 'hidden',
          position: 'relative',
        }}>
          <div style={{
            position: 'absolute',
            width: '40%',
            height: '100%',
            background: '#22c55e',
            borderRadius: 2,
            animation: 'slide 1.5s infinite',
          }} />
        </div>
        <style>{`@keyframes slide { from { left: -40% } to { left: 100% } }`}</style>
      </div>
    )
  }

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: '#111827',
      fontFamily: 'Courier New, monospace',
    }}>
      {/* Top bar — KPIs + sim controls */}
      <Dashboard
        summary={sim.summary}
        sites={sim.sites}
        selectedSiteId={selectedSiteId}
        onSiteChange={setSelectedSiteId}
        onSimControl={sim.simControl}
      />

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>

        {/* Topology canvas */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <TopologyView
            topology={sim.topology}
            devices={sim.devices}
            selectedSiteId={selectedSiteId}
            onDeviceClick={(id) => setSelectedDeviceId(id === selectedDeviceId ? null : id)}
          />
        </div>

        {/* Device detail panel (slides in from right side) */}
        {selectedDevice && (
          <DevicePanel
            device={selectedDevice}
            onClose={() => setSelectedDeviceId(null)}
            onReboot={sim.rebootDevice}
            onMaintenance={sim.setMaintenance}
            onInjectFailure={sim.injectFailure}
            onApiCall={handleApiCall}
          />
        )}

        {/* Alert console — right sidebar */}
        <AlertConsole
          alerts={sim.alerts}
          onDeviceClick={(id) => setSelectedDeviceId(id)}
        />
      </div>

      {/* Chaos panel — floating bottom-left */}
      <ChaosPanel
        sites={sim.sites}
        onTriggerPattern={sim.triggerPattern}
        onSetMultiplier={sim.setFailureMultiplier}
        failureMultiplier={sim.summary?.global_failure_multiplier ?? 1.0}
        onChangeSeed={sim.changeSeed}
        currentSeed={sim.summary?.seed ?? 42}
      />

      {/* Connection status */}
      {!sim.connected && (
        <div style={{
          position: 'fixed',
          top: 60,
          left: '50%',
          transform: 'translateX(-50%)',
          background: '#450a0a',
          border: '1px solid #ef4444',
          borderRadius: 6,
          padding: '6px 14px',
          fontSize: 11,
          color: '#fca5a5',
          zIndex: 200,
        }}>
          ● WebSocket disconnected — reconnecting...
        </div>
      )}
    </div>
  )
}
