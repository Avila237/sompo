import { useState, useEffect, useMemo } from 'react'
import { WTONE, scoreBand, scoreBandLabel } from '../../data/mock'
import {
  loadEquipamentoDetail,
  aggregateShapByGroup,
  featureLabel,
  SHAP_GROUP_META,
  type EquipamentoDetail,
  type GrupoShap,
  type ShapFactor,
} from '../../data/api'
import type { Equipment } from '../../types'
import { Card, Chip, ScoreBadge, Trend, Sparkline, Button } from '../../components/shared'
import { WIco } from '../../components/Icons'
import { ComingSoon } from '../../components/ComingSoon'

/* ── Diverging SHAP bar (positivo = aumenta risco) ────────── */

function DivergingBar({ value, maxAbs, color }: { value: number; maxAbs: number; color: string }) {
  const pct = maxAbs > 0 ? (Math.abs(value) / maxAbs) * 50 : 0
  const positive = value >= 0
  return (
    <div style={{ position: 'relative', height: 14, background: 'var(--bg-elev-2)', borderRadius: 4, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--line-3)' }} />
      <div
        style={{
          position: 'absolute',
          top: 2,
          bottom: 2,
          borderRadius: 3,
          background: color,
          opacity: positive ? 0.9 : 0.45,
          ...(positive
            ? { left: '50%', width: `${pct}%` }
            : { right: '50%', width: `${pct}%` }),
        }}
      />
    </div>
  )
}

/* ── Stat tile ────────────────────────────────────────────── */

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ background: 'var(--bg)', border: '1px solid var(--line)', borderRadius: 8, padding: '10px 12px' }}>
      <div style={{ fontSize: 10, color: 'var(--fg-mute)', fontWeight: 600, letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
      <div className="tabular" style={{ fontSize: 17, fontWeight: 800, color: tone ?? 'var(--fg)', letterSpacing: -0.5 }}>{value}</div>
    </div>
  )
}

const fmtSigned = (v: number) => `${v >= 0 ? '+' : '−'}${Math.abs(v).toFixed(1)}`
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

/* ── Main ─────────────────────────────────────────────────── */

