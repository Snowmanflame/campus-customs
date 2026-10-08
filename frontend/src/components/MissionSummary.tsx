import { AGENTS, STATUS_LABEL } from '../agents'
import type { Ticket } from '../types'

/** Short debrief of what the team did on a ticket, from the Boss's final decision. */
export default function MissionSummary({ ticket }: { ticket: Ticket }) {
  const d = ticket.last_decision

  if (ticket.state === 'running') {
    return <div className="debrief debrief--empty">The team is working this ticket. Debrief appears when the Boss signs off.</div>
  }
  if (!d) {
    return (
      <div className="debrief debrief--empty">
        {ticket.last_error
          ? <>Last run failed: <code>{ticket.last_error}</code></>
          : ticket.last_note
            ? <>Last note on file: {ticket.last_note}</>
            : 'Not worked yet. Pull LAUNCH to send the team in.'}
      </div>
    )
  }
  return (
    <div className="debrief">
      <div className="debrief__head">
        <span className="debrief__stamp">RESOLVED BY TEAM</span>
        <span className="chip chip--status">{STATUS_LABEL[d.final_status] ?? d.final_status}</span>
        <span className="debrief__crew">
          {d.assigned_to.map(a => (
            <span key={a} className="crew" style={{ ['--c' as string]: AGENTS[a]?.color ?? '#fff' }}>
              {AGENTS[a]?.callsign ?? a}
            </span>
          ))}
        </span>
      </div>
      <p className="debrief__decision">{d.decision}</p>
      <div className="debrief__cols">
        <div>
          <h4>Findings</h4>
          <ul>{d.findings.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
        <div>
          <h4>Actions</h4>
          <ul>{d.actions_taken.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      </div>
      <p className="debrief__next"><b>NEXT ▸</b> {d.next_step}</p>
    </div>
  )
}
