import { AGENTS, TEAM } from '../agents'
import type { TeamState } from '../teamState'
import type { AgentId } from '../types'

// Bumper positions on the playfield (percent of width/height).
const POS: Record<AgentId, [number, number]> = {
  boss: [50, 22],
  inventory: [14, 70],
  accounting: [37, 84],
  facilities: [63, 84],
  customer_service: [86, 70],
}

interface Props {
  team: TeamState
  running: boolean
  worked: boolean
}

/** Agents as pinball bumpers. The active one flashes; open delegations light the rails between them. */
export default function Playfield({ team, running, worked }: Props) {
  const isOpen = (a: AgentId, b: AgentId) => team.links.some(([x, y]) => x === a && y === b)
  const wasUsed = (a: AgentId, b: AgentId) => team.usedLinks.some(([x, y]) => (x === a && y === b) || (x === b && y === a))

  // draw a rail between every pair that delegated, plus faint rails Boss -> each specialist
  const pairs: [AgentId, AgentId][] = []
  for (const a of TEAM) for (const b of TEAM) if (a < b && (wasUsed(a, b) || a === 'boss' || b === 'boss')) pairs.push([a, b])

  return (
    <div className={`playfield ${running ? 'playfield--live' : ''}`}>
      <svg className="playfield__rails" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {pairs.map(([a, b]) => {
          const live = isOpen(a, b) || isOpen(b, a)
          const used = wasUsed(a, b)
          const [x1, y1] = POS[a]
          const [x2, y2] = POS[b]
          const color = live ? AGENTS[isOpen(a, b) ? b : a].color : used ? '#8fb8ff' : '#3b4675'
          return (
            <line
              key={a + b}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={color}
              strokeWidth={live ? 0.9 : used ? 0.45 : 0.25}
              strokeDasharray={live ? '2 1.4' : used ? undefined : '0.8 1.6'}
              className={live ? 'rail--live' : ''}
              vectorEffect="non-scaling-stroke"
            />
          )
        })}
      </svg>
      {TEAM.map(id => {
        const a = AGENTS[id]
        const live = team.live[id]
        const active = team.active === id
        const dispatched = live.turns > 0
        const [x, y] = POS[id]
        return (
          <div
            key={id}
            className={`bumper ${active ? 'bumper--active' : ''} ${worked && !dispatched ? 'bumper--idle' : ''}`}
            style={{ left: `${x}%`, top: `${y}%`, ['--c' as string]: a.color }}
          >
            <div className="bumper__ring">
              <div className="bumper__cap">{a.glyph}</div>
            </div>
            <div className="bumper__name">{a.callsign}</div>
          </div>
        )
      })}
      <div className="playfield__title">AGENT PLAYFIELD</div>
    </div>
  )
}
