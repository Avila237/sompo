import { useState, useMemo } from 'react'
import { WTONE, faixaDaMedia } from '../../lib/risco'
import {
  loadEquipamentos,
  loadVisaoGeral,
  type EquipamentoView,
} from '../../data/api'
import type { ToneKey } from '../../types'
import { Card, ScoreBadge, Trend, KPITile, SectionHeader, Button, ErroCarga, FilterSeg, Carregando } from '../../components/shared'
import { useCarga } from '../../lib/useCarga'
import { OperacaoRow } from './overview/OperacaoRow'
import { BrazilMap } from './overview/BrazilMap'
import { TrendChart } from './overview/TrendChart'
import { WIco } from '../../components/Icons'
import { ComingSoon } from '../../components/ComingSoon'

/* -- Main component ---------------------------------------- */

export default function SompoOverview({
  onPickEquip,
  onNav,
}: {
  onPickEquip: (equipamentoId: string) => void
  onNav: (screen: string) => void
}) {
  const [period, setPeriod] = useState<30 | 60 | 90>(30) // dias com dados
  const [showFilters, setShowFilters] = useState(false)
  const [riskFilter, setRiskFilter] = useState<'all' | 'safe' | 'warn' | 'crit'>('all')
  const [typeFilter, setTypeFilter] = useState<'all' | 'colheitadeira' | 'trator' | 'implemento'>('all')

  // Cargas separadas: falha só em /equipamentos afeta só o Top 5, não a página toda.
  // A lista de equipamentos alimenta o Top 5 e nao depende do periodo.
  const equipC = useCarga((recarregar) => loadEquipamentos({ recarregar }))
  // KPIs, regioes, alertas e tendencia vem de /kpis + /alertas. Refaz a busca
  // ao trocar o periodo porque a janela da serie e resolvida no servidor.
  const visaoC = useCarga(() => loadVisaoGeral(period), period)

  const views = useMemo<EquipamentoView[]>(() => equipC.dados ?? [], [equipC.dados])
  const visao = visaoC.dados

  const kpis = visao?.kpis ?? null
  const trend = visao?.tendencia ?? []
  const regions = useMemo(() => visao?.regioes ?? [], [visao])
  const porOperacao = useMemo(
    () => [...(visao?.porOperacao ?? [])].sort((a, b) => b.scoreMedio - a.scoreMedio),
    [visao],
  )
  const alertas = useMemo(() => visao?.alertas ?? [], [visao])

  const top5 = useMemo(() => {
    let list = [...views]
    if (riskFilter !== 'all') list = list.filter((e) => e.faixa === riskFilter)
    if (typeFilter !== 'all') list = list.filter((e) => e.tipo === typeFilter)
    return list.sort((a, b) => (b.score ?? -1) - (a.score ?? -1)).slice(0, 5)
  }, [views, riskFilter, typeFilter])

  const filteredAlerts = useMemo(() => {
    if (riskFilter === 'all') return alertas
    return alertas.filter((a) => a.sev === riskFilter)
  }, [alertas, riskFilter])

  // A API devolve equipamento_id no alerta, entao nao e mais preciso extrair
  // o id da mensagem por regex.
  const handleAlertClick = (equipamentoId: string) => {
    if (views.some((e) => e.id === equipamentoId)) onPickEquip(equipamentoId)
  }

  const handleClearFilters = () => { setRiskFilter('all'); setTypeFilter('all') }
  const filtersActive = riskFilter !== 'all' || typeFilter !== 'all'

  // Com dados na tela, recarga (período, tentar de novo) não troca a página por "Carregando"
  if (visaoC.carregando && !kpis) return <Carregando msg="Carregando dados da API…" />

  if (!kpis) {
    return (
      <ErroCarga
        titulo="Não foi possível carregar a visão geral."
        msg={visaoC.erro ?? 'A API não devolveu dados.'}
        onTentar={visaoC.tentarDeNovo}
      />
    )
  }

  const scoreTone: ToneKey = faixaDaMedia(kpis.scoreMedio)
  const scoreToneLabel = scoreTone === 'safe' ? 'Baixo risco global' : scoreTone === 'warn' ? 'Risco moderado' : 'Risco elevado'

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <SectionHeader
        title="Visão geral da carteira"
        sub={`Safra 2025 · ${kpis.totalEquip} equipamentos · ${kpis.totalAval.toLocaleString('pt-BR')} avaliações`}
        actions={
          <>
            <Button kind="ghost" onClick={() => setShowFilters((v) => !v)}>{WIco.filter()} Filtros</Button>
            {/* Sem endpoint de exportação: bloqueado e sem confirmação simulada */}
            <ComingSoon inline><Button kind="ghost">
              {WIco.download()} Exportar
            </Button></ComingSoon>
            <ComingSoon inline><Button kind="primary" tone="safe" onClick={() => onNav('simulator')}>Nova análise</Button></ComingSoon>
          </>
        }
      />

      {/* Já havia dados e a recarga (ex.: troca de período) falhou: mantém a tela e avisa */}
      {visaoC.erro && (
        <Card pad={0} style={{ padding: '0 18px' }}>
          <ErroCarga compacto titulo="Falha ao atualizar os indicadores; exibindo os últimos carregados." msg={visaoC.erro} onTentar={visaoC.tentarDeNovo} />
        </Card>
      )}

      {showFilters && (
        <div style={{
          background: 'var(--bg-elev)', border: '1px solid var(--line)', borderRadius: 10,
          padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
        }}>
          <FilterSeg
            value={riskFilter}
            onChange={(v) => setRiskFilter(v as 'all' | 'safe' | 'warn' | 'crit')}
            opts={[
              { k: 'all', l: 'Todos' },
              { k: 'safe', l: 'Baixo', dot: WTONE.safe.fg },
              { k: 'warn', l: 'Médio', dot: WTONE.warn.fg },
              { k: 'crit', l: 'Alto', dot: WTONE.crit.fg },
            ]}
          />
          <FilterSeg
            value={typeFilter}
            onChange={(v) => setTypeFilter(v as 'all' | 'colheitadeira' | 'trator' | 'implemento')}
            opts={[
              { k: 'all', l: 'Todos' },
              { k: 'colheitadeira', l: 'Colheitadeira' },
              { k: 'trator', l: 'Trator' },
              { k: 'implemento', l: 'Implemento' },
            ]}
          />
          <button
            onClick={handleClearFilters}
            style={{
              padding: '6px 14px', borderRadius: 6, border: '1px solid var(--line)',
              background: filtersActive ? 'var(--line)' : 'transparent',
              color: filtersActive ? 'var(--fg)' : 'var(--fg-mute)',
              fontWeight: 600, fontSize: 12, cursor: 'pointer',
            }}
          >
            Limpar
          </button>
        </div>
      )}

      {/* --- KPIs --- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
        <KPITile label="Equipamentos" value={kpis.totalEquip} sub="Frota monitorada" />
        <KPITile label="Avaliações" value={kpis.totalAval.toLocaleString('pt-BR')} sub="Registros de risco" />
        <KPITile label="Score médio" value={kpis.scoreMedio} unit="/100" accent={scoreTone} sub={scoreToneLabel} subTone={scoreTone} />
        <KPITile label="Risco alto" value={kpis.riscoAlto} accent="crit" sub={`${kpis.pctRiscoAlto.toFixed(1)} % da frota`} subTone="crit" />
        <KPITile label="Operadores" value={kpis.operadores} sub="Perfis monitorados" />
      </div>

      {/* --- Map + Trend --- */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 14 }}>
        <Card title={`Distribuição geográfica · ${regions.length} polos`} pad={12}>
          <div style={{ height: 340 }}>
            <BrazilMap regions={regions} />
          </div>
        </Card>

        {/* A janela conta dias COM dados (contrato de /kpis): "30d" sugeria dias corridos */}
        <Card
          // Período dos dados NA TELA: após uma recarga que falhou, o título não pode prometer o período pedido
          title={`Score médio · últimos ${visaoC.chaveDados ?? period} dias com dados${visaoC.carregando ? ' · atualizando…' : ''}`}
          action={
            <div style={{ display: 'flex', gap: 4 }}>
              {([30, 60, 90] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  title={`Últimos ${p} dias que têm avaliação`}
                  style={{
                    padding: '3px 10px', borderRadius: 4, border: '1px solid var(--line)',
                    background: period === p ? 'var(--line)' : 'transparent',
                    color: period === p ? 'var(--fg)' : 'var(--fg-mute)',
                    fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          }
          pad={16}
        >
          <TrendChart pontos={trend} />
        </Card>
      </div>

      {/* --- Aggregation by operation type (RF-09) --- */}
      <Card title={`Risco por tipo de operação · ${porOperacao.length} tipos`} pad={18}>
        {porOperacao.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {porOperacao.map((o) => (
              <OperacaoRow key={o.tipo} o={o} />
            ))}
          </div>
        ) : (
          <div style={{ padding: '18px 0', textAlign: 'center', color: 'var(--fg-mute)', fontSize: 13 }}>
            Sem avaliações agregadas por operação.
          </div>
        )}
      </Card>

      {/* --- Top 5 + Alerts --- */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 14 }}>
        <Card title="Top 5 · risco mais alto" pad={0}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 18 }}>
            {top5.map((eq) => (
              <button
                key={eq.id}
                onClick={() => onPickEquip(eq.id)}
                style={{
                  background: 'var(--bg-elev-2)', border: '1px solid var(--line)', borderRadius: 8,
                  padding: '10px 12px',
                  display: 'grid', gridTemplateColumns: 'auto 1.6fr 1fr 80px 70px',
                  gap: 12, alignItems: 'center', cursor: 'pointer', color: 'var(--fg)',
                }}
              >
                <ScoreBadge score={eq.score} tone={eq.faixa} size="sm" />
                <div style={{ textAlign: 'left', minWidth: 0 }}>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 0.5, fontWeight: 600 }}>{eq.id}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{eq.modelo}</div>
                </div>
                <div style={{ textAlign: 'left', fontSize: 12, color: 'var(--fg-dim)' }}>
                  <span style={{ textTransform: 'capitalize' }}>{eq.tipo}</span>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--fg-mute)' }}>{eq.operador}</div>
                </div>
                <Trend delta={eq.trend} />
                <span className="mono" style={{ fontSize: 11, color: 'var(--fg-mute)', textAlign: 'right' }}>{eq.avaliacoes} aval.</span>
              </button>
            ))}
            {equipC.erro && (
              <ErroCarga compacto titulo="Não foi possível carregar os equipamentos." msg={equipC.erro} onTentar={equipC.tentarDeNovo} />
            )}
            {!equipC.erro && top5.length === 0 && (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--fg-mute)', fontSize: 13 }}>
                Nenhum equipamento nesta faixa.
              </div>
            )}
          </div>
        </Card>

        <Card title="Alertas recentes" pad={0}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 18 }}>
            {filteredAlerts.map((a, i) => (
              <button
                key={i}
                onClick={() => handleAlertClick(a.equipamentoId)}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 10, padding: '2px 0 10px',
                  background: 'transparent', border: 'none',
                  borderBottom: i < filteredAlerts.length - 1 ? '1px solid var(--line)' : 'none',
                  width: '100%', textAlign: 'left', color: 'var(--fg)', cursor: 'pointer',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '0.7' }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '1' }}
              >
                <span style={{ width: 6, height: 6, borderRadius: 3, background: WTONE[a.sev].fg, marginTop: 7, boxShadow: `0 0 8px ${WTONE[a.sev].fg}`, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{a.msg}</div>
                </div>
                <span className="mono" style={{ fontSize: 11, color: 'var(--fg-dim)' }}>{a.time}</span>
              </button>
            ))}
            {filteredAlerts.length === 0 && (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--fg-mute)', fontSize: 13 }}>
                Nenhum alerta nesta faixa.
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}