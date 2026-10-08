import { useState } from 'react'
import { money } from '../agents'
import type { PaymentApproval, PurchaseOrder } from '../types'

interface Props {
  payments: PaymentApproval[]
  purchaseOrders: PurchaseOrder[]
  selectedId: number | null
  operator: string
  onOperator: (name: string) => void
  onApprove: (kind: 'payment' | 'purchase_order', id: number) => Promise<void>
  onReject: (id: number) => Promise<void>
}

/** Where the human signs off. Agents only queue requests; nothing moves until a flipper is hit here. */
export default function ApprovalConsole(p: Props) {
  const [busy, setBusy] = useState<string | null>(null)
  const empty = p.payments.length === 0 && p.purchaseOrders.length === 0
  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key)
    try { await fn() } finally { setBusy(null) }
  }
  const needName = !p.operator.trim()

  return (
    <div className="approvals">
      <label className="operator">
        <span>OPERATOR</span>
        <input
          value={p.operator}
          onChange={e => p.onOperator(e.target.value)}
          placeholder="your name"
          maxLength={40}
        />
      </label>
      {empty && <div className="approvals__empty">No requests waiting. Agents queue payments here for you.</div>}

      {p.payments.map(a => (
        <div key={`p${a.id}`} className={`req ${a.ticket_id === p.selectedId ? 'req--here' : ''}`}>
          <div className="req__top">
            <span className="req__tag">PAYMENT #{a.id}</span>
            <span className="req__ticket">ticket #{a.ticket_id}</span>
          </div>
          <div className="req__amount">{money(a.amount)}</div>
          <div className="req__payee">{a.kind === 'rent' ? 'Rent' : `Invoice ${a.ref_id}`} → {a.payee}</div>
          <p className="req__reason">{a.reason}</p>
          <div className="req__by">requested by {a.requested_by} · from {a.account}</div>
          <div className="flippers">
            <button
              className="flipper flipper--go"
              disabled={needName || busy !== null}
              onClick={() => run(`p${a.id}`, () => p.onApprove('payment', a.id))}
              title={needName ? 'Enter your name first' : 'Approve and pay'}
            >
              {busy === `p${a.id}` ? 'PAYING…' : 'APPROVE & PAY'}
            </button>
            <button
              className="flipper flipper--stop"
              disabled={needName || busy !== null}
              onClick={() => run(`r${a.id}`, () => p.onReject(a.id))}
            >
              REJECT
            </button>
          </div>
        </div>
      ))}

      {p.purchaseOrders.map(po => (
        <div key={`o${po.id}`} className={`req req--po ${po.ticket_id === p.selectedId ? 'req--here' : ''}`}>
          <div className="req__top">
            <span className="req__tag">PURCHASE ORDER #{po.id}</span>
            <span className="req__ticket">ticket #{po.ticket_id}</span>
          </div>
          <div className="req__amount">{po.qty} × {po.sku} {po.size}</div>
          <div className="req__payee">{po.vendor_name} · {money(po.total_cost)} · ETA {po.expected_arrival}</div>
          <div className="req__by">drafted by {po.created_by} · no cash moves on approval</div>
          <div className="flippers">
            <button
              className="flipper flipper--go"
              disabled={needName || busy !== null}
              onClick={() => run(`o${po.id}`, () => p.onApprove('purchase_order', po.id))}
            >
              {busy === `o${po.id}` ? 'APPROVING…' : 'APPROVE PO'}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
