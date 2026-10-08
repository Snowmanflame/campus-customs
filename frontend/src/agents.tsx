import type { ReactNode } from 'react'
import type { AgentId, Speaker } from './types'

export interface AgentStyle {
  id: Speaker
  name: string
  callsign: string
  role: string
  color: string
  glyph: ReactNode
}

const g = (d: string) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d={d} fill="currentColor" />
  </svg>
)

// Each agent gets its own colour, glyph, and voice on the board.
export const AGENTS: Record<Speaker, AgentStyle> = {
  boss: {
    id: 'boss', name: 'Boss', callsign: 'COMMAND', role: 'Routes tickets · final call', color: '#ffd23f',
    glyph: g('M3 18h18l-1.5-9-4.5 4-3-7-3 7-4.5-4L3 18zm0 2h18v2H3v-2z'),
  },
  inventory: {
    id: 'inventory', name: 'Inventory', callsign: 'CARGO', role: 'Stock · shortfalls · restock', color: '#38e1ff',
    glyph: g('M12 2 3 6.5v11L12 22l9-4.5v-11L12 2zm0 2.3 6.3 3.2L12 10.7 5.7 7.5 12 4.3zM5 9.2l6 3v7.4l-6-3V9.2zm8 10.4v-7.4l6-3v7.4l-6 3z'),
  },
  accounting: {
    id: 'accounting', name: 'Accounting', callsign: 'CREDITS', role: 'Cash · invoices · margins', color: '#53ff8a',
    glyph: g('M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15.9V19h-2v-1.1c-1.7-.3-3-1.4-3.1-3h2c.1.8.8 1.4 2.1 1.4 1.4 0 1.9-.6 1.9-1.2 0-.8-.6-1.1-2.3-1.5-1.9-.4-3.4-1.1-3.4-3 0-1.4 1.1-2.5 2.8-2.9V6.6h2v1.1c1.6.4 2.5 1.6 2.6 2.9h-2c-.1-.8-.6-1.3-1.8-1.3-1.1 0-1.7.5-1.7 1.1 0 .7.7.9 2.3 1.3 2 .5 3.4 1.2 3.4 3.1 0 1.5-1.1 2.6-2.8 3.1z'),
  },
  facilities: {
    id: 'facilities', name: 'Facilities', callsign: 'DOCKMASTER', role: 'Lease · rent · the shop space', color: '#ff8a3d',
    glyph: g('M4 22V8l5-3v3l5-3v3l6-4v18H4zm3-3h2v-3H7v3zm0-5h2v-3H7v3zm4 5h2v-3h-2v3zm0-5h2v-3h-2v3zm4 5h2v-3h-2v3zm0-5h2v-3h-2v3z'),
  },
  customer_service: {
    id: 'customer_service', name: 'Customer Service', callsign: 'COMMS', role: 'Drafts customer messages', color: '#ff4fd8',
    glyph: g('M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2zm3 5v2h2V9H7zm4 0v2h2V9h-2zm4 0v2h2V9h-2z'),
  },
  human: {
    id: 'human', name: 'Human', callsign: 'OPERATOR', role: 'Approves payments', color: '#ff5a5a',
    glyph: g('M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10zm0 2c-4.4 0-8 2.2-8 5v3h16v-3c0-2.8-3.6-5-8-5z'),
  },
}

export const TEAM: AgentId[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const STATUS_LABEL: Record<string, string> = {
  open: 'OPEN',
  in_progress: 'IN PROGRESS',
  waiting_approval: 'AWAITING APPROVAL',
  waiting_vendor: 'AWAITING VENDOR',
  waiting_customer: 'AWAITING CUSTOMER',
  resolved: 'RESOLVED',
  closed: 'CLOSED',
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
