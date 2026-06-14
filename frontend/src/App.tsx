import { useState } from 'react'
import { AlertConsole } from './components/AlertConsole'
import { BottomNav } from './components/BottomNav'
import { BottomSheet } from './components/BottomSheet'
import { ChaosPanel } from './components/ChaosPanel'
import { Dashboard } from './components/Dashboard'
import { DevicePanel } from './components/DevicePanel'
import { TopologyView } from './components/TopologyView'
import { useIsMobile } from './hooks/useIsMobile'
import { useSimulation } from './hooks/useSimulation'
import { APICallResult } from './types'

type MobileTab = 'topology' | 'alerts' | 'chaos'

export default function App() {
  const sim = useSimulation()
  const isMobile = useIsMobile()
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null)
  const [mobileTab, setMobileTab] = useState<MobileTab>('topology')

  const selectedDevice = selectedDeviceId ? sim.devices[selectedDeviceId] ?? null : null

  const handleApiCall = async (deviceId: string, action: string): Promise<APICallResult> =>
    sim.callDeviceAPI(deviceId, action)

  const handleDeviceClick = (id: string) => {
    setSelectedDeviceId(id === selectedDeviceId ? null : id)
    if (isMobile) setMobileTab('topology')  // keep map visible, sheet slides up
  }

  if (sim.loading) {
    return (
      <div style={loadingStyle}>
        <div style={{ fontSize: 28 }}>◈</div>
        <div style={{ fontSize: 14, color: '#22c55e', letterSpacing: 2 }}>net-runner</div>
        <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>connecting to sim engine...</div>
        <style>{`@keyframes slide { from{left:-40%} to{left:100%} }`}</style>
        <div style={{ width: 160, height: 2, background: '#1e293b', borderRadius: 2, overflow: 'hidden', position: 'relative', marginTop: 16 }}>
          <div style={{ position: 'absolute', width: '40%', height: '100%', background: '#22c55e', animation: 'slide 1.5s infinite' }} />
        </div>
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // Mobile layout — full-screen tabs + bottom nav + bottom sheet for devices
  // -----------------------------------------------------------------------
  if (isMobile) {
    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#111827', fontFamily: 'Courier New, monospace', overflow: 'hidden' }}>
        <Dashboard
          summary={sim.summary}
          sites={sim.sites}
          selectedSiteId={selectedSiteId}
          onSiteChange={setSelectedSiteId}
          onSimControl={sim.simControl}
          isMobile
        />

        {/* Tab content */}
        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          {/* Topology always rendered (keeps Cytoscape alive) but hidden when on other tabs */}
          <div style={{ position: 'absolute', inset: 0, display: mobileTab === 'topology' ? 'block' : 'none' }}>
            <TopologyView
              topology={sim.topology}
              devices={sim.devices}
              selectedSiteId={selectedSiteId}
              onDeviceClick={handleDeviceClick}
              isMobile
            />
          </div>

          {mobileTab === 'alerts' && (
            <div style={{ position: 'absolute', inset: 0, overflowY: 'auto' }}>
              <AlertConsole alerts={sim.alerts} onDeviceClick={(id) => { handleDeviceClick(id); setMobileTab('topology') }} />
            </div>
          )}

          {mobileTab === 'chaos' && (
            <div style={{ position: 'absolute', inset: 0, overflowY: 'auto', padding: 12 }}>
              <ChaosPanel
                sites={sim.sites}
                onTriggerPattern={sim.triggerPattern}
                onSetMultiplier={sim.setFailureMultiplier}
                failureMultiplier={sim.summary?.global_failure_multiplier ?? 1.0}
                onChangeSeed={sim.changeSeed}
                currentSeed={sim.summary?.seed ?? 42}
                inline
              />
            </div>
          )}
        </div>

        {/* Bottom nav */}
        <BottomNav
          active={mobileTab}
          onChange={setMobileTab}
          alertCount={sim.alerts.length}
        />

        {/* Device detail — bottom sheet */}
        <BottomSheet
          open={!!selectedDevice}
          onClose={() => setSelectedDeviceId(null)}
          title={selectedDevice ? `${selectedDevice.hostname} — ${selectedDevice.vendor} ${selectedDevice.model}` : ''}
          snapPoints={[65, 90]}
        >
          {selectedDevice && (
            <DevicePanel
              device={selectedDevice}
              onClose={() => setSelectedDeviceId(null)}
              onReboot={sim.rebootDevice}
              onMaintenance={sim.setMaintenance}
              onInjectFailure={sim.injectFailure}
              onApiCall={handleApiCall}
              inline
            />
          )}
        </BottomSheet>

        {!sim.connected && <DisconnectBanner />}
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // Desktop layout — side-by-side panels
  // -----------------------------------------------------------------------
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#111827', fontFamily: 'Courier New, monospace' }}>
      <Dashboard
        summary={sim.summary}
        sites={sim.sites}
        selectedSiteId={selectedSiteId}
        onSiteChange={setSelectedSiteId}
        onSimControl={sim.simControl}
        isMobile={false}
      />

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <TopologyView
            topology={sim.topology}
            devices={sim.devices}
            selectedSiteId={selectedSiteId}
            onDeviceClick={handleDeviceClick}
          />
        </div>

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

        <AlertConsole alerts={sim.alerts} onDeviceClick={handleDeviceClick} />
      </div>

      <ChaosPanel
        sites={sim.sites}
        onTriggerPattern={sim.triggerPattern}
        onSetMultiplier={sim.setFailureMultiplier}
        failureMultiplier={sim.summary?.global_failure_multiplier ?? 1.0}
        onChangeSeed={sim.changeSeed}
        currentSeed={sim.summary?.seed ?? 42}
      />

      {!sim.connected && <DisconnectBanner />}
    </div>
  )
}

function DisconnectBanner() {
  return (
    <div style={{
      position: 'fixed', top: 60, left: '50%', transform: 'translateX(-50%)',
      background: '#450a0a', border: '1px solid #ef4444', borderRadius: 6,
      padding: '6px 14px', fontSize: 11, color: '#fca5a5', zIndex: 300,
    }}>
      ● WebSocket disconnected — reconnecting...
    </div>
  )
}

const loadingStyle: React.CSSProperties = {
  height: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: '#111827',
  fontFamily: 'Courier New, monospace',
  color: '#f9fafb',
  flexDirection: 'column',
  gap: 4,
}
