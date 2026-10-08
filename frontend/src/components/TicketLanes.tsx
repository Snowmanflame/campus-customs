import { STATUS_LABEL } from '../agents'
import type { Ticket } from '../types'

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  onSelect: (id: number) => void
}

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'CUSTOMER ORDER',
  rent_notice: 'RENT NOTICE',
  price_override: 'DISCOUNT REQUEST',
}

/** The three tickets as pinball rollover lanes: amber = open, cyan = team running, green = resolved. */
export default function TicketLanes({ tickets, selectedId, onSelect }: Props) {
  return (
    <div className="lanes">
      {tickets.map(t => {
        const detail = [t.sku, t.size, t.qty ? `×${t.qty}` : null].filter(Boolean).join(' · ')
        return (
          <button
            key={t.id}
            className={`lane lane--${t.state} ${selectedId === t.id ? 'lane--selected' : ''}`}
            onClick={() => onSelect(t.id)}
          >
            <span className="lane__lamp" aria-hidden="true" />
            <span className="lane__body">
              <span className="lane__top">
                <span className="lane__id">#{t.id}</span>
                <span className="lane__type">{TYPE_LABEL[t.type] ?? t.type.toUpperCase()}</span>
              </span>
              <span className="lane__subject">{t.subject}</span>
              <span className="lane__meta">{t.requester}{detail ? ` · ${detail}` : ''}</span>
              <span className="lane__chips">
                <span className={`chip chip--${t.state}`}>
                  {t.state === 'running' ? 'TEAM ON IT' : t.state === 'resolved' ? 'RESOLVED' : 'OPEN'}
                </span>
                {t.state === 'resolved' && t.status !== 'resolved' && (
                  <span className="chip chip--status">{STATUS_LABEL[t.status] ?? t.status}</span>
                )}
                {t.last_error && <span className="chip chip--error">RUN FAILED</span>}
              </span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
