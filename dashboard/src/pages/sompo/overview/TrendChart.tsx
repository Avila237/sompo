import { WTONE, scoreBand } from '../../../lib/risco'
import type { TendenciaPonto } from '../../../data/api'
import { fmtDiaIso } from '../../../lib/formato'

/* -- Trend chart sub-component ----------------------------- */

export function TrendChart({ pontos }: { pontos: TendenciaPonto[] }) {
  const data = pontos.map((p) => p.score)
  const W = 480, H = 200, PAD = { t: 16, r: 12, b: 24, l: 12 }
  const cw = W - PAD.l - PAD.r
  const ch = H - PAD.t - PAD.b
  const max = 100, min = 0

  if (data.length < 2) {
    return (
      <div style={{ height: H, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--fg-mute)', fontSize: 13 }}>
        Sem dados suficientes no período.
      </div>
    )
  }

  const pts = data.map((v, i) => {
    const x = PAD.l + (i / (data.length - 1)) * cw
    const y = PAD.t + (1 - (v - min) / (max - min)) * ch
    return `${x},${y}`
  }).join(' ')

  const avg = data.reduce((a, b) => a + b, 0) / data.length
  const mn = Math.min(...data)
  const mx = Math.max(...data)
  const bandY = (v: number) => PAD.t + (1 - v / 100) * ch

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: 'block' }}>
        <rect x={PAD.l} y={bandY(100)} width={cw} height={bandY(66) - bandY(100)} fill="rgba(232,55,46,0.05)" />
        <rect x={PAD.l} y={bandY(66)} width={cw} height={bandY(33) - bandY(66)} fill="rgba(255,181,38,0.05)" />
        <rect x={PAD.l} y={bandY(33)} width={cw} height={bandY(0) - bandY(33)} fill="rgba(90,224,107,0.05)" />

        <line x1={PAD.l} y1={bandY(33)} x2={W - PAD.r} y2={bandY(33)} stroke="rgba(90,224,107,0.2)" strokeWidth="0.7" strokeDasharray="4,3" />
        <line x1={PAD.l} y1={bandY(66)} x2={W - PAD.r} y2={bandY(66)} stroke="rgba(255,181,38,0.2)" strokeWidth="0.7" strokeDasharray="4,3" />

        <polyline points={pts} fill="none" stroke={WTONE[scoreBand(avg)].fg} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {(() => {
          const last = data[data.length - 1]
          const x = W - PAD.r
          const y = PAD.t + (1 - last / 100) * ch
          const c = WTONE[scoreBand(last)].fg
          return (
            <>
              <circle cx={x} cy={y} r="5" fill={c} fillOpacity="0.2" />
              <circle cx={x} cy={y} r="3" fill={c} />
            </>
          )
        })()}

        {/* Eixo com a data real do ponto: os pontos são dias com dados, não dias corridos */}
        <text x={PAD.l} y={H - 4} fill="var(--fg-mute)" fontSize="9" fontFamily="Inter Tight">{fmtDiaIso(pontos[0].dia)}</text>
        <text x={PAD.l + cw / 2} y={H - 4} fill="var(--fg-mute)" fontSize="9" fontFamily="Inter Tight" textAnchor="middle">{fmtDiaIso(pontos[Math.floor((pontos.length - 1) / 2)].dia)}</text>
        <text x={W - PAD.r} y={H - 4} fill="var(--fg-mute)" fontSize="9" fontFamily="Inter Tight" textAnchor="end">{fmtDiaIso(pontos[pontos.length - 1].dia)}</text>
      </svg>

      <div style={{ display: 'flex', gap: 20, marginTop: 10, paddingLeft: 4 }}>
        {[
          { k: 'MÍN', v: mn.toFixed(0), tone: 'safe' as const },
          { k: 'MÉD', v: avg.toFixed(0), tone: 'warn' as const },
          { k: 'MÁX', v: mx.toFixed(0), tone: 'crit' as const },
        ].map((s) => (
          <div key={s.k} style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
            <span style={{ fontSize: 10, color: 'var(--fg-mute)', fontWeight: 700, letterSpacing: 1 }}>{s.k}</span>
            <span className="tabular" style={{ fontSize: 16, fontWeight: 800, color: WTONE[s.tone].fg }}>{s.v}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
