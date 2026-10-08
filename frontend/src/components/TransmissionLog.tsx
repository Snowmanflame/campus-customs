import { useEffect, useRef, useState } from 'react'
import { AGENTS } from '../agents'
import type { AgentEvent } from '../types'

const ICON: Record<string, string> = {
  run_started: '◉', delegation: '➤', delegation_result: '◀', delegation_refused: '⊘',
  tool_call: '⚙', tool_result: '↳', run_finished: '★', error: '⚠',
  payment_approved: '✔', purchase_order_approved: '✔', payment_rejected: '✖',
}

function line(e: AgentEvent): string {
  if (e.kind === 'delegation' && typeof e.data.request === 'string') {
    const target = String(e.data.target ?? '').replace('_', ' ').toUpperCase()
    return `asks ${target}: ${e.data.request}`
  }
  if (e.kind === 'delegation_result') {
    const r = e.data.report as { summary?: string } | undefined
    return `reports: ${r?.summary ?? e.detail}`
  }
  return e.detail
}

/** Scrolling transmission log for the selected ticket. Telemetry (tool calls/results) can be hidden. */
export default function TransmissionLog({ events }: { events: AgentEvent[] }) {
  const [telemetry, setTelemetry] = useState(true)
  const box = useRef<HTMLDivElement>(null)
  const shown = telemetry ? events : events.filter(e => e.kind !== 'tool_call' && e.kind !== 'tool_result')

  useEffect(() => {
    const el = box.current
    if (el) el.scrollTop = el.scrollHeight
  }, [shown.length])

  return (
    <div className="log">
      <div className="log__bar">
        <span>TRANSMISSION LOG</span>
        <label className="toggle">
          <input type="checkbox" checked={telemetry} onChange={e => setTelemetry(e.target.checked)} />
          <span>tool telemetry</span>
        </label>
      </div>
      <div className="log__body" ref={box}>
        {shown.length === 0 && <div className="log__empty">No transmissions yet for this ticket.</div>}
        {shown.map(e => {
          const a = AGENTS[e.agent] ?? AGENTS.human
          const tele = e.kind === 'tool_call' || e.kind === 'tool_result'
          return (
            <div key={e.id} className={`tx tx--${e.kind} ${tele ? 'tx--tele' : ''}`} style={{ ['--c' as string]: a.color }}>
              <span className="tx__time">{new Date(e.at).toLocaleTimeString([], { hour12: false })}</span>
              <span className="tx__who">{a.callsign}</span>
              <span className="tx__icon">{ICON[e.kind] ?? '•'}</span>
              <span className="tx__text">{line(e)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