export default function SompoDetail({ equip, onBack }: { equip: Equipment | null; onBack: () => void }) {
  const [detail, setDetail] = useState<EquipamentoDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [reportState, setReportState] = useState<null | 'generating' | 'done'>(null)
  const [showCallPanel, setShowCallPanel] = useState(false)
  const [callState, setCallState] = useState<null | 'connected'>(null)
  const [showAlertPanel, setShowAlertPanel] = useState(false)
  const [alertSeverity, setAlertSeverity] = useState<'yellow' | 'red'>('red')
  const [alertMsg, setAlertMsg] = useState('Condições adversas detectadas. Retorne à base.')
  const [alertState, setAlertState] = useState<null | 'sent'>(null)

  useEffect(() => {
    if (!equip) { setLoading(false); return }
    let active = true
    setLoading(true)
    setError(null)
    loadEquipamentoDetail(equip.id)
      .then((d) => { if (active) { setDetail(d); setLoading(false) } })
      .catch((e) => { if (active) { setError(String(e?.message ?? e)); setLoading(false) } })
    return () => { active = false }
  }, [equip])

  const shapGroups = useMemo<GrupoShap[]>(
    () => (detail?.predicao ? aggregateShapByGroup(detail.predicao.top_fatores_shap) : []),
    [detail],
  )
  const topFactors = useMemo<ShapFactor[]>(
    () =>
      detail?.predicao
        ? [...detail.predicao.top_fatores_shap].sort((a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value))
        : [],
    [detail],
  )

  if (!equip) {
    return (
      <div style={{ padding: '40px 28px', textAlign: 'center', color: 'var(--fg-mute)', fontSize: 14 }}>
        Selecione um equipamento no Ranking para ver o detalhe.
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ padding: '24px 28px', display: 'flex', alignItems: 'center', justifyContent: 'center', height: 320, color: 'var(--fg-mute)', fontSize: 14 }}>
        Carregando detalhe de {equip.id}…
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div style={{ padding: '24px 28px', color: 'var(--red)', fontSize: 14 }}>
        Erro ao carregar detalhe: {error ?? 'sem dados'}
      </div>
    )
  }

  const { equipamento, ultima, predicao, historico } = detail
  const score = ultima ? ultima.risco_score : 0
  const band = scoreBand(score)
  const bandLabel = scoreBandLabel(score)
  const trend =
    historico.length >= 2
      ? Math.round(historico[historico.length - 1].score - historico[historico.length - 2].score)
      : 0

  const maxGroupAbs = shapGroups.reduce((m, g) => Math.max(m, Math.abs(g.value)), 0)
  const maxFactorAbs = topFactors.reduce((m, f) => Math.max(m, Math.abs(f.shap_value)), 0)

  const histScores = historico.map((h) => h.score)
  const histMin = histScores.length ? Math.min(...histScores) : 0
  const histMax = histScores.length ? Math.max(...histScores) : 0
  const fmtDate = (ts: string) => (ts ? new Date(ts).toLocaleDateString('pt-BR') : '—')

  const noturno = ultima ? ultima.horario_operacao >= 20 || ultima.horario_operacao <= 5 : false

  const handleReport = () => {
    setReportState('generating')
    setTimeout(() => { setReportState('done'); setTimeout(() => setReportState(null), 2000) }, 1500)
  }
  const handleCall = () => {
    setCallState('connected')
    setTimeout(() => { setCallState(null); setShowCallPanel(false) }, 2000)
  }
  const handleAlert = () => {
    setAlertState('sent')
    setTimeout(() => { setAlertState(null); setShowAlertPanel(false) }, 2000)
  }

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <button
          onClick={onBack}
          style={{ background: 'none', border: 'none', color: 'var(--fg-dim)', cursor: 'pointer', fontWeight: 600, fontSize: 13, padding: 0, display: 'inline-flex', alignItems: 'center', gap: 4 }}
        >
          ← Equipamentos
        </button>
        <span style={{ color: 'var(--fg-mute)', fontSize: 13 }}>/</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--fg)' }}>{equipamento.equipamento_id}</span>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <ScoreBadge score={score} size="xl" />
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.4 }}>{equipamento.equipamento_id}</span>
            <Chip state={band} label={bandLabel} />
            <Trend delta={trend} />
            {equipamento.tem_iot && <Chip state="info" label="IoT" size="sm" />}
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg)', marginBottom: 2 }}>{equipamento.modelo_equipamento}</div>
          <div style={{ fontSize: 12, color: 'var(--fg-dim)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ textTransform: 'capitalize' }}>{equipamento.tipo_equipamento}</span>
            <span>{equipamento.idade_equipamento} anos</span>
            <span>{equipamento.historico_sinistros} sinistro(s)</span>
            {ultima && <span className="mono">{ultima.operador_id}</span>}
            {ultima && <span>última aval. {fmtDate(ultima.timestamp)}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <ComingSoon inline><Button kind="ghost" onClick={handleReport}>
            {WIco.doc()}  {reportState === 'generating' ? 'Gerando...' : reportState === 'done' ? 'Pronto ✓' : 'Relatório'}
          </Button></ComingSoon>
          <ComingSoon inline><Button kind="ghost" onClick={() => setShowCallPanel((v) => !v)}>
            {WIco.phone()}  Ligar operador
          </Button></ComingSoon>
          <ComingSoon inline><Button kind="primary" tone="crit" onClick={() => setShowAlertPanel((v) => !v)}>
            {WIco.alert()}  Disparar alerta
          </Button></ComingSoon>
        </div>
      </div>

      {/* Call operator panel */}
      {showCallPanel && ultima && (
        <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--line)', borderRadius: 8, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--fg)' }}>Ligar para operador</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ fontSize: 13, color: 'var(--fg-dim)' }}>
              <strong style={{ color: 'var(--fg)' }}>Operador:</strong> {ultima.operador_id}
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-dim)' }}>
              <strong style={{ color: 'var(--fg)' }}>Score comportamental:</strong> {Math.round(ultima.score_operador_historico)}
            </div>
          </div>
          <div>
            <Button kind="primary" tone="info" onClick={handleCall}>
              {callState === 'connected' ? 'Conectado ✓' : 'Confirmar ligação'}
            </Button>
          </div>
        </div>
      )}

      {/* Alert panel */}
      {showAlertPanel && (
        <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--line)', borderLeft: '3px solid var(--red)', borderRadius: 8, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--fg)' }}>Disparar alerta</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-dim)' }}>Severidade</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setAlertSeverity('yellow')}
                style={{ padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  border: alertSeverity === 'yellow' ? '1px solid var(--amber)' : '1px solid var(--line)',
                  background: alertSeverity === 'yellow' ? 'rgba(245,190,80,0.15)' : 'var(--bg)',
                  color: alertSeverity === 'yellow' ? 'var(--amber)' : 'var(--fg-dim)' }}
              >
                Atenção (amarelo)
              </button>
              <button
                onClick={() => setAlertSeverity('red')}
                style={{ padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  border: alertSeverity === 'red' ? '1px solid var(--red)' : '1px solid var(--line)',
                  background: alertSeverity === 'red' ? 'rgba(255,100,100,0.15)' : 'var(--bg)',
                  color: alertSeverity === 'red' ? 'var(--red)' : 'var(--fg-dim)' }}
              >
                Parada (vermelho)
              </button>
            </div>
          </div>
          <textarea
            value={alertMsg}
            onChange={(e) => setAlertMsg(e.target.value)}
            rows={3}
            style={{ width: '100%', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--line)', background: 'var(--bg)', color: 'var(--fg)', fontSize: 13, fontFamily: 'inherit', resize: 'vertical', outline: 'none' }}
          />
          <div>
            <Button kind="primary" tone="crit" onClick={handleAlert}>
              {alertState === 'sent' ? 'Alerta enviado ✓' : 'Enviar alerta'}
            </Button>
          </div>
        </div>
      )}

      {/* Two-column grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14, alignItems: 'start' }}>

        {/* LEFT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* SHAP decomposition by group */}
          <Card
            title="Decomposição do score · grupos SHAP"
            action={predicao ? <Chip state="neut" label={predicao.modelo_versao} size="sm" /> : undefined}
          >
            {predicao ? (
              <>
                <div style={{ fontSize: 12, color: 'var(--fg-dim)', marginBottom: 14 }}>
                  Score real <strong style={{ color: WTONE[band].fg }}>{Math.round(score)}</strong>
                  {' · '}predito <strong style={{ color: 'var(--fg)' }}>{Math.round(predicao.risco_score_predito)}</strong>
                  {'  ·  '}+ aumenta risco / − reduz (soma dos top 5 fatores por grupo)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {shapGroups.map((g) => (
                    <div key={g.group} style={{ display: 'grid', gridTemplateColumns: '130px 1fr 56px', alignItems: 'center', gap: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {WIco.dot(g.color)}
                        <span style={{ fontSize: 12, color: 'var(--fg-dim)', fontWeight: 600 }}>{g.label}</span>
                      </div>
                      <DivergingBar value={g.value} maxAbs={maxGroupAbs} color={g.color} />
                      <span className="tabular" style={{ fontSize: 13, fontWeight: 800, color: g.value >= 0 ? 'var(--red)' : 'var(--green)', textAlign: 'right' }}>
                        {fmtSigned(g.value)}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--fg-mute)', fontSize: 13 }}>Sem predição SHAP para este equipamento.</div>
            )}
          </Card>

          {/* Top 5 contributing factors */}
          <Card title="Top 5 fatores contribuintes">
            {topFactors.length ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {topFactors.map((c, i) => {
                  const meta = SHAP_GROUP_META[c.group]
                  const color = meta?.color ?? '#A8AEAB'
                  return (
                    <div key={i} style={{ display: 'grid', gridTemplateColumns: '24px 1fr 110px 90px 56px', alignItems: 'center', gap: 10 }}>
                      <span className="tabular" style={{ fontSize: 13, fontWeight: 800, color: 'var(--fg-mute)', textAlign: 'center' }}>{i + 1}</span>
                      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg)' }}>{featureLabel(c.feature)}</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {WIco.dot(color)}
                        <span style={{ fontSize: 11, color: 'var(--fg-dim)' }}>{meta?.label ?? c.group}</span>
                      </div>
                      <div style={{ height: 6, borderRadius: 3, background: 'var(--bg-elev-2)', overflow: 'hidden' }}>
                        <div style={{ width: `${maxFactorAbs ? (Math.abs(c.shap_value) / maxFactorAbs) * 100 : 0}%`, height: '100%', borderRadius: 3, background: color, opacity: 0.75 }} />
                      </div>
                      <span className="tabular" style={{ fontSize: 12, fontWeight: 700, color: c.shap_value >= 0 ? 'var(--red)' : 'var(--green)', textAlign: 'right' }}>
                        {fmtSigned(c.shap_value)}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div style={{ color: 'var(--fg-mute)', fontSize: 13 }}>Sem fatores SHAP disponíveis.</div>
            )}
          </Card>

          {/* Operating conditions */}
          {ultima && (
            <Card title="Condições operacionais · última avaliação">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                <Stat label="Operação" value={cap(ultima.tipo_operacao)} />
                <Stat label="Velocidade" value={`${ultima.velocidade_kmh.toFixed(1)} km/h`} />
                <Stat label="Horas sessão" value={`${ultima.horas_operacao.toFixed(1)} h`} />
                <Stat label="Horário" value={`${ultima.horario_operacao}h${noturno ? ' 🌙' : ''}`} tone={noturno ? 'var(--amber)' : undefined} />
                <Stat label="Clima" value={cap(ultima.condicao_clima)} />
                <Stat label="Vento" value={`${ultima.velocidade_vento.toFixed(0)} km/h`} />
                <Stat label="Temp. ar" value={`${ultima.temperatura_ar.toFixed(0)} °C`} />
                <Stat label="Vibração" value={ultima.vibracao_g != null ? `${ultima.vibracao_g.toFixed(2)} g` : '—'} />
              </div>
            </Card>
          )}
        </div>

        {/* RIGHT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Score history */}
          <Card title={`Histórico de score · ${historico.length} avaliações`}>
            {histScores.length >= 2 ? (
              <>
                <Sparkline data={histScores} color={WTONE[band].fg} height={60} />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                  <span style={{ fontSize: 10, color: 'var(--fg-mute)' }}>{fmtDate(historico[0].ts)}</span>
                  <span style={{ fontSize: 10, color: 'var(--fg-mute)' }}>{fmtDate(historico[historico.length - 1].ts)}</span>
                </div>
                <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
                    <span style={{ fontSize: 10, color: 'var(--fg-mute)', fontWeight: 700 }}>MÍN</span>
                    <span className="tabular" style={{ fontSize: 15, fontWeight: 800, color: WTONE.safe.fg }}>{histMin.toFixed(0)}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 5 }}>
                    <span style={{ fontSize: 10, color: 'var(--fg-mute)', fontWeight: 700 }}>MÁX</span>
                    <span className="tabular" style={{ fontSize: 15, fontWeight: 800, color: WTONE.crit.fg }}>{histMax.toFixed(0)}</span>
                  </div>
                </div>
              </>
            ) : (
              <div style={{ color: 'var(--fg-mute)', fontSize: 13 }}>Histórico insuficiente.</div>
            )}
          </Card>

          {/* Maintenance */}
          {ultima && (
            <Card
              title="Manutenção"
              action={<Chip state={ultima.manutencao_atrasada ? 'crit' : 'safe'} label={ultima.manutencao_atrasada ? 'atrasada' : 'em dia'} size="sm" />}
            >
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <Stat label="Desde últ. (dias)" value={`${ultima.ultima_manutencao_dias}`} tone={ultima.manutencao_atrasada ? 'var(--red)' : undefined} />
                <Stat label="Recom. (dias)" value={`${equipamento.intervalo_manut_recomendado_dias}`} />
                <Stat label="Desde últ. (horas)" value={`${ultima.ultima_manutencao_horas_op.toFixed(0)}`} />
                <Stat label="Recom. (horas)" value={`${equipamento.intervalo_manut_recomendado_horas}`} />
              </div>
              <div style={{ marginTop: 10, fontSize: 12, color: 'var(--fg-dim)' }}>
                Índice de atraso:{' '}
                <strong style={{ color: ultima.atraso_manutencao_pct >= 1 ? 'var(--red)' : 'var(--fg)' }}>
                  {ultima.atraso_manutencao_pct.toFixed(2)}×
                </strong>{' '}
                do limite recomendado
              </div>
            </Card>
          )}

          {/* Current operator */}
          {ultima && (
            <Card title="Operador atual">
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
                <div style={{ width: 48, height: 48, borderRadius: '50%', background: 'var(--bg-elev-2)', border: '2px solid var(--line)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 800, color: 'var(--fg-dim)' }}>
                  {ultima.operador_id.slice(-2)}
                </div>
                <div style={{ flex: 1 }}>
                  <div className="mono" style={{ fontSize: 14, fontWeight: 700, color: 'var(--fg)' }}>{ultima.operador_id}</div>
                  <div style={{ fontSize: 12, color: 'var(--fg-dim)' }}>Score histórico {Math.round(ultima.score_operador_historico)}</div>
                </div>
                {noturno && <Chip state="warn" label="operação noturna" size="sm" />}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <Stat label="Acima do recom." value={`${ultima.pct_velocidade_acima_recomendada.toFixed(0)} %`} />
                <Stat label="Eventos bruscos" value={`${ultima.freq_eventos_bruscos.toFixed(1)}/h`} />
                <Stat label="Oper. noturnas" value={`${ultima.pct_operacoes_noturnas.toFixed(0)} %`} />
                <Stat label="Score comport." value={`${Math.round(ultima.score_operador_historico)}`} />
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}