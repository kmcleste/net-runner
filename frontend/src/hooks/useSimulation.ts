import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Device, Site, TopologyData, WorldSummary, WSMessage } from '../types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''
const API = `${API_BASE}/api`
const WS_URL = import.meta.env.VITE_WS_URL
  ?? `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`

interface SimState {
  summary: WorldSummary | null
  devices: Record<string, Device>
  sites: Record<string, Site>
  topology: TopologyData | null
  alerts: Alert[]
  connected: boolean
  loading: boolean
}

export function useSimulation() {
  const [state, setState] = useState<SimState>({
    summary: null,
    devices: {},
    sites: {},
    topology: null,
    alerts: [],
    connected: false,
    loading: true,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setState(s => ({ ...s, connected: true, loading: false }))
    }

    ws.onmessage = (ev) => {
      const msg: WSMessage = JSON.parse(ev.data)

      if (msg.type === 'world_snapshot') {
        const { summary, devices, sites, topology } = msg.data
        const deviceMap = Object.fromEntries(devices.map(d => [d.id, d]))
        const siteMap = Object.fromEntries(sites.map(s => [s.id, s]))
        setState(prev => ({
          ...prev,
          summary,
          devices: deviceMap,
          sites: siteMap,
          topology,
          loading: false,
        }))
      } else if (msg.type === 'device_update') {
        setState(prev => ({
          ...prev,
          devices: { ...prev.devices, [msg.data.id]: msg.data },
        }))
      } else if (msg.type === 'alert') {
        setState(prev => ({
          ...prev,
          alerts: [msg.data, ...prev.alerts].slice(0, 500),
        }))
      } else if (msg.type === 'tick') {
        setState(prev => ({ ...prev, summary: msg.data }))
      } else if (msg.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }))
      }
    }

    ws.onclose = () => {
      setState(s => ({ ...s, connected: false }))
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const simControl = useCallback(async (action: string, speed?: number) => {
    await fetch(`${API}/sim/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, speed }),
    })
  }, [])

  const injectFailure = useCallback(async (deviceId: string, failureModeId: string) => {
    const res = await fetch(`${API}/chaos/inject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: deviceId, failure_mode_id: failureModeId }),
    })
    return res.json()
  }, [])

  const triggerPattern = useCallback(async (pattern: string, siteId?: string, vendor?: string) => {
    const res = await fetch(`${API}/chaos/pattern`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pattern, site_id: siteId, target_vendor: vendor }),
    })
    return res.json()
  }, [])

  const rebootDevice = useCallback(async (deviceId: string) => {
    await fetch(`${API}/devices/${deviceId}/reboot`, { method: 'POST' })
  }, [])

  const setMaintenance = useCallback(async (deviceId: string, enable: boolean) => {
    await fetch(`${API}/devices/${deviceId}/maintenance?enable=${enable}`, { method: 'POST' })
  }, [])

  const callDeviceAPI = useCallback(async (deviceId: string, action: string) => {
    const res = await fetch(`${API}/devices/${deviceId}/api/${action}`, { method: 'POST' })
    return res.json()
  }, [])

  const setFailureMultiplier = useCallback(async (multiplier: number) => {
    await fetch(`${API}/sim/failure-multiplier?multiplier=${multiplier}`, { method: 'POST' })
  }, [])

  const changeSeed = useCallback(async (seed: number) => {
    await fetch(`${API}/sim/seed/${seed}`, { method: 'POST' })
  }, [])

  return {
    ...state,
    simControl,
    injectFailure,
    triggerPattern,
    rebootDevice,
    setMaintenance,
    callDeviceAPI,
    setFailureMultiplier,
    changeSeed,
  }
}
