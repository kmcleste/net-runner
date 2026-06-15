import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AgentThought,
  RemediationAction,
  RemediationConfig,
  RemediationWSMessage,
  RuleDefinition,
} from '../types'

// Remediation service URL — set VITE_REMEDIATION_URL in env to point at the
// standalone service.  Falls back to localhost:9000 for local dev.
const REM_API = import.meta.env.VITE_REMEDIATION_URL ?? 'http://localhost:9000'
const REM_WS = (() => {
  const u = import.meta.env.VITE_REMEDIATION_WS_URL
  if (u) return u
  return REM_API.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws'
})()

interface RemState {
  actions: RemediationAction[]
  config: RemediationConfig | null
  rules: RuleDefinition[]
  agentThought: AgentThought | null
  agentRunning: boolean
  riskScores: Record<string, number>
  connected: boolean
  sourceUrl: string
}

export function useRemediation() {
  const [state, setState] = useState<RemState>({
    actions: [],
    config: null,
    rules: [],
    agentThought: null,
    agentRunning: false,
    riskScores: {},
    connected: false,
    sourceUrl: '',
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    const ws = new WebSocket(REM_WS)
    wsRef.current = ws

    ws.onopen = () => setState(s => ({ ...s, connected: true }))

    ws.onmessage = (ev) => {
      const msg: RemediationWSMessage = JSON.parse(ev.data)

      if (msg.type === 'snapshot') {
        setState(s => ({
          ...s,
          config: msg.data.config,
          rules: msg.data.rules,
          actions: msg.data.actions,
          riskScores: msg.data.risk_scores,
          sourceUrl: msg.data.source_url,
        }))
      } else if (msg.type === 'action') {
        setState(s => {
          const existing = s.actions.findIndex(a => a.id === msg.data.id)
          if (existing >= 0) {
            const next = [...s.actions]
            next[existing] = msg.data
            return { ...s, actions: next }
          }
          return { ...s, actions: [msg.data, ...s.actions].slice(0, 200) }
        })
      } else if (msg.type === 'ml_scores') {
        setState(s => ({ ...s, riskScores: msg.data }))
      } else if (msg.type === 'agent_thought') {
        setState(s => ({
          ...s,
          agentThought: msg.data,
          agentRunning: !msg.data.is_complete,
        }))
      } else if (msg.type === 'config') {
        setState(s => ({ ...s, config: msg.data }))
      } else if (msg.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }))
      }
    }

    ws.onclose = () => {
      setState(s => ({ ...s, connected: false }))
      reconnectTimer.current = setTimeout(connect, 5000)
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

  const approve = useCallback(async (id: string) => {
    await fetch(`${REM_API}/actions/${id}/approve`, { method: 'POST' })
  }, [])

  const reject = useCallback(async (id: string) => {
    await fetch(`${REM_API}/actions/${id}/reject`, { method: 'POST' })
  }, [])

  const updateConfig = useCallback(async (patch: Partial<RemediationConfig>) => {
    await fetch(`${REM_API}/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
  }, [])

  const toggleRule = useCallback(async (ruleId: string, enabled: boolean) => {
    await fetch(`${REM_API}/rules/${ruleId}/toggle?enabled=${enabled}`, { method: 'POST' })
  }, [])

  const triggerAgent = useCallback(async () => {
    await fetch(`${REM_API}/agent/trigger`, { method: 'POST' })
    setState(s => ({ ...s, agentRunning: true }))
  }, [])

  return {
    ...state,
    approve,
    reject,
    updateConfig,
    toggleRule,
    triggerAgent,
  }
}
