import type { AgentEvent, AgentId } from './types'

export interface AgentLive {
  said: string | null        // last thing the agent said (request it sent, or report it returned)
  doing: string | null       // last MCP tool it called
  tools: string[]            // every MCP tool it used on this ticket, in order of first use
  turns: number              // events attributed to the agent
}

export interface TeamState {
  live: Record<AgentId, AgentLive>
  active: AgentId | null
  links: [AgentId, AgentId][]       // delegations currently open (caller -> callee)
  usedLinks: [AgentId, AgentId][]   // every delegation that happened on this ticket
}

const TEAM: AgentId[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']
const isAgent = (s: unknown): s is AgentId => typeof s === 'string' && (TEAM as string[]).includes(s)
const clip = (s: string, n = 220) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

/** Fold the event feed for one ticket into "who is saying/doing what". */
export function deriveTeam(events: AgentEvent[], running: boolean): TeamState {
  const live = Object.fromEntries(
    TEAM.map(a => [a, { said: null, doing: null, tools: [], turns: 0 } as AgentLive]),
  ) as Record<AgentId, AgentLive>
  let links: [AgentId, AgentId][] = []
  const used: [AgentId, AgentId][] = []
  let active: AgentId | null = null

  for (const e of events) {
    if (!isAgent(e.agent)) continue
    const me = live[e.agent]
    me.turns += 1
    switch (e.kind) {
      case 'run_started':
        me.said = `Picking up ticket #${e.ticket_id}.`
        active = e.agent
        break
      case 'delegation': {
        const target = e.data.target
        const request = typeof e.data.request === 'string' ? e.data.request : e.detail
        if (isAgent(target)) {
          me.said = `▸ ${target.replace('_', ' ').toUpperCase()}: ${clip(request)}`
          links = [...links, [e.agent, target]]
          if (!used.some(([a, b]) => a === e.agent && b === target)) used.push([e.agent, target])
          live[target].said = live[target].said ?? 'Receiving orders…'
          active = target
        }
        break
      }
      case 'delegation_result': {
        const report = e.data.report as { summary?: string } | undefined
        me.said = clip(report?.summary ?? e.detail, 320)
        const idx = links.map(([, b]) => b).lastIndexOf(e.agent)
        if (idx >= 0) {
          active = links[idx][0]
          links = links.filter((_, i) => i !== idx)
        }
        break
      }
      case 'delegation_refused':
        me.said = clip(e.detail)
        break
      case 'tool_call': {
        const tool = typeof e.data.tool === 'string' ? e.data.tool : e.detail.split('(')[0]
        me.doing = clip(e.detail, 140)
        if (!me.tools.includes(tool)) me.tools.push(tool)
        active = e.agent
        break
      }
      case 'run_finished': {
        const d = e.data.decision as { decision?: string } | undefined
        me.said = clip(d?.decision ?? e.detail, 320)
        me.doing = null
        links = []
        active = null
        break
      }
      case 'error':
        me.said = `⚠ ${clip(e.detail)}`
        links = []
        active = null
        break
    }
  }
  return { live, active: running ? active : null, links: running ? links : [], usedLinks: used }
}
