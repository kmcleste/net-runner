import { useState } from 'react'
import { AlertConsole } from './components/AlertConsole'
import { BottomNav } from './components/BottomNav'
import { BottomSheet } from './components/BottomSheet'
import { ChaosPanel } from './components/ChaosPanel'
import { ChoroplethView } from './components/ChoroplethView'
import { Dashboard } from './components/Dashboard'
import { DevicePanel } from './components/DevicePanel'
import { TopologyView } from './components/TopologyView'
import { useIsMobile } from './hooks/useIsMobile'
import { useSimulation } from './hooks/useSimulation'
import { APICallResult } from './types'
import { c, font, radius, tint } from './theme'

type MobileTab = 'topology' | 'geo' | 'alerts' | 'chaos'
type DesktopView = 'topology' | 'geo'

export default function App() {
  const sim = useSimulation()
  const isMobile = useIsMobile()
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  const [selectedSiteId, setSelectedSiteId] = useState<string | null>(null)
  const [mobileTab, setMobileTab] = useState<MobileTab>('topology')
  const [desktopView, setDesktopView] = useState<DesktopView>('topology')

  const selectedDevice = selectedDeviceId ? sim.devices[selectedDeviceId] ?? null : null

  const handleApiCall = async (deviceId: string, action: string): Promise<APICallResult> =>
    sim.callDeviceAPI(deviceId, action)

  const handleDeviceClick = (id: string) => {
    setSelectedDeviceId(id === selectedDeviceId ? null : id)
    if (isMobile) setMobileTab('topology')
  }

  // When a site is selected from the choropleth, switch to topology and drill in
  const handleGeoSiteSelect = (siteId: string | null) => {
    setSelectedSiteId(siteId)
    if (isMobile && siteId) setMobileTab('topology')
  }

  if (sim.loading) {
    return (
      <div style={loadingStyle}>
        <div style={{ fontSize: 30, color: c.accent, textShadow: `0 0 16px ${c.accent}aa` }}>◈</div>
        <div style={{ fontSize: 15, color: c.text, letterSpacing: 3, fontWeight: 600 }}>net&#8209;runner</div>
        <div style={{ fontSize: 11, color: c.faint, marginTop: 4 }}>linking to sim engine…</div>
        <style>{`@keyframes slide { from{left:-40%} to{left:100%} }`}</style>
        <div style={{ width: 180, height: 2, background: c.line, borderRadius: 2, overflow: 'hidden', position: 'relative', marginTop: 18 }}>
          <div style={{ position: 'absolute', width: '40%', height: '100%', background: c.accent, boxShadow: `0 0 10px ${c.accent}`, animation: 'slide 1.5s infinite' }} />
        </div>
      </div>
    )
  }

  // -----------------------------------------------------------------------
  // Mobile layout — full-screen tabs + bottom nav + bottom sheet for devices
  // -----------------------------------------------------------------------
  if (isMobile) {
    return (
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'transparent', fontFamily: font.sans, overflow: 'hidden' }}>
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
              sites={sim.sites}
              selectedSiteId={selectedSiteId}
              onDeviceClick={handleDeviceClick}
              onSiteSelect={setSelectedSiteId}
              isMobile
            />
          </div>

          {mobileTab === 'geo' && (
            <div style={{ position: 'absolute', inset: 0 }}>
              <ChoroplethView
                sites={sim.sites}
                devices={sim.devices}
                selectedSiteId={selectedSiteId}
                onSiteSelect={handleGeoSiteSelect}
                isMobile
              />
            </div>
          )}

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
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'transparent', fontFamily: font.sans }}>
      <Dashboard
        summary={sim.summary}
        sites={sim.sites}
        selectedSiteId={selectedSiteId}
        onSiteChange={setSelectedSiteId}
        onSimControl={sim.simControl}
        isMobile={false}
      />

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* View toggle — Topology / Geo */}
        <div style={{
          position: 'absolute', top: 12, right: selectedDevice ? 380 : 340, zIndex: 20,
          display: 'flex', gap: 1, background: c.panel, border: `1px solid ${c.line}`, borderRadius: radius.md,
        }}>
          <ViewToggle
            label="◈ Topo"
            active={desktopView === 'topology'}
            onClick={() => setDesktopView('topology')}
          />
          <ViewToggle
            label="◎ Geo"
            active={desktopView === 'geo'}
            onClick={() => setDesktopView('geo')}
            accentColor={c.human}
          />
        </div>

        <div style={{ flex: 1, overflow: 'hidden', position: 'relative' }}>
          {/* Topology — always mounted to keep Cytoscape alive */}
          <div style={{ position: 'absolute', inset: 0, display: desktopView === 'topology' ? 'block' : 'none' }}>
            <TopologyView
              topology={sim.topology}
              devices={sim.devices}
              sites={sim.sites}
              selectedSiteId={selectedSiteId}
              onDeviceClick={handleDeviceClick}
              onSiteSelect={setSelectedSiteId}
            />
          </div>

          {desktopView === 'geo' && (
            <div style={{ position: 'absolute', inset: 0 }}>
              <ChoroplethView
                sites={sim.sites}
                devices={sim.devices}
                selectedSiteId={selectedSiteId}
                onSiteSelect={handleGeoSiteSelect}
              />
            </div>
          )}
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

function ViewToggle({
  label, active, onClick, accentColor = c.accent,
}: {
  label: string
  active: boolean
  onClick: () => void
  accentColor?: string
}) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? tint(accentColor, 0.14) : 'transparent',
        border: 'none',
        borderRadius: radius.sm,
        color: active ? accentColor : c.faint,
        fontSize: 11,
        fontWeight: active ? 700 : 500,
        fontFamily: font.sans,
        padding: '6px 12px',
        cursor: 'pointer',
        letterSpacing: 0.5,
        transition: 'all 0.15s',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )
}

function DisconnectBanner() {
  return (
    <div style={{
      position: 'fixed', top: 66, left: '50%', transform: 'translateX(-50%)',
      background: c.panel, border: `1px solid ${c.crit}`, borderRadius: 7,
      padding: '7px 14px', fontSize: 11, color: c.crit, zIndex: 300,
      display: 'flex', alignItems: 'center', gap: 7,
      boxShadow: `0 8px 24px rgba(0,0,0,0.5)`,
    }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%', background: c.crit,
        boxShadow: `0 0 8px ${c.crit}`,
      }} className="led-pulse" />
      Link down — reconnecting…
    </div>
  )
}

const loadingStyle: React.CSSProperties = {
  height: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'transparent',
  fontFamily: font.sans,
  color: c.text,
  flexDirection: 'column',
  gap: 4,
}
