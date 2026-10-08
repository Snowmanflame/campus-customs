import { useEffect, useRef } from 'react'

/**
 * Animated ecumenopolis backdrop: twinkling stars and moons over a dusk sky,
 * three parallax layers of skyscrapers with lit windows and blinking beacons,
 * and lanes of air traffic weaving between the layers.
 * Buildings are pre-rendered once per resize; each frame only blits them and
 * moves stars, beacons, speeders, and the occasional cruiser.
 */

interface Star { x: number; y: number; r: number; phase: number; speed: number }
interface Beacon { x: number; y: number; phase: number; color: string; layer: number }
interface Car { x: number; speed: number; color: string; trail: number }
interface Lane { y: number; depth: number; dir: 1 | -1; cars: Car[]; wobble: number }
interface Cruiser { x: number; y: number; scale: number; speed: number }
interface Meteor { x: number; y: number; vx: number; vy: number; life: number }

const rand = (a: number, b: number) => a + Math.random() * (b - a)
const pick = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)]

const LAYERS = [
  { base: '#1b1f45', edge: 'rgba(160,140,255,0.18)', minH: 0.32, maxH: 0.78, minW: 18, maxW: 60, win: 'rgba(170,190,255,', winP: 0.12, gap: 2 },
  { base: '#0f1230', edge: 'rgba(255,150,110,0.22)', minH: 0.22, maxH: 0.6, minW: 30, maxW: 90, win: 'rgba(255,205,140,', winP: 0.2, gap: 4 },
  { base: '#05060f', edge: 'rgba(255,120,80,0.35)', minH: 0.12, maxH: 0.42, minW: 50, maxW: 140, win: 'rgba(255,225,170,', winP: 0.26, gap: 6 },
]

function renderLayer(w: number, h: number, li: number, beacons: Beacon[]): HTMLCanvasElement {
  const L = LAYERS[li]
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const g = c.getContext('2d')!
  let x = -20
  while (x < w + 20) {
    const bw = rand(L.minW, L.maxW)
    const bh = h * rand(L.minH, L.maxH) * (li === 0 && Math.random() < 0.15 ? 1.18 : 1)
    const top = h - bh
    // tower body with a vertical sheen
    const body = g.createLinearGradient(x, 0, x + bw, 0)
    body.addColorStop(0, L.base)
    body.addColorStop(0.5, shade(L.base, 10))
    body.addColorStop(1, L.base)
    g.fillStyle = body
    g.fillRect(x, top, bw, bh)
    // stepped crown / spire
    const style = Math.random()
    g.fillStyle = L.base
    if (style < 0.35) {
      g.fillRect(x + bw * 0.2, top - bh * 0.06, bw * 0.6, bh * 0.06)
      g.fillRect(x + bw * 0.38, top - bh * 0.12, bw * 0.24, bh * 0.06)
    } else if (style < 0.6) {
      g.beginPath()
      g.moveTo(x, top)
      g.lineTo(x + bw / 2, top - bh * 0.16)
      g.lineTo(x + bw, top)
      g.fill()
    } else if (style < 0.8) {
      g.fillRect(x + bw / 2 - 1.5, top - bh * 0.22, 3, bh * 0.22)
    }
    const spireTop = style < 0.35 ? top - bh * 0.12 : style < 0.6 ? top - bh * 0.16 : style < 0.8 ? top - bh * 0.22 : top
    if (Math.random() < 0.7) beacons.push({ x: x + bw / 2, y: spireTop - 2, phase: rand(0, 6.28), color: Math.random() < 0.8 ? '#ff3b3b' : '#7fd8ff', layer: li })
    // rim light from the sunset haze
    g.fillStyle = L.edge
    g.fillRect(x + bw - 2, top, 2, bh)
    // windows
    const ww = li === 2 ? 4 : li === 1 ? 3 : 2
    const wh = li === 2 ? 3 : 2
    for (let wy = top + 6; wy < h - 4; wy += wh + L.gap) {
      for (let wx = x + 4; wx < x + bw - 4; wx += ww + L.gap) {
        if (Math.random() < L.winP) {
          g.fillStyle = L.win + rand(0.35, 0.95).toFixed(2) + ')'
          g.fillRect(wx, wy, ww, wh)
        }
      }
    }
    // horizontal light bands on some towers
    if (Math.random() < 0.3) {
      g.fillStyle = li === 0 ? 'rgba(120,200,255,0.35)' : 'rgba(255,170,90,0.35)'
      for (let k = 0; k < 3; k++) g.fillRect(x, top + bh * rand(0.1, 0.9), bw, 1)
    }
    x += bw + rand(-6, 10)
  }
  return c
}

function shade(hex: string, amt: number) {
  const n = parseInt(hex.slice(1), 16)
  const r = Math.min(255, (n >> 16) + amt), gg = Math.min(255, ((n >> 8) & 255) + amt), b = Math.min(255, (n & 255) + amt)
  return `rgb(${r},${gg},${b})`
}

