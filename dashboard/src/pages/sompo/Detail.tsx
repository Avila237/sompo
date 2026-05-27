import { useState, useMemo } from 'react'
import { EQUIPMENT, HISTORY, CONTRIBS, GROUPS, WTONE, scoreBand, scoreBandLabel } from '../../data/mock'
import type { Equipment } from '../../types'
import { Card, Chip, ScoreBadge, ScoreBar, Trend, Sparkline, Button } from '../../components/shared'
import { WIco } from '../../components/Icons'

const MAINT_ITEMS = [
  { label: 'Troca filtros hidráulicos', status: 'crit' as const, due: '53 h atrás' },
  { label: 'Revisão correia dentada', status: 'warn' as const, due: 'em 12 h' },
  { label: 'Calibração injetores', status: 'safe' as const, due: 'em 48 h' },
  { label: 'Inspeção rodados', status: 'safe' as const, due: 'em 5 d' },
]

const OP_STATS: { label: string; value: string }[] = [
  { label: 'Freadas bruscas', value: '14' },
  { label: 'Velocidade', value: '23 km/h' },
  { label: 'Horas hoje', value: '9.2 h' },
  { label: 'Score comport.', value: '72' },
]

const SHAP_GROUPS = [
  { key: 'env', pts: 30, label: 'Ambiental', color: 'var(--blue)' },
  { key: 'op', pts: 23, label: 'Operador', color: 'var(--amber)' },
  { key: 'maint', pts: 19, label: 'Manutenção', color: 'var(--red)' },
]

const BAR_SEGMENTS = [
  { label: 'base', pts: 16, color: 'var(--fg-mute)' },
  { label: 'env', pts: 30, color: 'var(--blue)' },
  { label: 'op', pts: 23, color: 'var(--amber)' },
  { label: 'maint', pts: 19, color: 'var(--red)' },
]

