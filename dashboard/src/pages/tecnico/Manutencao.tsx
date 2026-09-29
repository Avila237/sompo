import { useMemo, useState } from 'react'
import { loadEquipamentos, type EquipamentoView } from '../../data/api'
import { Card, Carregando, ErroCarga, FilterSeg, KPITile, SectionHeader } from '../../components/shared'
import { useCarga } from '../../lib/useCarga'
import { rotuloDaFaixa, SEM_AVALIACAO, WTONE } from '../../lib/risco'

const GRID = '1.1fr 1.8fr 1fr 0.9fr 1fr 1fr'
const fmtAtraso = (v: number) => `${v.toFixed(2).replace('.', ',')}×`

/**
 * Tela inicial do técnico (BRA-460): a frota ordenada pelo atraso de manutenção
 * da última avaliação (campos da BRA-469). `atraso_manutencao_pct` é múltiplo
 * do intervalo recomendado; acima de 1 é atraso (Regra 14).
 */
export default function Manutencao({ onPickEquip }: { onPickEquip: (equipamentoId: string) => void }) {
  const carga = useCarga((recarregar) => loadEquipamentos({ recarregar }))
  const [filtro, setFiltro] = useState<'atrasadas' | 'todas'>('atrasadas')

  const ordenados = useMemo<EquipamentoView[]>(() => {
    const lista = [...(carga.dados ?? [])]
    // Maior atraso primeiro; sem dado de manutenção vai para o fim
    return lista.sort((a, b) => (b.atrasoPct ?? -1) - (a.atrasoPct ?? -1))
  }, [carga.dados])

  if (carga.carregando && !carga.dados) return <Carregando msg="Carregando manutenção da frota…" />
  if (!carga.dados) {
    return <ErroCarga titulo="Não foi possível carregar a frota." msg={carga.erro ?? 'A API não devolveu dados.'} onTentar={carga.tentarDeNovo} />
  }

  // API anterior à BRA-469 não manda os campos: dizer isso, não mostrar zeros
  if (ordenados.length > 0 && ordenados.every((e) => e.atrasoPct === undefined)) {
    return (
      <div style={{ padding: '24px 28px' }}>
        <SectionHeader title="Manutenção da frota" />
        <Card>
          <div style={{ fontSize: 13, color: 'var(--fg-dim)' }}>
            A API ainda não informa o estado de manutenção dos equipamentos. Esta tela depende desse dado e não o inventa.
          </div>
        </Card>
      </div>
    )
  }

  const atrasadas = ordenados.filter((e) => e.manutAtrasada === true)
  const emDia = ordenados.filter((e) => e.manutAtrasada === false)
  // Só entre os atrasados: sem nenhum, uma razão < 1 aparecia como "maior atraso"
  const maior = atrasadas.find((e) => e.atrasoPct != null)
  // Frota inteira sem avaliação: não dá para afirmar que ninguém está atrasado
  const semDado = ordenados.every((e) => e.manutAtrasada == null)
  const visiveis = filtro === 'atrasadas' ? atrasadas : ordenados

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader
        title="Manutenção da frota"
        sub="Ordenado pelo atraso de manutenção da última avaliação: primeiro quem mais passou do intervalo recomendado."
        actions={
          <FilterSeg
            value={filtro}
            onChange={(v) => setFiltro(v as 'atrasadas' | 'todas')}
            opts={[{ k: 'atrasadas', l: `Atrasadas ${atrasadas.length}` }, { k: 'todas', l: 'Toda a frota' }]}
          />
        }
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
        <KPITile label="Manutenção atrasada" value={atrasadas.length} accent="crit" sub="equipamentos" subTone="crit" />
        <KPITile label="Maior atraso" value={maior?.atrasoPct != null ? fmtAtraso(maior.atrasoPct) : '—'} sub={maior ? `${maior.id} · do intervalo recomendado` : semDado ? 'sem dado de manutenção' : 'nenhum equipamento atrasado'} />
        <KPITile label="Em dia" value={emDia.length} accent="safe" sub="equipamentos" subTone="safe" />
      </div>

      <Card pad={0}>
        <div style={{ display: 'grid', gridTemplateColumns: GRID, gap: 8, padding: '10px 18px', fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 1, textTransform: 'uppercase', fontWeight: 700 }}>
          <span>Equipamento</span><span>Modelo</span><span>Manutenção</span><span title="Múltiplo do intervalo recomendado já usado; acima de 1× é atraso">Intervalo usado</span><span>Desde a última</span><span>Risco</span>
        </div>
        {visiveis.length === 0 && (
          <div style={{ padding: '14px 18px', fontSize: 13, color: 'var(--fg-mute)', borderTop: '1px solid var(--line)' }}>
            {filtro === 'atrasadas' ? 'Nenhum equipamento com manutenção atrasada.' : 'Nenhum equipamento na frota.'}
          </div>
        )}
        {visiveis.map((e) => {
          const manut = e.manutAtrasada == null ? null : e.manutAtrasada ? WTONE.crit : WTONE.safe
          return (
            <button
              key={e.id}
              type="button"
              onClick={() => onPickEquip(e.id)}
              style={{
                width: '100%', display: 'grid', gridTemplateColumns: GRID, gap: 8, alignItems: 'center', padding: '11px 18px', minHeight: 44,
                border: 'none', borderTop: '1px solid var(--line)', background: 'transparent', color: 'var(--fg)', textAlign: 'left', fontSize: 13, cursor: 'pointer',
              }}
            >
              <span className="mono" style={{ fontWeight: 600 }}>{e.id}</span>
              <span style={{ color: 'var(--fg-dim)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{e.modelo}</span>
              <span>
                {manut ? (
                  <span style={{ padding: '2px 7px', borderRadius: 4, fontSize: 10, fontWeight: 700, letterSpacing: 0.8, background: manut.bg, color: manut.fg, border: `1px solid ${manut.ring}` }}>
                    {e.manutAtrasada ? 'ATRASADA' : 'EM DIA'}
                  </span>
                ) : <span style={{ color: 'var(--fg-mute)' }}>—</span>}
              </span>
              <span className="tabular" style={{ fontWeight: 700, color: manut?.fg ?? 'var(--fg-mute)' }}>{e.atrasoPct != null ? fmtAtraso(e.atrasoPct) : '—'}</span>
              <span className="tabular" style={{ color: 'var(--fg-dim)' }}>{e.diasManut != null ? `${e.diasManut} dias` : '—'}</span>
              <span className="tabular" style={{ fontWeight: 700, color: WTONE[e.faixa].fg }}>
                {e.score === null ? SEM_AVALIACAO : `${Math.round(e.score)} · ${rotuloDaFaixa(e.faixa)}`}
              </span>
            </button>
          )
        })}
      </Card>
    </div>
  )
}
