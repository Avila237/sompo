import { useState } from 'react'
import { Card } from '../../../components/shared'
import { WTONE } from '../../../lib/risco'
import type { ToneKey } from '../../../types'
import {
  criterioLegivel,
  IDS_FALLBACK,
  ROTULO_PUBLICO,
  type Publico,
  type Recomendacao,
} from '../../../data/recomendacoes'

// Tom identifica quem age (design aprovado no canvas da BRA-458); não é faixa de risco
const TOM_PUBLICO: Record<Publico, ToneKey> = { operador: 'info', gestor: 'warn', tecnico: 'neut' }

type Filtro = 'todos' | Publico

/**
 * Ações preventivas da última avaliação, com o critério que disparou cada uma.
 * A lista vem em ordem de prioridade do backend; o filtro só recorta por quem age.
 */
export function RecomendacoesCard({ recomendacoes }: { recomendacoes: Recomendacao[] }) {
  const [filtro, setFiltro] = useState<Filtro>('todos')

  if (recomendacoes.length === 0) {
    return (
      <Card title="Recomendações preventivas">
        <div style={{ fontSize: 13, color: 'var(--fg-dim)' }}>
          Nenhuma ação preventiva para a última avaliação: risco baixo e nenhuma regra disparada.
        </div>
      </Card>
    )
  }

  const publicos = (['operador', 'gestor', 'tecnico'] as const).filter((p) => recomendacoes.some((r) => r.publico === p))
  const visiveis = recomendacoes.filter((r) => filtro === 'todos' || r.publico === filtro)
  const opcoes: Array<{ k: Filtro; l: string }> = [
    { k: 'todos', l: `Todos ${recomendacoes.length}` },
    ...publicos.map((p) => ({ k: p, l: `${ROTULO_PUBLICO[p]} ${recomendacoes.filter((r) => r.publico === p).length}` })),
  ]
  const n = recomendacoes.length

  return (
    <Card
      title={`Recomendações preventivas · ${n} ${n === 1 ? 'ação' : 'ações'} em ordem de prioridade`}
      pad={0}
      action={publicos.length > 1 ? (
        <div role="group" aria-label="Filtrar por quem age" style={{ display: 'inline-flex', border: '1px solid var(--line)', borderRadius: 6, overflow: 'hidden' }}>
          {opcoes.map((o) => {
            const ativo = filtro === o.k
            return (
              <button
                key={o.k}
                type="button"
                aria-pressed={ativo}
                onClick={() => setFiltro(o.k)}
                style={{
                  padding: '6px 12px', minHeight: 32, border: 'none', borderRight: '1px solid var(--line)',
                  fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  background: ativo ? 'var(--line)' : 'transparent', color: ativo ? 'var(--fg)' : 'var(--fg-mute)',
                }}
              >
                {o.l}
              </button>
            )
          })}
        </div>
      ) : undefined}
    >
      {visiveis.map((r, i) => {
        const tom = WTONE[TOM_PUBLICO[r.publico]]
        return (
          <div key={`${r.id}-${i}`} style={{ display: 'grid', gridTemplateColumns: '120px minmax(0, 1fr)', gap: 16, padding: '14px 18px', borderTop: i > 0 ? '1px solid var(--line)' : 'none' }}>
            <div>
              <span style={{
                display: 'inline-flex', padding: '3px 8px', borderRadius: 4, fontSize: 10, fontWeight: 700,
                letterSpacing: 0.8, textTransform: 'uppercase', background: tom.bg, color: tom.fg, border: `1px solid ${tom.ring}`,
              }}>
                {ROTULO_PUBLICO[r.publico]}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.4 }}>{r.acao}</div>
              <div style={{ fontSize: 12, color: 'var(--fg-dim)', lineHeight: 1.5 }}>
                <span style={{ color: 'var(--fg-mute)', fontWeight: 600 }}>Por quê: </span>{criterioLegivel(r.criterio)}
              </div>
              {IDS_FALLBACK.has(r.id) && (
                <div style={{ fontSize: 11, color: 'var(--fg-mute)' }}>
                  Nenhuma regra específica disparou; a ação vem do fator que mais elevou o score.
                </div>
              )}
              <div className="mono" style={{ fontSize: 10, color: 'var(--fg-mute)', overflowWrap: 'anywhere' }}>
                regra {r.id} · {r.criterio}
              </div>
            </div>
          </div>
        )
      })}
    </Card>
  )
}