export default function SompoDetail({ equip, onBack }: { equip: Equipment | null; onBack: () => void }) {
  const eq = equip ?? EQUIPMENT[0]
  const band = scoreBand(eq.score)
  const bandLabel = scoreBandLabel(eq.score)

  const barTotal = useMemo(() => BAR_SEGMENTS.reduce((s, g) => s + g.pts, 0), [])

  const [reportState, setReportState] = useState<null | 'generating' | 'done'>(null)
  const [showCallPanel, setShowCallPanel] = useState(false)
  const [callState, setCallState] = useState<null | 'connected'>(null)
  const [showAlertPanel, setShowAlertPanel] = useState(false)
  const [alertSeverity, setAlertSeverity] = useState<'yellow' | 'red'>('yellow')
  const [alertMsg, setAlertMsg] = useState('Condições adversas detectadas. Retorne à base.')
  const [alertState, setAlertState] = useState<null | 'sent'>(null)

  const handleReport = () => {
    setReportState('generating')
    setTimeout(() => {
      setReportState('done')
      setTimeout(() => setReportState(null), 2000)
    }, 2000)
  }

  const handleCall = () => {
    setCallState('connected')
    setTimeout(() => {
      setCallState(null)
      setShowCallPanel(false)
    }, 2000)
  }

  const handleAlert = () => {
    setAlertState('sent')
    setTimeout(() => {
      setAlertState(null)
      setShowAlertPanel(false)
    }, 2000)
  }

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <button
          onClick={onBack}
          style={{ background: 'none', border: 'none', color: 'var(--fg-dim)', cursor: 'pointer', fontWeight: 600, fontSize: 13, padding: 0, display: 'inline-flex', alignItems: 'center', gap: 4 }}
        >
          ← Ranking
        </button>
        <span style={{ color: 'var(--fg-mute)', fontSize: 13 }}>/</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--fg)' }}>{eq.id}</span>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <ScoreBadge score={eq.score} size="xl" />
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.4 }}>{eq.id}</span>
            <Chip state={band} label={bandLabel} />
            <Trend delta={eq.trend} />
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg)', marginBottom: 2 }}>{eq.model}</div>
          <div style={{ fontSize: 12, color: 'var(--fg-dim)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ textTransform: 'capitalize' }}>{eq.type}</span>
            <span>{eq.client}</span>
            <span>{eq.region}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button kind="ghost" onClick={handleReport}>
            {WIco.doc()}  {reportState === 'generating' ? 'Gerando...' : reportState === 'done' ? 'Pronto ✓' : 'Relatório'}
          </Button>
          <Button kind="ghost" onClick={() => setShowCallPanel((v) => !v)}>
            {WIco.phone()}  Ligar operador
          </Button>
          <Button kind="primary" tone="crit" onClick={() => setShowAlertPanel((v) => !v)}>
            {WIco.alert()}  Disparar alerta
          </Button>
        </div>
      </div>

      {/* Call operator panel */}
      {showCallPanel && (
        <div style={{
          background: 'var(--bg-elev)',
          border: '1px solid var(--line)',
          borderRadius: 8,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--fg)' }}>Ligar para operador</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div style={{ fontSize: 13, color: 'var(--fg)' }}>
              <strong>Operador:</strong> {eq.opName}
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-dim)' }}>
              <strong style={{ color: 'var(--fg)' }}>ID:</strong> {eq.op}
            </div>
            <div style={{ fontSize: 13, color: 'var(--fg-dim)' }}>
              <strong style={{ color: 'var(--fg)' }}>Telefone:</strong> +55 65 9 8842-1907
            </div>
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-dim)', fontStyle: 'italic', background: 'var(--bg)', borderRadius: 6, padding: '10px 12px', border: '1px solid var(--line)' }}>
            "Suspenda a operação. Condições adversas detectadas."
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
        <div style={{
          background: 'var(--bg-elev)',
          border: '1px solid var(--line)',
          borderLeft: '3px solid var(--red)',
          borderRadius: 8,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--fg)' }}>Disparar alerta</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-dim)' }}>Severidade</span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setAlertSeverity('yellow')}
                style={{
                  padding: '8px 16px',
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: alertSeverity === 'yellow' ? '1px solid var(--amber)' : '1px solid var(--line)',
                  background: alertSeverity === 'yellow' ? 'rgba(245,190,80,0.15)' : 'var(--bg)',
                  color: alertSeverity === 'yellow' ? 'var(--amber)' : 'var(--fg-dim)',
                }}
              >
                Atenção (amarelo)
              </button>
              <button
                onClick={() => setAlertSeverity('red')}
                style={{
                  padding: '8px 16px',
                  borderRadius: 6,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: alertSeverity === 'red' ? '1px solid var(--red)' : '1px solid var(--line)',
                  background: alertSeverity === 'red' ? 'rgba(255,100,100,0.15)' : 'var(--bg)',
                  color: alertSeverity === 'red' ? 'var(--red)' : 'var(--fg-dim)',
                }}
              >
                Parada (vermelho)
              </button>
            </div>
          </div>
          <textarea
            value={alertMsg}
            onChange={(e) => setAlertMsg(e.target.value)}
            rows={3}
            style={{
              width: '100%',
              padding: '10px 12px',
              borderRadius: 6,
              border: '1px solid var(--line)',
              background: 'var(--bg)',
              color: 'var(--fg)',
              fontSize: 13,
              fontFamily: 'inherit',
              resize: 'vertical',
              outline: 'none',
            }}
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

          {/* SHAP decomposition */}
          <Card title="Decomposição do score · grupos SHAP">
            {/* Stacked bar */}
            <div style={{ display: 'flex', height: 28, borderRadius: 6, overflow: 'hidden', marginBottom: 16 }}>
              {BAR_SEGMENTS.map((seg) => (
                <div
                  key={seg.label}
                  style={{
                    width: `${(seg.pts / barTotal) * 100}%`,
                    background: seg.color,
                    opacity: 0.85,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 10,
                    fontWeight: 700,
                    color: '#0A0C0B',
                    letterSpacing: 0.5,
                  }}
                >
                  {seg.pts > 10 ? `${seg.pts}` : ''}
                </div>
              ))}
              {/* headroom */}
              <div style={{ flex: 1, background: 'var(--bg-elev-2)' }} />
            </div>

            {/* Group stat cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
              {SHAP_GROUPS.map((g) => (
                <div
                  key={g.key}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--line)',
                    borderRadius: 8,
                    padding: '12px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {WIco.dot(g.color)}
                    <span style={{ fontSize: 11, color: 'var(--fg-dim)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.8 }}>{g.label}</span>
                  </div>
                  <span className="tabular" style={{ fontSize: 22, fontWeight: 800, color: g.color, letterSpacing: -0.5 }}>+{g.pts}</span>
                  <span style={{ fontSize: 10, color: 'var(--fg-mute)' }}>pts</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Top 5 contributing factors */}
          <Card title="Top 5 fatores contribuintes">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {CONTRIBS.map((c, i) => {
                const grp = GROUPS[c.group]
                return (
                  <div key={i} style={{ display: 'grid', gridTemplateColumns: '24px 1fr 100px 80px 60px', alignItems: 'center', gap: 10 }}>
                    <span className="tabular" style={{ fontSize: 13, fontWeight: 800, color: 'var(--fg-mute)', textAlign: 'center' }}>{i + 1}</span>
                    <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg)' }}>{c.label}</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {WIco.dot(grp.color)}
                      <span style={{ fontSize: 11, color: 'var(--fg-dim)' }}>{grp.label}</span>
                    </div>
                    <div style={{ height: 6, borderRadius: 3, background: 'var(--bg-elev-2)', overflow: 'hidden' }}>
                      <div style={{ width: `${c.pct}%`, height: '100%', borderRadius: 3, background: grp.color, opacity: 0.7 }} />
                    </div>
                    <span className="tabular" style={{ fontSize: 12, fontWeight: 700, color: grp.color, textAlign: 'right' }}>{c.val}</span>
                  </div>
                )
              })}
            </div>
          </Card>

          {/* Contextual explanation */}
          <Card
            title="Explicação contextual"
            action={<Chip state="info" label="RAG" icon={WIco.info()} size="sm" />}
          >
            <div style={{ fontSize: 13, lineHeight: 1.75, color: 'var(--fg-dim)' }}>
              O equipamento <strong style={{ color: 'var(--fg)' }}>{eq.id}</strong> apresenta score de risco{' '}
              <strong style={{ color: WTONE[band].fg }}>{eq.score}</strong> ({bandLabel}), impulsionado
              principalmente por{' '}
              <strong style={{ color: 'var(--blue)' }}>condições ambientais adversas</strong> (vento em
              altitude e inclinação do terreno) e{' '}
              <strong style={{ color: 'var(--amber)' }}>fadiga do operador</strong> ({eq.opName}, 9 h sem
              pausa). A <strong style={{ color: 'var(--red)' }}>manutenção atrasada</strong> dos filtros
              hidráulicos agrava o cenário, elevando a probabilidade de sinistro em{' '}
              <strong style={{ color: WTONE[band].fg }}>38%</strong> acima da média da frota.
            </div>
            <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
              {['Boletim INMET 27/05', 'Telemetria CAN-bus', 'Histórico de manutenção'].map((t) => (
                <Chip key={t} state="neut" label={t} size="sm" />
              ))}
            </div>
          </Card>
        </div>

        {/* RIGHT COLUMN */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Score history */}
          <Card title="Histórico de score · 30 dias">
            <Sparkline data={HISTORY} color={WTONE[band].fg} height={60} />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
              <span style={{ fontSize: 10, color: 'var(--fg-mute)' }}>30 d atrás</span>
              <span style={{ fontSize: 10, color: 'var(--fg-mute)' }}>hoje</span>
            </div>
          </Card>

          {/* Maintenance */}
          <Card
            title="Manutenção"
            action={eq.maint === 'atrasada' ? <Chip state="crit" label="atrasada" size="sm" /> : undefined}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {MAINT_ITEMS.map((m, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {WIco.dot(WTONE[m.status].fg)}
                  <span style={{ flex: 1, fontSize: 13, color: 'var(--fg)' }}>{m.label}</span>
                  <span style={{ fontSize: 11, color: WTONE[m.status].fg, fontWeight: 600 }}>{m.due}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Current operator */}
          <Card title="Operador atual">
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
              {/* Avatar circle */}
              <div style={{
                width: 48, height: 48, borderRadius: '50%',
                background: 'var(--bg-elev-2)', border: '2px solid var(--line)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, fontWeight: 800, color: 'var(--fg-dim)',
              }}>
                {eq.opName.charAt(0)}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--fg)' }}>{eq.opName}</div>
                <div style={{ fontSize: 12, color: 'var(--fg-dim)' }}>{eq.op}</div>
              </div>
              <Chip state="warn" label="9h sem pausa" size="sm" />
            </div>

            {/* Operator stats grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {OP_STATS.map((st) => (
                <div
                  key={st.label}
                  style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--line)',
                    borderRadius: 8,
                    padding: '10px 12px',
                  }}
                >
                  <div style={{ fontSize: 10, color: 'var(--fg-mute)', fontWeight: 600, letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 4 }}>{st.label}</div>
                  <div className="tabular" style={{ fontSize: 18, fontWeight: 800, color: 'var(--fg)', letterSpacing: -0.5 }}>{st.value}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}