export default function CityBackground() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current!
    const ctx = canvas.getContext('2d')!
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let W = 0, H = 0, raf = 0, last = performance.now()
    let layers: HTMLCanvasElement[] = []
    let sky: CanvasGradient
    let stars: Star[] = [], beacons: Beacon[] = [], lanes: Lane[] = [], cruisers: Cruiser[] = []
    let meteor: Meteor | null = null

    const setup = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = window.innerWidth
      H = window.innerHeight
      canvas.width = W * dpr
      canvas.height = H * dpr
      canvas.style.width = W + 'px'
      canvas.style.height = H + 'px'
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

      sky = ctx.createLinearGradient(0, 0, 0, H)
      sky.addColorStop(0, '#02030b')
      sky.addColorStop(0.35, '#0a0d2c')
      sky.addColorStop(0.58, '#2a1652')
      sky.addColorStop(0.76, '#7a2d5e')
      sky.addColorStop(0.9, '#d4603f')
      sky.addColorStop(1, '#f2a65a')

      stars = Array.from({ length: Math.round((W * H) / 3800) }, () => ({
        x: rand(0, W), y: H * 0.62 * Math.random() ** 1.4, r: rand(0.3, 1.5), phase: rand(0, 6.28), speed: rand(0.5, 2.2),
      }))
      beacons = []
      layers = [0, 1, 2].map(i => renderLayer(W, H, i, beacons))

      const colors = ['#fff4d6', '#ffd38a', '#9fe8ff', '#ffffff', '#ffb36b']
      lanes = Array.from({ length: 16 }, (_, i) => {
        const depth = (i + 0.5) / 16
        const dir: 1 | -1 = Math.random() < 0.5 ? 1 : -1
        const n = Math.round(rand(2, 6) * (W / 1400) + 1)
        return {
          y: H * (0.32 + 0.5 * depth) + rand(-H * 0.04, H * 0.04),
          depth, dir, wobble: rand(0, 6.28),
          cars: Array.from({ length: n }, () => ({
            x: rand(-200, W + 200), speed: rand(40, 70) + 190 * depth, color: pick(colors), trail: 18 + 90 * depth,
          })),
        }
      })
      cruisers = [{ x: rand(0, W), y: H * rand(0.12, 0.22), scale: rand(0.7, 1.1), speed: rand(6, 10) }]
    }

    const drawStars = (t: number) => {
      for (const s of stars) {
        const a = 0.45 + 0.55 * Math.sin(t * 0.001 * s.speed + s.phase)
        ctx.globalAlpha = Math.max(0.08, a)
        ctx.fillStyle = '#e8eeff'
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, 6.283)
        ctx.fill()
      }
      ctx.globalAlpha = 1
    }

    const drawMoons = () => {
      const m = (x: number, y: number, r: number, c1: string, c2: string) => {
        const gr = ctx.createRadialGradient(x - r * 0.35, y - r * 0.35, r * 0.1, x, y, r)
        gr.addColorStop(0, c1)
        gr.addColorStop(1, c2)
        ctx.fillStyle = gr
        ctx.beginPath()
        ctx.arc(x, y, r, 0, 6.283)
        ctx.fill()
      }
      ctx.globalAlpha = 0.85
      m(W * 0.82, H * 0.16, Math.min(W, H) * 0.07, '#f6d9c4', '#5b3150')
      ctx.globalAlpha = 0.6
      m(W * 0.9, H * 0.27, Math.min(W, H) * 0.025, '#cfe6ff', '#2c3566')
      ctx.globalAlpha = 1
    }

    const drawCruisers = (dt: number) => {
      for (const c of cruisers) {
        c.x += c.speed * dt
        if (c.x > W + 300) { c.x = -300; c.y = H * rand(0.1, 0.24) }
        const s = 90 * c.scale
        ctx.fillStyle = 'rgba(40,46,80,0.85)'
        ctx.beginPath()
        ctx.moveTo(c.x + s, c.y)
        ctx.lineTo(c.x - s * 0.9, c.y - s * 0.16)
        ctx.lineTo(c.x - s, c.y + s * 0.08)
        ctx.closePath()
        ctx.fill()
        ctx.fillStyle = 'rgba(30,34,60,0.95)'
        ctx.fillRect(c.x - s * 0.55, c.y - s * 0.2, s * 0.25, s * 0.08)
        ctx.fillStyle = '#9fd8ff'
        for (let k = 0; k < 6; k++) ctx.fillRect(c.x - s * 0.8 + k * s * 0.22, c.y - s * 0.02, 2, 1)
        ctx.fillStyle = 'rgba(120,200,255,0.9)'
        ctx.beginPath()
        ctx.arc(c.x - s, c.y - s * 0.04, 3, 0, 6.283)
        ctx.fill()
      }
    }

    const drawBeacons = (t: number, layer: number) => {
      for (const b of beacons) {
        if (b.layer !== layer) continue
        const on = Math.sin(t * 0.003 + b.phase) > 0.55
        if (!on) continue
        ctx.fillStyle = b.color
        ctx.shadowColor = b.color
        ctx.shadowBlur = 8
        ctx.fillRect(b.x - 1.5, b.y - 1.5, 3, 3)
        ctx.shadowBlur = 0
      }
    }

    const drawTraffic = (t: number, dt: number, minD: number, maxD: number) => {
      for (const lane of lanes) {
        if (lane.depth < minD || lane.depth >= maxD) continue
        const y0 = lane.y + Math.sin(t * 0.0004 + lane.wobble) * 6
        const size = 0.8 + 2.6 * lane.depth
        for (const car of lane.cars) {
          car.x += car.speed * lane.dir * dt
          if (lane.dir === 1 && car.x > W + 220) car.x = -rand(40, 400)
          if (lane.dir === -1 && car.x < -220) car.x = W + rand(40, 400)
          const tail = car.x - lane.dir * car.trail
          const grad = ctx.createLinearGradient(tail, y0, car.x, y0)
          grad.addColorStop(0, 'rgba(255,80,60,0)')
          grad.addColorStop(1, lane.dir === 1 ? 'rgba(255,120,90,0.75)' : 'rgba(255,90,70,0.75)')
          ctx.strokeStyle = grad
          ctx.lineWidth = size * 0.9
          ctx.beginPath()
          ctx.moveTo(tail, y0)
          ctx.lineTo(car.x, y0)
          ctx.stroke()
          ctx.fillStyle = car.color
          ctx.shadowColor = car.color
          ctx.shadowBlur = 6 + 10 * lane.depth
          ctx.beginPath()
          ctx.arc(car.x, y0, size, 0, 6.283)
          ctx.fill()
          ctx.shadowBlur = 0
        }
      }
    }

    const haze = (y: number, h: number, color: string) => {
      const gr = ctx.createLinearGradient(0, y, 0, y + h)
      gr.addColorStop(0, 'rgba(0,0,0,0)')
      gr.addColorStop(1, color)
      ctx.fillStyle = gr
      ctx.fillRect(0, y, W, h)
    }

    const drawMeteor = (dt: number) => {
      if (!meteor && Math.random() < dt * 0.08) {
        meteor = { x: rand(W * 0.1, W * 0.9), y: rand(0, H * 0.2), vx: rand(-420, -260), vy: rand(120, 200), life: 1 }
      }
      if (!meteor) return
      meteor.x += meteor.vx * dt
      meteor.y += meteor.vy * dt
      meteor.life -= dt * 0.9
      const gr = ctx.createLinearGradient(meteor.x, meteor.y, meteor.x - meteor.vx * 0.15, meteor.y - meteor.vy * 0.15)
      gr.addColorStop(0, `rgba(255,255,255,${Math.max(0, meteor.life)})`)
      gr.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.strokeStyle = gr
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.moveTo(meteor.x, meteor.y)
      ctx.lineTo(meteor.x - meteor.vx * 0.15, meteor.y - meteor.vy * 0.15)
      ctx.stroke()
      if (meteor.life <= 0) meteor = null
    }

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      // the window can report 0x0 while the tab is hidden; (re)build once it has a real size
      if (window.innerWidth !== W || window.innerHeight !== H) {
        if (!window.innerWidth || !window.innerHeight) return
        setup()
      }
      const dt = Math.min(0.05, (now - last) / 1000) * (reduce ? 0.15 : 1)
      last = now
      ctx.fillStyle = sky
      ctx.fillRect(0, 0, W, H)
      drawStars(now)
      drawMeteor(dt)
      drawMoons()
      drawCruisers(dt)
      ctx.drawImage(layers[0], 0, 0, W, H)
      drawBeacons(now, 0)
      haze(H * 0.45, H * 0.55, 'rgba(120,50,90,0.35)')
      drawTraffic(now, dt, 0, 0.45)
      ctx.drawImage(layers[1], 0, 0, W, H)
      drawBeacons(now, 1)
      haze(H * 0.55, H * 0.45, 'rgba(60,20,50,0.45)')
      drawTraffic(now, dt, 0.45, 0.8)
      ctx.drawImage(layers[2], 0, 0, W, H)
      drawBeacons(now, 2)
      drawTraffic(now, dt, 0.8, 1.01)
    }

    raf = requestAnimationFrame(frame)
    let resizeTimer = 0
    const onResize = () => {
      clearTimeout(resizeTimer)
      resizeTimer = window.setTimeout(() => { if (window.innerWidth && window.innerHeight) setup() }, 150)
    }
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return <canvas ref={ref} className="city" aria-hidden="true" />
}
