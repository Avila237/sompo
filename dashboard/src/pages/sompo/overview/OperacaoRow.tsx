import { WTONE, scoreBand } from '../../../lib/risco'
import type { OperacaoAgg } from '../../../data/api'
import { ScoreBar } from '../../../components/shared'

/* -- Agregacao por tipo de operacao (terceiro eixo do RF-09) -- */

export function OperacaoRow({ o }: { o: OperacaoAgg }) {
  const tone = scoreBand(o.scoreMedio)
  const pctAlto = o.avaliacoes ? (o.riscoAlto / o.avaliacoes) * 100 : 0
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr 52px 110px 120px', alignItems: 'center', gap: 12 }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg)', textTransform: 'capitalize' }}>
        {o.tipo}
      </span>
      <ScoreBar score={o.scoreMedio} height={8} />
      <span className="tabular" style={{ fontSize: 13, fontWeight: 700, color: WTONE[tone].fg, textAlign: 'right' }}>
        {o.scoreMedio}
      </span>
      <span className="tabular" style={{ fontSize: 11, color: 'var(--fg-mute)', textAlign: 'right' }}>
        {o.avaliacoes.toLocaleString('pt-BR')} avaliações
      </span>
      <span className="tabular" style={{ fontSize: 11, color: 'var(--fg-dim)', textAlign: 'right' }}>
        {o.riscoAlto.toLocaleString('pt-BR')} altas · {pctAlto.toFixed(0)} %
      </span>
    </div>
  )
}
