import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { API_BASE, ApiError, api } from './api'
import { money } from './agents'
import { deriveTeam } from './teamState'
import { sound } from './sound'
import type { AgentEvent, ApprovalsResponse, Ticket } from './types'
import AgentComms from './components/AgentComms'
import ApprovalConsole from './components/ApprovalConsole'
import CashScore from './components/CashScore'
import CityBackground from './components/CityBackground'
import MissionSummary from './components/MissionSummary'
import Playfield from './components/Playfield'
import TicketLanes from './components/TicketLanes'
import TransmissionLog from './components/TransmissionLog'

type Toast = { id: number; tone: 'ok' | 'bad' | 'info'; text: string }

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [shopToday, setShopToday] = useState<string>('')
  const [runningTicket, setRunningTicket] = useState<number | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [balance, setBalance] = useState<number | null>(null)
  const [approvals, setApprovals] = useState<ApprovalsResponse>({ payments: [], purchase_orders: [], cash_accounts: [] })
  const [online, setOnline] = useState(true)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [operator, setOperator] = useState(() => localStorage.getItem('cc-operator') ?? '')
  const lastId = useRef(0)
  const primed = useRef(false)   // don't replay the backlog as sound on first load
  const [soundOn, setSoundOn] = useState(() => localStorage.getItem('cc-sound') !== 'off')

  useEffect(() => { sound.enabled = soundOn }, [soundOn])
  useEffect(() => {
    const unlock = () => sound.unlock()
    window.addEventListener('pointerdown', unlock)
    return () => window.removeEventListener('pointerdown', unlock)
  }, [])

  const toast = useCallback((tone: Toast['tone'], text: string) => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, tone, text }])
    window.setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 5200)
  }, [])

  const refreshBoard = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()])
      setTickets(t.tickets)
      setShopToday(t.shop_today)
      setRunningTicket(t.running_ticket)
      setBalance(c.balance)
      setApprovals(a)
      setOnline(true)
      setSelectedId(s => s ?? t.tickets[0]?.id ?? null)
    } catch {
      setOnline(false)
    }
  }, [])

  const refreshEvents = useCallback(async () => {
    try {
      const r = await api.events(lastId.current)
      if (r.last_id < lastId.current) {          // backend restarted or reset: start over
        lastId.current = 0
        setEvents([])
        return
      }
      // Two polls can overlap (the loop restarts when a run starts/ends), so only
      // keep events newer than what we already have - never add or play one twice.
      const fresh = r.events.filter(e => e.id > lastId.current)
      if (fresh.length) {
        lastId.current = fresh[fresh.length - 1].id
        setEvents(prev => [...prev, ...fresh.filter(e => !prev.length || e.id > prev[prev.length - 1].id)])
        if (primed.current) sound.events(fresh)
      }
      primed.current = true
    } catch { /* board refresh reports offline */ }
  }, [])

  // Poll fast while the team is working, slower when idle.
  useEffect(() => {
    let alive = true
    const loop = async () => {
      while (alive) {
        await Promise.all([refreshBoard(), refreshEvents()])
        await new Promise(r => setTimeout(r, runningTicket !== null ? 1000 : 3000))
      }
    }
    loop()
    return () => { alive = false }
  }, [refreshBoard, refreshEvents, runningTicket])

  // Toast when a run finishes.
  const prevRunning = useRef<number | null>(null)
  useEffect(() => {
    const was = prevRunning.current
    prevRunning.current = runningTicket
    if (was !== null && runningTicket === null) {
      const t = tickets.find(x => x.id === was)
      if (t?.last_error) toast('bad', `Ticket #${was}: run failed. ${t.last_error}`)
      else toast('ok', `Ticket #${was} resolved by the team.`)
    }
  }, [runningTicket, tickets, toast])

  const selected = tickets.find(t => t.id === selectedId) ?? null
  const ticketEvents = useMemo(() => events.filter(e => e.ticket_id === selectedId), [events, selectedId])
  const running = selected !== null && runningTicket === selected.id
  const worked = !!selected && selected.state === 'resolved'
  const team = useMemo(() => deriveTeam(ticketEvents, running), [ticketEvents, running])
  const pendingTotal = approvals.payments.reduce((s, a) => s + a.amount, 0)

  const launch = async () => {
    if (!selected) return
    sound.unlock()
    sound.plunger()
    try {
      await api.runTicket(selected.id)
      setRunningTicket(selected.id)
      toast('info', `Team launched on ticket #${selected.id}.`)
      refreshBoard()
    } catch (e) {
      sound.tilt()
      toast('bad', e instanceof ApiError ? e.message : 'Backend unreachable.')
    }
  }

  const approve = async (kind: 'payment' | 'purchase_order', id: number) => {
    try {
      const r = await api.approve(kind, id, operator.trim())
      if (kind === 'payment') toast('ok', `Paid ${money(Number(r.amount))}. ${String(r.effect ?? '')}`)
      else toast('ok', `Purchase order #${id} approved.`)
    } catch (e) {
      toast('bad', e instanceof ApiError ? e.message : 'Approval failed.')
    }
    await Promise.all([refreshBoard(), refreshEvents()])
  }

  const reject = async (id: number) => {
    try {
      await api.reject(id, operator.trim())
      toast('info', `Payment #${id} rejected. No money moved.`)
    } catch (e) {
      toast('bad', e instanceof ApiError ? e.message : 'Reject failed.')
    }
    await Promise.all([refreshBoard(), refreshEvents()])
  }

  const reset = async () => {
    if (!window.confirm('NEW GAME: reset the database to its original values and clear the feed?')) return
    try {
      const r = await api.reset()
      lastId.current = 0
      setEvents([])
      toast('info', `Database reset. Checking back to ${money(r.checking_balance)}.`)
    } catch (e) {
      toast('bad', e instanceof ApiError ? e.message : 'Reset failed.')
    }
    refreshBoard()
  }

  const selectTicket = (id: number) => {
    sound.rollover()
    setSelectedId(id)
  }

  const toggleSound = () => {
    const next = !soundOn
    setSoundOn(next)
    localStorage.setItem('cc-sound', next ? 'on' : 'off')
    sound.enabled = next
    sound.unlock()
    if (next) sound.chime('boss')
  }

  const onOperator = (name: string) => {
    setOperator(name)
    localStorage.setItem('cc-operator', name)
  }

  const resolvedCount = tickets.filter(t => t.state === 'resolved').length
  const mission = running
    ? `MISSION ▸ TEAM WORKING TICKET #${selected?.id}`
    : runningTicket !== null
      ? `MISSION ▸ TEAM BUSY ON #${runningTicket}`
      : approvals.payments.length
        ? `MISSION ▸ ${approvals.payments.length} PAYMENT${approvals.payments.length > 1 ? 'S' : ''} AWAIT YOUR APPROVAL`
        : resolvedCount === tickets.length && tickets.length
          ? 'MISSION ▸ ALL TICKETS RESOLVED · JACKPOT'
          : 'MISSION ▸ SELECT A TICKET AND LAUNCH'

  return (
    <>
      <CityBackground />
      <div className="scanlines" aria-hidden="true" />
      <div className="desk">
        <header className="marquee">
          <div className="marquee__logo">
            <span className="marquee__ring" aria-hidden="true" />
            <div>
              <h1>CAMPUS CUSTOMS</h1>
              <p>GALACTIC OPERATIONS DESK · SECTOR NEW HAVEN</p>
            </div>
          </div>
          <div className="marquee__mission">{mission}</div>
          <div className="marquee__meta">
            <span>STARDATE <b>{shopToday || '—'}</b></span>
            <span>RESOLVED <b>{resolvedCount}/{tickets.length || 3}</b></span>
            <button className={`snd ${soundOn ? 'snd--on' : ''}`} onClick={toggleSound} title="Pinball sound effects">
              {soundOn ? '♪ SOUND ON' : '♪ SOUND OFF'}
            </button>
            <span className={online ? 'sig sig--on' : 'sig sig--off'}>{online ? 'LINK OK' : 'NO SIGNAL'}</span>
          </div>
        </header>

        {!online && (
          <div className="offline">
            Can't reach the backend at <code>{API_BASE}</code>. Start it from <code>backend/</code> with{' '}
            <code>uvicorn main:app --reload --port 8000</code>.
          </div>
        )}

        <main className="table">
          <section className="panel panel--lanes">
            <h2 className="panel__title">TICKET LANES</h2>
            <TicketLanes tickets={tickets} selectedId={selectedId} onSelect={selectTicket} />
            <div className="launch">
              <button
                className={`plunger ${running ? 'plunger--live' : ''}`}
                disabled={!selected || runningTicket !== null || !online}
                onClick={launch}
              >
                <span className="plunger__knob" aria-hidden="true" />
                {running ? 'TEAM IN FLIGHT…' : runningTicket !== null ? `BUSY ON #${runningTicket}` : `LAUNCH TEAM ON #${selected?.id ?? '—'}`}
              </button>
              <button className="newgame" onClick={reset} disabled={runningTicket !== null || !online}>NEW GAME · RESET DB</button>
            </div>
          </section>

          <section className="panel panel--field">
            <h2 className="panel__title">
              {selected ? <>TICKET #{selected.id} · {selected.subject.toUpperCase()}</> : 'NO TICKET'}
              {selected && <span className={`lamp lamp--${selected.state}`}>{selected.state === 'running' ? 'IN PLAY' : selected.state.toUpperCase()}</span>}
            </h2>
            {selected?.notes && <p className="ticket-note">“{selected.notes}” · {selected.requester}</p>}
            <Playfield team={team} running={running} worked={worked} />
            <AgentComms team={team} worked={worked} />
          </section>

          <section className="panel panel--side">
            <CashScore balance={balance} pendingTotal={pendingTotal} online={online} />
            <h2 className="panel__title">APPROVAL CONSOLE</h2>
            <ApprovalConsole
              payments={approvals.payments}
              purchaseOrders={approvals.purchase_orders}
              selectedId={selectedId}
              operator={operator}
              onOperator={onOperator}
              onApprove={approve}
              onReject={reject}
            />
          </section>

          <section className="panel panel--debrief">
            <h2 className="panel__title">MISSION DEBRIEF</h2>
            {selected && <MissionSummary ticket={selected} />}
          </section>

          <section className="panel panel--log">
            <TransmissionLog events={ticketEvents} />
          </section>
        </main>
      </div>

      <div className="toasts" role="status">
        {toasts.map(t => <div key={t.id} className={`toast toast--${t.tone}`}>{t.text}</div>)}
      </div>
    </>
  )
}
