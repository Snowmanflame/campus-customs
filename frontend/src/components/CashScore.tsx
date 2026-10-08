import { useEffect, useRef, useState } from 'react'
import { money } from '../agents'

interface Props {
  balance: number | null
  pendingTotal: number
  online: boolean
}

/** Space Cadet–style LED score panel. The balance counts down when an approved payment lands. */
export default function CashScore({ balance, pendingTotal, online }: Props) {
  const [shown, setShown] = useState<number | null>(balance)
  const [debit, setDebit] = useState<number | null>(null)
  const prev = useRef<number | null>(balance)

  useEffect(() => {
    if (balance === null) return
    const from = prev.current
    prev.current = balance
    if (from === null || from === balance) {
      setShown(balance)
      return
    }
    if (balance < from) {
      setDebit(from - balance)
      window.setTimeout(() => setDebit(null), 3200)
    }
    const start = performance.now()
    const dur = 1400
    let raf = 0
    const tick = (now: number) => {
      const k = Math.min(1, (now - start) / dur)
      const eased = 1 - (1 - k) ** 3
      setShown(from + (balance - from) * eased)
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [balance])

  const projected = balance === null ? null : balance - pendingTotal

  return (
    <div className={`score ${debit ? 'score--debit' : ''}`}>
      <div className="score__label">CHECKING · CREDITS</div>
      <div className="score__led" aria-live="polite">
        {!online ? '— NO SIGNAL —' : shown === null ? '$ - - - -' : money(shown)}
      </div>
      {debit !== null && <div className="score__debit">−{money(debit)}</div>}
      <div className="score__row">
        <span>PENDING APPROVAL</span>
        <b>{money(pendingTotal)}</b>
      </div>
      <div className={`score__row ${projected !== null && projected < 0 ? 'score__row--bad' : ''}`}>
        <span>IF ALL APPROVED</span>
        <b>{projected === null ? '—' : money(projected)}</b>
      </div>
    </div>
  )
}
