import type {
  ApprovalsResponse, CashResponse, EventsResponse, TicketsResponse,
} from './types'

/** The FastAPI backend (backend/main.py). Override with VITE_API_BASE in frontend/.env. */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function detailText(body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail: unknown }).detail
    if (typeof d === 'string') return d
    if (d && typeof d === 'object' && 'reason' in d) return String((d as { reason: unknown }).reason)
    return JSON.stringify(d)
  }
  return 'Request failed'
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, detailText(body))
  return body as T
}

export const api = {
  tickets: () => call<TicketsResponse>('/tickets'),
  runTicket: (id: number) => call<{ ticket_id: number; status: string }>(`/tickets/${id}/run`, { method: 'POST' }),
  events: (since: number) => call<EventsResponse>(`/events?since=${since}&limit=1000`),
  approvals: () => call<ApprovalsResponse>('/approvals?status=pending'),
  approve: (kind: 'payment' | 'purchase_order', id: number, approvedBy: string) =>
    call<Record<string, unknown>>('/approve', {
      method: 'POST',
      body: JSON.stringify({ kind, id, approved_by: approvedBy }),
    }),
  reject: (id: number, rejectedBy: string) =>
    call<Record<string, unknown>>('/reject', {
      method: 'POST',
      body: JSON.stringify({ id, rejected_by: rejectedBy, note: 'Rejected on the dashboard' }),
    }),
  cash: () => call<CashResponse>('/cash'),
  reset: () => call<{ reset: boolean; checking_balance: number }>('/reset', { method: 'POST' }),
}
