import { useMemo, useState } from 'react'
import { WTONE, faixaDaMedia, rotuloDaMedia } from '../../lib/risco'
import { loadTendencias, type Eixo, type SerieTendencia } from '../../data/tendencias'
import { Card, Chip, SectionHeader, Button, ErroCarga, Carregando, FilterSeg } from '../../components/shared'
import { WIco } from '../../components/Icons'
import { useCarga } from '../../lib/useCarga'
import { fmtDiaIso } from '../../lib/formato'
import { baixarCsv, gerarCsv } from '../../lib/csv'
import { TendenciaChart } from './relatorios/TendenciaChart'

// Distintas em claridade, não só em matiz; fora do verde/âmbar/vermelho das faixas de risco
const CORES = ['#6EB9FF', '#FFB526', '#34D3C0', '#A78BFA', '#D5D9D6']

const ROTULO_EIXO: Record<Eixo, string> = { equipamento: 'Equipamento', regiao: 'Região', operacao: 'Operação' }
const PERIODOS = [30, 60, 90] as const

/** Resumo de uma série para tabela e destaques. Início/fim são o primeiro e o último ponto REAIS. */
function resumo(s: SerieTendencia) {
  const inicio = s.pontos[0]?.score ?? null
  const fim = s.pontos[s.pontos.length - 1]?.score ?? null
  const pico = s.pontos.length ? Math.max(...s.pontos.map((p) => p.score)) : null
  const variacao = inicio !== null && fim !== null && s.pontos.length > 1 ? fim - inicio : null
  return { inicio, fim, pico, variacao }
}

const fmt = (v: number | null) => (v === null ? '—' : String(Math.round(v)))

function Variacao({ v }: { v: number | null }) {
  if (v === null) return <span style={{ color: 'var(--fg-mute)' }}>—</span>
  const r = Math.round(v)
  const cor = r > 0 ? 'var(--red)' : r < 0 ? 'var(--green)' : 'var(--fg-mute)'
  return <span style={{ color: cor, fontWeight: 700 }}>{r > 0 ? `▲ +${r}` : r < 0 ? `▼ −${Math.abs(r)}` : '0'}</span>
}

