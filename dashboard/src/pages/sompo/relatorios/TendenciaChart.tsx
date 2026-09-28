import type { SerieTendencia } from '../../../data/tendencias'
import { fmtDiaIso } from '../../../lib/formato'

const W = 840, H = 300, PL = 36, PR = 12, PT = 12, PB = 28
const CW = W - PL - PR
const CH = H - PT - PB

/**
 * Séries de score num eixo X comum (`datas`: dias com dados, não corridos).
 * Cada ponto real ganha marcador; a linha liga só os pontos reais do grupo —
 * nenhum ponto é criado para dia sem avaliação.
 */
export function TendenciaChart({ datas, series, cores, foco }: {
  datas: string[]
  series: SerieTendencia[]
  cores: string[]
  foco: string | null
}) {
  if (datas.length < 2) {
    return (
      <div style={{ width: W, height: H, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--fg-mute)', fontSize: 13, textAlign: 'center' }}>
        A janela tem menos de 2 dias com dados; não há série para desenhar.
      </div>
    )
  }

  const idx = new Map(datas.map((d, i) => [d, i]))
  const x = (i: number) => PL + (i / (datas.length - 1)) * CW
  const y = (v: number) => PT + (1 - v / 100) * CH
  const n = datas.length
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round((n - 1) * f))

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label="Evolução do score médio por grupo" style={{ display: 'block', flexShrink: 0 }}>
      <rect x={PL} y={y(100)} width={CW} height={y(66) - y(100)} fill="rgba(232,55,46,0.05)" />
      <rect x={PL} y={y(66)} width={CW} height={y(33) - y(66)} fill="rgba(255,181,38,0.05)" />
      <rect x={PL} y={y(33)} width={CW} height={y(0) - y(33)} fill="rgba(90,224,107,0.05)" />
      <line x1={PL} y1={y(66)} x2={W - PR} y2={y(66)} stroke="rgba(255,181,38,0.25)" strokeDasharray="4,3" />
      <line x1={PL} y1={y(33)} x2={W - PR} y2={y(33)} stroke="rgba(90,224,107,0.25)" strokeDasharray="4,3" />
      {[100, 66, 33, 0].map((v) => (
        <text key={v} x={PL - 8} y={y(v) + 4} fill="#6B7370" fontSize="10" textAnchor="end">{v}</text>
      ))}

      {series.map((s, si) => {
        const pts = s.pontos
          .filter((p) => idx.has(p.dia))
          .map((p) => ({ px: x(idx.get(p.dia)!), py: y(p.score) }))
        const ativo = !foco || foco === s.chave
        const cor = cores[si % cores.length]
        return (
          <g key={s.chave} opacity={ativo ? 1 : 0.18}>
            {pts.length > 1 && (
              <polyline
                points={pts.map((p) => `${p.px.toFixed(1)},${p.py.toFixed(1)}`).join(' ')}
                fill="none" stroke={cor} strokeWidth={foco === s.chave ? 3 : 2}
                strokeLinecap="round" strokeLinejoin="round"
              />
            )}
            {pts.map((p, i) => <circle key={i} cx={p.px} cy={p.py} r={2.5} fill={cor} />)}
          </g>
        )
      })}

      {ticks.map((i, k) => (
        <text
          key={k} x={x(i)} y={H - 6} fill="#6B7370" fontSize="10" fontFamily="JetBrains Mono, monospace"
          textAnchor={k === 0 ? 'start' : k === ticks.length - 1 ? 'end' : 'middle'}
        >
          {fmtDiaIso(datas[i])}
        </text>
      ))}
    </svg>
  )
}
