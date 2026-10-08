import type { AgentEvent, Speaker } from './types'

/**
 * Pinball-cabinet sound board, synthesized live with the Web Audio API
 * (no audio files). Every agent has its own pitch so you can hear who is
 * working: Boss deepest, Customer Service highest.
 *
 *   delegation         laser zap, pitched to the agent being called
 *   tool_call          bumper "pop" in the calling agent's pitch
 *   delegation_result  rising two-note chime from the reporting agent
 *   run_started        Boss bumper (the plunger itself fires on the LAUNCH click)
 *   run_finished       jackpot arpeggio
 *   payment_approved   coin + score drain
 *   delegation_refused / error   tilt buzzer
 */

const PITCH: Record<Speaker, number> = {
  boss: 196,              // G3 - command voice
  facilities: 262,        // C4
  inventory: 330,         // E4
  accounting: 392,        // G4
  customer_service: 523,  // C5
  human: 440,
}

type Wave = OscillatorType

class SoundBoard {
  private ctx: AudioContext | null = null
  private out: GainNode | null = null
  enabled = true

  /** Browsers only allow audio after a user gesture; call this from a click. */
  unlock() {
    if (!this.ctx) {
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
      if (!Ctx) return
      this.ctx = new Ctx()
      const comp = this.ctx.createDynamicsCompressor()
      comp.threshold.value = -18
      comp.ratio.value = 6
      this.out = this.ctx.createGain()
      this.out.gain.value = 0.28
      this.out.connect(comp).connect(this.ctx.destination)
    }
    if (this.ctx.state === 'suspended') void this.ctx.resume()
  }

  private ready(): AudioContext | null {
    if (!this.enabled || !this.ctx || !this.out || this.ctx.state !== 'running') return null
    return this.ctx
  }

  private tone(t0: number, f0: number, f1: number, dur: number, wave: Wave, vol = 0.6, attack = 0.005) {
    const ctx = this.ctx!, o = ctx.createOscillator(), g = ctx.createGain()
    o.type = wave
    o.frequency.setValueAtTime(f0, t0)
    o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t0 + dur)
    g.gain.setValueAtTime(0.0001, t0)
    g.gain.exponentialRampToValueAtTime(vol, t0 + attack)
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
    o.connect(g).connect(this.out!)
    o.start(t0)
    o.stop(t0 + dur + 0.02)
  }

  private noise(t0: number, dur: number, fromHz: number, toHz: number, vol = 0.4) {
    const ctx = this.ctx!
    const buf = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * dur), ctx.sampleRate)
    const data = buf.getChannelData(0)
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
    const src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain()
    src.buffer = buf
    f.type = 'bandpass'
    f.Q.value = 4
    f.frequency.setValueAtTime(fromHz, t0)
    f.frequency.exponentialRampToValueAtTime(toHz, t0 + dur)
    g.gain.setValueAtTime(vol, t0)
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur)
    src.connect(f).connect(g).connect(this.out!)
    src.start(t0)
  }

  // ---------------------------------------------------------------- sound vocabulary

  laser(who: Speaker, t0?: number) {
    const ctx = this.ready(); if (!ctx) return
    const t = t0 ?? ctx.currentTime, p = PITCH[who] * 4
    this.tone(t, p, p / 8, 0.22, 'sawtooth', 0.35)
    this.tone(t + 0.01, p * 1.5, p / 6, 0.18, 'square', 0.15)
  }

  bumper(who: Speaker, t0?: number) {
    const ctx = this.ready(); if (!ctx) return
    const t = t0 ?? ctx.currentTime, p = PITCH[who] * 2
    this.tone(t, p, p * 0.55, 0.09, 'square', 0.35)
    this.noise(t, 0.04, 3000, 1500, 0.18)
  }

  chime(who: Speaker, t0?: number) {
    const ctx = this.ready(); if (!ctx) return
    const t = t0 ?? ctx.currentTime, p = PITCH[who] * 2
    this.tone(t, p, p, 0.14, 'triangle', 0.45)
    this.tone(t + 0.09, p * 1.5, p * 1.5, 0.22, 'triangle', 0.45)
  }

  plunger(t0?: number) {
    const ctx = this.ready(); if (!ctx) return
    const t = t0 ?? ctx.currentTime
    this.noise(t, 0.35, 200, 4000, 0.5)
    this.tone(t + 0.05, 120, 900, 0.4, 'sawtooth', 0.25, 0.05)
    this.tone(t + 0.42, 880, 1760, 0.12, 'square', 0.25)
  }

  jackpot(t0?: number) {
    const ctx = this.ready(); if (!ctx) return
    const t = t0 ?? ctx.currentTime
    ;[523, 659, 784, 1047, 1319, 1568].forEach((f, i) => this.tone(t + i * 0.07, f, f, 0.16, 'square', 0.28))
    this.tone(t + 0.45, 2093, 2093, 0.4, 'triangle', 0.3)
  }

  coin(t0?: number) {
    const ctx = this.ready(); if (!ctx) return
    const t = t0 ?? ctx.currentTime
    this.tone(t, 988, 988, 0.08, 'square', 0.3)
    this.tone(t + 0.08, 1319, 1319, 0.35, 'square', 0.3)
    for (let i = 0; i < 6; i++) this.tone(t + 0.45 + i * 0.06, 700 - i * 70, 650 - i * 70, 0.05, 'square', 0.18) // score drain
  }

  tilt(t0?: number) {
    const ctx = this.ready(); if (!ctx) return
    const t = t0 ?? ctx.currentTime
    this.tone(t, 110, 92, 0.45, 'sawtooth', 0.35)
    this.tone(t, 116, 98, 0.45, 'square', 0.2)
  }

  rollover() {
    const ctx = this.ready(); if (!ctx) return
    this.tone(ctx.currentTime, 1760, 2349, 0.06, 'square', 0.18)
  }

  /** Play a batch of new events as a short, staggered sequence (capped so a burst stays musical). */
  events(batch: AgentEvent[]) {
    const ctx = this.ready(); if (!ctx || !batch.length) return
    let t = ctx.currentTime + 0.02
    for (const e of batch.slice(-8)) {
      const who = e.agent
      switch (e.kind) {
        case 'run_started': this.bumper('boss', t); t += 0.12; break
        case 'delegation': {
          const target = typeof e.data.target === 'string' ? (e.data.target as Speaker) : who
          this.laser(target in PITCH ? target : who, t); t += 0.24; break
        }
        case 'tool_call': this.bumper(who, t); t += 0.11; break
        case 'tool_result': break
        case 'delegation_result': this.chime(who, t); t += 0.3; break
        case 'run_finished': this.jackpot(t); t += 0.8; break
        case 'payment_approved': case 'purchase_order_approved': this.coin(t); t += 0.8; break
        case 'delegation_refused': case 'error': case 'payment_rejected': this.tilt(t); t += 0.5; break
      }
    }
  }
}

export const sound = new SoundBoard()
