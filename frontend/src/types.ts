// Shapes returned by backend/main.py (FastAPI, Problem 7).

export type AgentId = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type Speaker = AgentId | 'human'

export type TicketStatus =
  | 'open' | 'in_progress' | 'waiting_approval' | 'waiting_vendor' | 'waiting_customer' | 'resolved' | 'closed'

export interface BossDecision {
  ticket_id: number
  ticket_type: string
  assigned_to: AgentId[]
  findings: string[]
  actions_taken: string[]
  pending_human_approvals: number[]
  draft_ids: number[]
  purchase_order_ids: number[]
  final_status: TicketStatus
  decision: string
  next_step: string
}

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  notes: string | null
  created_at: string
  last_note: string | null
  state: 'open' | 'running' | 'resolved'
  running: boolean
  last_decision: BossDecision | null
  last_error: string | null
}

export interface TicketsResponse {
  shop_today: string
  running_ticket: number | null
  tickets: Ticket[]
}

export type EventKind =
  | 'run_started' | 'delegation' | 'delegation_result' | 'delegation_refused'
  | 'tool_call' | 'tool_result' | 'run_finished' | 'error'
  | 'payment_approved' | 'purchase_order_approved' | 'payment_rejected'

export interface AgentEvent {
  id: number
  at: string
  ticket_id: number | null
  agent: Speaker
  kind: EventKind
  detail: string
  data: Record<string, unknown>
}

export interface EventsResponse {
  running_ticket: number | null
  last_id: number
  events: AgentEvent[]
}

export interface PaymentApproval {
  id: number
  kind: 'invoice' | 'rent'
  ref_id: number
  ticket_id: number | null
  payee: string
  amount: number
  account: string
  reason: string
  requested_by: string
  status: 'pending' | 'paid' | 'rejected' | 'refused'
  created_on: string
}

export interface PurchaseOrder {
  id: number
  vendor_id: number
  vendor_name: string
  sku: string
  size: string
  qty: number
  unit_cost: number
  total_cost: number
  ticket_id: number | null
  expected_arrival: string
  status: 'draft' | 'approved'
  created_by: string
}

export interface ApprovalsResponse {
  payments: PaymentApproval[]
  purchase_orders: PurchaseOrder[]
  cash_accounts: { name: string; balance: number }[]
}

export interface CashResponse {
  name: string
  balance: number
  date: string
}
