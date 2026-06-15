import { useState } from 'react'
import { AgentThought, RemediationAction, RemediationConfig, RuleDefinition } from '../types'
import { c, font, radius, sevColor, tint } from '../theme'
import { Led } from './Led'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ACTION_LABEL: Record<string, string> = {
  reboot: 'REBOOT',
  maintenance_on: 'MAINT ON',
  maintenance_off: 'MAINT OFF',
  alert: 'ALERT',
}

const STATUS_COLOR: Record<string, string> = {
  pending: c.warn,
  approved: c.accent,
  auto: c.accent,
  rejected: c.faint,
  executing: c.reboot,
  done: c.ok,
  failed: c.crit,
}

const AGENT_LABEL: Record<string, string> = {
  rules: 'RULE',
  ml: 'ML',
  llm: 'LLM',
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface Props {
  actions: RemediationAction[]
  config: RemediationConfig | null
  rules: RuleDefinition[]
  agentThought: AgentThought | null
  agentRunning: boolean
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onUpdateConfig: (patch: Partial<RemediationConfig>) => void
  onToggleRule: (id: string, enabled: boolean) => void
  onTriggerAgent: () => void
  inline?: boolean
}

type Tab = 'actions' | 'agent' | 'rules' | 'config'

export function RemediationPanel({
  actions, config, rules, agentThought, agentRunning,
  onApprove, onReject, onUpdateConfig, onToggleRule, onTriggerAgent,
  inline = false,
}: Props) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<Tab>('actions')

  const pending = actions.filter(a => a.status === 'pending').length

  const content = (
    <PanelContent
      tab={tab} setTab={setTab}
      actions={actions} config={config} rules={rules}
      agentThought={agentThought} agentRunning={agentRunning}
      onApprove={onApprove} onReject={onReject}
      onUpdateConfig={onUpdateConfig} onToggleRule={onToggleRule}
      onTriggerAgent={onTriggerAgent}
    />
  )

  if (inline) return content

  // Desktop floating panel
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        style={{
          position: 'fixed', right: 14, bottom: 14,
          display: 'flex', alignItems: 'center', gap: 7,
          background: tint(c.accent, 0.14),
          border: `1px solid ${c.accent}`,
          borderRadius: radius.lg,
          color: c.accent,
          fontSize: 12, fontWeight: 700,
          padding: '9px 15px',
          cursor: 'pointer', zIndex: 50,
          letterSpacing: 1.5,
          boxShadow: '0 6px 20px rgba(0,0,0,0.4)',
        }}
      >
        <Led color={c.accent} size={9} pulse={pending > 0} />
        REMEDIATION
        {pending > 0 && (
          <span style={{
            background: c.warn, color: c.ink, fontSize: 9, fontWeight: 800,
            borderRadius: 8, padding: '1px 5px', marginLeft: 2,
          }}>
            {pending}
          </span>
        )}
      </button>
    )
  }

  return (
    <div style={{
      position: 'fixed', right: 14, bottom: 14, width: 380,
      background: c.panel, border: `1px solid ${c.line}`,
      borderRadius: radius.lg, zIndex: 50,
      boxShadow: '0 24px 48px rgba(0,0,0,0.7)',
      overflow: 'hidden', display: 'flex', flexDirection: 'column',
      maxHeight: 'min(80vh, 600px)',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '11px 14px',
        background: `linear-gradient(180deg, ${c.raised}, ${c.panel})`,
        borderBottom: `1px solid ${c.line}`,
        flexShrink: 0,
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 700, color: c.accent, letterSpacing: 1.5 }}>
          <Led color={c.accent} size={9} pulse={pending > 0} />
          REMEDIATION ENGINE
          {pending > 0 && (
            <span style={{ background: c.warn, color: c.ink, fontSize: 9, fontWeight: 800, borderRadius: 8, padding: '1px 5px' }}>
              {pending} pending
            </span>
          )}
        </span>
        <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', color: c.faint, cursor: 'pointer', fontSize: 18, lineHeight: 1 }}>
          ×
        </button>
      </div>
      <div style={{ overflowY: 'auto', flex: 1, WebkitOverflowScrolling: 'touch' } as React.CSSProperties}>
        {content}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab content
// ---------------------------------------------------------------------------

interface ContentProps {
  tab: Tab
  setTab: (t: Tab) => void
  actions: RemediationAction[]
  config: RemediationConfig | null
  rules: RuleDefinition[]
  agentThought: AgentThought | null
  agentRunning: boolean
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onUpdateConfig: (patch: Partial<RemediationConfig>) => void
  onToggleRule: (id: string, enabled: boolean) => void
  onTriggerAgent: () => void
}

function PanelContent({
  tab, setTab, actions, config, rules, agentThought, agentRunning,
  onApprove, onReject, onUpdateConfig, onToggleRule, onTriggerAgent,
}: ContentProps) {
  const pending = actions.filter(a => a.status === 'pending').length
  const TABS: { id: Tab; label: string; badge?: number }[] = [
    { id: 'actions', label: 'Actions', badge: pending },
    { id: 'agent', label: 'Agent' },
    { id: 'rules', label: 'Rules' },
    { id: 'config', label: 'Config' },
  ]
  return (
    <div>
      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${c.line}`, background: c.raised }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              flex: 1, padding: '8px 4px', background: 'none',
              border: 'none', borderBottom: `2px solid ${tab === t.id ? c.accent : 'transparent'}`,
              color: tab === t.id ? c.text : c.faint,
              fontSize: 10, fontWeight: tab === t.id ? 700 : 500,
              fontFamily: font.sans, cursor: 'pointer',
              textTransform: 'uppercase', letterSpacing: 0.8,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
            }}
          >
            {t.label}
            {t.badge !== undefined && t.badge > 0 && (
              <span style={{ background: c.warn, color: c.ink, fontSize: 8, fontWeight: 800, borderRadius: 6, padding: '1px 4px' }}>
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      <div style={{ padding: 12 }}>
        {tab === 'actions' && (
          <ActionsTab actions={actions} onApprove={onApprove} onReject={onReject} />
        )}
        {tab === 'agent' && (
          <AgentTab
            thought={agentThought} running={agentRunning}
            config={config} onTrigger={onTriggerAgent}
          />
        )}
        {tab === 'rules' && (
          <RulesTab rules={rules} config={config} onToggle={onToggleRule} />
        )}
        {tab === 'config' && (
          <ConfigTab config={config} onUpdate={onUpdateConfig} />
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Actions tab
// ---------------------------------------------------------------------------

function ActionsTab({ actions, onApprove, onReject }: {
  actions: RemediationAction[]
  onApprove: (id: string) => void
  onReject: (id: string) => void
}) {
  const recent = actions.slice(0, 30)
  if (recent.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '28px 0', color: c.faint, fontSize: 11 }}>
        <Led color={c.ok} size={8} /> No remediation actions yet
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      {recent.map(a => <ActionCard key={a.id} action={a} onApprove={onApprove} onReject={onReject} />)}
    </div>
  )
}

function ActionCard({ action: a, onApprove, onReject }: {
  action: RemediationAction
  onApprove: (id: string) => void
  onReject: (id: string) => void
}) {
  const statusColor = STATUS_COLOR[a.status] ?? c.faint
  const sev = sevColor[a.severity] ?? c.warn
  const isPending = a.status === 'pending'

  return (
    <div style={{
      background: c.raised, border: `1px solid ${c.line}`,
      borderLeft: `3px solid ${sev}`,
      borderRadius: radius.md, padding: '9px 11px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
        <Led color={statusColor} size={7} pulse={isPending} />
        <span style={{ fontSize: 10, fontWeight: 700, color: c.text, flex: 1 }}>
          {a.hostname}
        </span>
        <span style={{
          fontSize: 8, fontWeight: 700, letterSpacing: 0.5,
          color: sev, background: tint(sev, 0.15),
          borderRadius: 3, padding: '2px 5px',
        }}>
          {ACTION_LABEL[a.action_type] ?? a.action_type}
        </span>
        <span style={{
          fontSize: 8, color: c.faint, background: tint(c.faint, 0.1),
          borderRadius: 3, padding: '2px 5px',
        }}>
          {AGENT_LABEL[a.agent_type] ?? a.agent_type}
        </span>
      </div>

      <div style={{ fontSize: 10, color: c.dim, lineHeight: 1.5, marginBottom: 5 }}>
        {a.reason}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 9, color: c.faint }}>
          {a.site_name} · {new Date(a.created_at).toLocaleTimeString()}
        </span>
        {a.result && (
          <span style={{ fontSize: 9, color: a.status === 'failed' ? c.crit : c.ok }}>
            {a.result}
          </span>
        )}
        {!a.result && (
          <span style={{ fontSize: 9, color: statusColor, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            {a.status}
          </span>
        )}
      </div>

      {isPending && (
        <div style={{ display: 'flex', gap: 6, marginTop: 8, paddingTop: 8, borderTop: `1px solid ${c.line}` }}>
          <button
            onClick={() => onApprove(a.id)}
            style={{
              flex: 1, background: tint(c.ok, 0.15), border: `1px solid ${c.ok}`,
              borderRadius: radius.sm, color: c.ok, fontSize: 10, fontWeight: 700,
              padding: '5px 0', cursor: 'pointer',
            }}
          >
            ✓ Approve
          </button>
          <button
            onClick={() => onReject(a.id)}
            style={{
              flex: 1, background: tint(c.crit, 0.12), border: `1px solid ${c.crit}`,
              borderRadius: radius.sm, color: c.crit, fontSize: 10, fontWeight: 700,
              padding: '5px 0', cursor: 'pointer',
            }}
          >
            ✕ Reject
          </button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Agent tab
// ---------------------------------------------------------------------------

function AgentTab({ thought, running, config, onTrigger }: {
  thought: AgentThought | null
  running: boolean
  config: RemediationConfig | null
  onTrigger: () => void
}) {
  const enabled = config?.llm_enabled ?? false
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: c.text }}>NOC Analyst Agent</div>
          <div style={{ fontSize: 10, color: c.faint, marginTop: 2 }}>
            {enabled ? 'Claude-powered root-cause analysis' : 'LLM agent disabled in config'}
          </div>
        </div>
        <button
          onClick={onTrigger}
          disabled={running || !enabled}
          style={{
            background: running ? tint(c.faint, 0.1) : tint(c.human, 0.14),
            border: `1px solid ${running ? c.faint : c.human}`,
            borderRadius: radius.sm,
            color: running ? c.faint : c.human,
            fontSize: 10, fontWeight: 700, padding: '6px 12px',
            cursor: running || !enabled ? 'default' : 'pointer',
            display: 'flex', alignItems: 'center', gap: 6,
            whiteSpace: 'nowrap',
          }}
        >
          {running ? <><Led color={c.human} size={7} pulse /> Analysing…</> : '▶ Analyse now'}
        </button>
      </div>

      {thought ? (
        <div style={{
          background: c.raised, border: `1px solid ${c.line}`,
          borderRadius: radius.md, padding: '11px 12px',
          fontSize: 11, color: c.dim, lineHeight: 1.65,
          fontFamily: font.mono,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          maxHeight: 340, overflowY: 'auto',
        }}>
          {thought.content}
          {!thought.is_complete && (
            <span style={{ display: 'inline-block', width: 8, height: 12, background: c.human, marginLeft: 2, verticalAlign: 'middle', animation: 'led-breathe 0.8s ease-in-out infinite' }} />
          )}
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '24px 0', color: c.faint, fontSize: 11 }}>
          {enabled ? 'No analysis yet — trigger manually or wait for a critical alert.' : 'Enable the LLM agent in Config to use this feature.'}
        </div>
      )}

      {thought?.actions_proposed && thought.actions_proposed.length > 0 && (
        <div style={{ marginTop: 10, fontSize: 10, color: c.dim }}>
          <span style={{ color: c.faint, textTransform: 'uppercase', letterSpacing: 0.8 }}>Actions proposed: </span>
          {thought.actions_proposed.length} — check Actions tab
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Rules tab
// ---------------------------------------------------------------------------

function RulesTab({ rules, config, onToggle }: {
  rules: RuleDefinition[]
  config: RemediationConfig | null
  onToggle: (id: string, enabled: boolean) => void
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      {rules.map(r => {
        const eff = config?.rules_status[r.id] ?? r.enabled
        const sev = sevColor[r.severity] ?? c.warn
        return (
          <div key={r.id} style={{
            background: c.raised, border: `1px solid ${c.line}`,
            borderLeft: `3px solid ${eff ? sev : c.faint}`,
            borderRadius: radius.md, padding: '9px 11px',
            opacity: eff ? 1 : 0.55,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
              <Led color={eff ? sev : c.faint} size={7} />
              <span style={{ fontSize: 11, fontWeight: 600, color: c.text, flex: 1 }}>{r.name}</span>
              <span style={{
                fontSize: 8, color: r.auto_execute ? c.ok : c.warn,
                background: tint(r.auto_execute ? c.ok : c.warn, 0.12),
                borderRadius: 3, padding: '2px 5px', fontWeight: 700, letterSpacing: 0.3,
              }}>
                {r.auto_execute ? 'AUTO' : 'HiL'}
              </span>
              <button
                onClick={() => onToggle(r.id, !eff)}
                style={{
                  background: eff ? tint(c.ok, 0.12) : tint(c.faint, 0.1),
                  border: `1px solid ${eff ? c.ok : c.faint}`,
                  borderRadius: 3, color: eff ? c.ok : c.faint,
                  fontSize: 8, fontWeight: 700, padding: '2px 7px', cursor: 'pointer',
                }}
              >
                {eff ? 'ON' : 'OFF'}
              </button>
            </div>
            <div style={{ fontSize: 9, color: c.faint, lineHeight: 1.5 }}>{r.description}</div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Config tab
// ---------------------------------------------------------------------------

function ConfigTab({ config, onUpdate }: {
  config: RemediationConfig | null
  onUpdate: (patch: Partial<RemediationConfig>) => void
}) {
  if (!config) return <div style={{ color: c.faint, fontSize: 11, textAlign: 'center', padding: 20 }}>Loading…</div>

  const toggles: { key: keyof RemediationConfig; label: string; hint: string }[] = [
    { key: 'human_in_loop', label: 'Global Human-in-the-Loop', hint: 'When ON, all auto_execute actions are treated as pending and require manual approval — overrides individual rule settings.' },
    { key: 'rules_enabled', label: 'Rules engine', hint: 'Evaluate built-in condition→action rules on every sim tick.' },
    { key: 'ml_enabled', label: 'ML risk scoring', hint: 'Compute per-device risk scores (0–100) using rolling metrics and anomaly detection.' },
    { key: 'llm_enabled', label: 'LLM agent', hint: 'Enable the Claude-powered NOC analyst agent (requires ANTHROPIC_API_KEY).' },
    { key: 'llm_auto_trigger', label: 'LLM auto-trigger on critical', hint: 'Automatically wake the LLM agent when a critical alert fires.' },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {toggles.map(({ key, label, hint }) => {
        const val = config[key] as boolean
        return (
          <div key={key}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: c.text }}>{label}</span>
              <button
                onClick={() => onUpdate({ [key]: !val })}
                style={{
                  background: val ? tint(c.ok, 0.14) : tint(c.faint, 0.1),
                  border: `1px solid ${val ? c.ok : c.faint}`,
                  borderRadius: radius.sm, color: val ? c.ok : c.faint,
                  fontSize: 10, fontWeight: 700, padding: '4px 12px', cursor: 'pointer',
                  minWidth: 42, textAlign: 'center',
                }}
              >
                {val ? 'ON' : 'OFF'}
              </button>
            </div>
            <div style={{ fontSize: 9, color: c.faint, lineHeight: 1.5 }}>{hint}</div>
          </div>
        )
      })}
    </div>
  )
}
