import { AGENTS, TEAM } from '../agents'
import type { TeamState } from '../teamState'

interface Props {
  team: TeamState
  worked: boolean
}

/** One card per agent: what it last said, what it's doing now, and which MCP tools it used. */
export default function AgentComms({ team, worked }: Props) {
  return (
    <div className="comms">
      {TEAM.map(id => {
        const a = AGENTS[id]
        const live = team.live[id]
        const active = team.active === id
        const dispatched = live.turns > 0
        const state = active ? 'ACTIVE' : dispatched ? 'REPORTED' : worked ? 'NOT DISPATCHED' : 'STANDBY'
        return (
          <article
            key={id}
            className={`comm ${active ? 'comm--active' : ''} ${!dispatched ? 'comm--quiet' : ''}`}
            style={{ ['--c' as string]: a.color }}
          >
            <header className="comm__head">
              <span className="comm__glyph">{a.glyph}</span>
              <span className="comm__who">
                <b>{a.name}</b>
                <small>{a.role}</small>
              </span>
              <span className={`comm__state comm__state--${state.split(' ')[0].toLowerCase()}`}>{state}</span>
            </header>
            <p className="comm__said">
              {live.said ?? (worked ? 'Not needed on this ticket.' : 'Awaiting launch.')}
            </p>
            {live.doing && active && <p className="comm__doing">⟢ {live.doing}</p>}
            {live.tools.length > 0 && (
              <div className="comm__tools">
                {live.tools.map(t => <code key={t}>{t}</code>)}
              </div>
            )}
          </article>
        )
      })}
    </div>
  )
}