export default function SompoReports() {
  const [eixo, setEixo] = useState<Eixo>('operacao')
  const [dias, setDias] = useState<(typeof PERIODOS)[number]>(30)
  const [foco, setFoco] = useState<string | null>(null)

  const carga = useCarga(() => loadTendencias(eixo, dias), `${eixo}:${dias}`)
  const dados = carga.dados
  const series = useMemo(() => dados?.series ?? [], [dados])
  const linhas = useMemo(() => series.map((s, i) => ({ s, cor: CORES[i % CORES.length], ...resumo(s) })), [series])

  if (carga.carregando && !dados) return <Carregando msg="Carregando tendência…" />
  if (!dados) {
    return <ErroCarga titulo="Não foi possível carregar a tendência." msg={carga.erro ?? 'A API não devolveu dados.'} onTentar={carga.tentarDeNovo} />
  }

  const datas = dados.datas
  const janela = datas.length ? `${fmtDiaIso(datas[0])} – ${fmtDiaIso(datas[datas.length - 1])}` : 'sem dados'
  const rotulo = ROTULO_EIXO[dados.eixo].toLowerCase()

  const comFim = linhas.filter((l) => l.fim !== null)
  const maior = comFim.length ? comFim.reduce((a, b) => (b.fim! > a.fim! ? b : a)) : null
  const comVar = linhas.filter((l) => l.variacao !== null)
  const alta = comVar.length ? comVar.reduce((a, b) => (b.variacao! > a.variacao! ? b : a)) : null

  const exportar = () => {
    const csv = gerarCsv(
      ['eixo', 'chave', 'dia', 'score_medio', 'avaliacoes'],
      series.flatMap((s) => s.pontos.map((p) => [dados.eixo, s.chave, p.dia, p.score, p.avaliacoes])),
    )
    baixarCsv(`tendencias_${dados.eixo}_${dados.dias}d_${datas[datas.length - 1] ?? 'vazio'}.csv`, csv)
  }

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader
        title="Tendência de risco"
        sub={`Score médio diário por ${rotulo} · últimos ${dados.dias} dias com dados · ${janela}${carga.carregando ? ' · atualizando…' : ''}`}
        actions={
          <Button kind="ghost" onClick={exportar} disabled={series.length === 0}>
            {WIco.download()} Exportar CSV
          </Button>
        }
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <FilterSeg
          value={eixo}
          onChange={(v) => { setEixo(v as Eixo); setFoco(null) }}
          opts={(['equipamento', 'regiao', 'operacao'] as const).map((k) => ({ k, l: ROTULO_EIXO[k] }))}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 11, color: 'var(--fg-mute)', fontWeight: 600, letterSpacing: 0.8, textTransform: 'uppercase' }}>Dias com dados</span>
          <FilterSeg value={String(dias)} onChange={(v) => setDias(Number(v) as (typeof PERIODOS)[number])} opts={PERIODOS.map((p) => ({ k: String(p), l: String(p) }))} />
        </div>
      </div>

      {/* Recarga que falhou com dados na tela: mantém os anteriores e avisa */}
      {carga.erro && (
        <Card pad={0} style={{ padding: '0 18px' }}>
          <ErroCarga compacto titulo="Falha ao atualizar; exibindo a última tendência carregada." msg={carga.erro} onTentar={carga.tentarDeNovo} />
        </Card>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
        <Destaque titulo="Maior score no último ponto" valor={maior ? fmt(maior.fim) : '—'} cor={maior ? WTONE[faixaDaMedia(maior.fim!)].fg : undefined} legenda={maior?.s.rotulo ?? 'sem dados'} />
        <Destaque titulo="Maior alta no período" valor={alta ? `${alta.variacao! >= 0 ? '+' : '−'}${Math.abs(Math.round(alta.variacao!))}` : '—'} cor={alta && alta.variacao! > 0 ? 'var(--red)' : undefined} legenda={alta?.s.rotulo ?? 'precisa de 2 pontos'} />
        <Destaque titulo="Janela" valor={String(datas.length)} legenda={`dias com dados · ${janela}`} />
      </div>

      {series.length === 0 ? (
        <Card>
          <div style={{ padding: '32px 0', textAlign: 'center' }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Nenhuma avaliação para este eixo na janela</div>
            <div style={{ fontSize: 12, color: 'var(--fg-dim)', marginTop: 6 }}>Nada é preenchido com zero.</div>
          </div>
        </Card>
      ) : (
        <>
          <Card title={`Evolução · top ${series.length} por ${rotulo}`}>
            <div style={{ display: 'flex', gap: 24 }}>
              <TendenciaChart datas={datas} series={series} cores={CORES} foco={foco} />
              <div style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
                <div style={{ fontSize: 11, color: 'var(--fg-mute)', fontWeight: 600 }}>Clique numa linha da tabela para destacar a série.</div>
                {linhas.map((l) => (
                  <div key={l.s.chave} style={{ display: 'flex', alignItems: 'center', gap: 8, opacity: !foco || foco === l.s.chave ? 1 : 0.4 }}>
                    <span style={{ width: 14, height: 3, borderRadius: 2, background: l.cor, flexShrink: 0 }} />
                    <span style={{ fontSize: 12, flexGrow: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textTransform: dados.eixo === 'operacao' ? 'capitalize' : 'none' }}>{l.s.rotulo}</span>
                    <span className="tabular" style={{ fontSize: 12, fontWeight: 700, color: l.fim !== null ? WTONE[faixaDaMedia(l.fim)].fg : 'var(--fg-mute)' }}>{fmt(l.fim)}</span>
                  </div>
                ))}
                <div style={{ marginTop: 'auto', fontSize: 11, color: 'var(--fg-mute)', lineHeight: 1.5 }}>
                  Cada ponto marcado é um dia <strong style={{ color: 'var(--fg-dim)' }}>com avaliação</strong> do grupo. Dia sem dado não vira zero nem é inventado; o eixo usa a data real.
                </div>
              </div>
            </div>
          </Card>

          <Card pad={0}>
            <div style={{ display: 'grid', gridTemplateColumns: GRID, gap: 8, padding: '10px 18px', fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 1, textTransform: 'uppercase', fontWeight: 700 }}>
              <span>{ROTULO_EIXO[dados.eixo]}</span><span>Início</span><span>Fim</span><span>Variação</span><span>Média</span><span>Pico</span><span>Avaliações</span>
            </div>
            {linhas.map((l) => {
              const focado = foco === l.s.chave
              return (
                <button
                  key={l.s.chave}
                  type="button"
                  aria-pressed={focado}
                  onClick={() => setFoco(focado ? null : l.s.chave)}
                  style={{
                    width: '100%', display: 'grid', gridTemplateColumns: GRID, gap: 8, alignItems: 'center',
                    padding: '11px 18px', minHeight: 44, border: 'none', borderTop: '1px solid var(--line)',
                    background: focado ? 'var(--bg-elev-2)' : 'transparent', color: 'var(--fg)', textAlign: 'left', fontSize: 13, cursor: 'pointer',
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: l.cor, flexShrink: 0 }} />
                    <span style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textTransform: dados.eixo === 'operacao' ? 'capitalize' : 'none' }}>{l.s.rotulo}</span>
                  </span>
                  <span className="tabular" style={{ color: 'var(--fg-dim)' }}>{fmt(l.inicio)}</span>
                  <span className="tabular" style={{ fontWeight: 700 }}>{fmt(l.fim)}</span>
                  <span className="tabular"><Variacao v={l.variacao} /></span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="tabular">{Math.round(l.s.scoreMedio)}</span>
                    <Chip state={faixaDaMedia(l.s.scoreMedio)} label={rotuloDaMedia(l.s.scoreMedio)} size="sm" />
                  </span>
                  <span className="tabular" style={{ color: 'var(--fg-dim)' }}>{fmt(l.pico)}</span>
                  <span className="tabular" style={{ color: 'var(--fg-dim)' }}>{l.s.avaliacoes.toLocaleString('pt-BR')}</span>
                </button>
              )
            })}
          </Card>
        </>
      )}
    </div>
  )
}

const GRID = '2fr 1fr 1fr 1fr 1.2fr 1fr 1fr'

function Destaque({ titulo, valor, legenda, cor }: { titulo: string; valor: string; legenda: string; cor?: string }) {
  return (
    <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--line)', borderRadius: 10, padding: '14px 18px' }}>
      <div style={{ fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 1.3, textTransform: 'uppercase', fontWeight: 700 }}>{titulo}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 6, minWidth: 0 }}>
        <span className="tabular" style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1, color: cor ?? 'var(--fg)' }}>{valor}</span>
        <span style={{ fontSize: 13, color: 'var(--fg-dim)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{legenda}</span>
      </div>
    </div>
  )
}
