import { useState, useMemo, useEffect } from 'react'
import { EQUIPMENT, REGIONS, HISTORY, WTONE, scoreBand } from '../../data/mock'
import type { Equipment } from '../../types'
import type { ToneKey } from '../../types'
import { Card, ScoreBadge, Trend, KPITile, SectionHeader, Button } from '../../components/shared'
import { WIco } from '../../components/Icons'

/* -- FilterSeg helper (inline, same pattern as Ranking) ---- */

function FilterSeg({
  value,
  onChange,
  opts,
}: {
  value: string
  onChange: (v: string) => void
  opts: Array<{ k: string; l: string; dot?: string }>
}) {
  return (
    <div style={{ display: 'inline-flex', border: '1px solid var(--line)', borderRadius: 6, overflow: 'hidden' }}>
      {opts.map((o) => {
        const active = value === o.k
        return (
          <button
            key={o.k}
            onClick={() => onChange(o.k)}
            style={{
              padding: '6px 12px',
              border: 'none',
              borderRight: '1px solid var(--line)',
              background: active ? 'var(--line)' : 'transparent',
              color: active ? 'var(--fg)' : 'var(--fg-mute)',
              fontWeight: 600,
              fontSize: 12,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {o.dot && (
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: o.dot,
                  flexShrink: 0,
                }}
              />
            )}
            {o.l}
          </button>
        )
      })}
    </div>
  )
}

/* -- Brazil map sub-component ------------------------------ */

function BrazilMap({ regions, onPickRegion }: { regions: typeof REGIONS; onPickRegion?: (r: typeof REGIONS[number]) => void }) {
  const highRisk = regions.reduce((a, b) => (b.avg > a.avg ? b : a), regions[0])
  return (
    <svg viewBox="0 0 420 420" width="100%" height="100%" style={{ display: 'block' }}>
      {/* simplified Brazil outline */}
      <path
        d="M160,40 C120,50 90,80 70,110 C50,140 40,180 45,220 C50,260 70,300 100,330
           C130,360 170,380 210,390 C250,380 290,360 310,340 C340,310 360,270 365,230
           C370,190 360,150 340,120 C320,90 290,60 250,45 C220,35 190,35 160,40 Z"
        fill="rgba(255,255,255,0.03)"
        stroke="var(--line)"
        strokeWidth="1.5"
      />

      {/* region dots */}
      {regions.map((r) => {
        const cx = r.x * 420
        const cy = r.y * 420
        const radius = Math.sqrt(r.count) * 2.4 + 4
        const band = scoreBand(r.avg)
        const color = WTONE[band].fg
        return (
          <g
            key={r.name}
            style={{ cursor: onPickRegion ? 'pointer' : 'default' }}
            onClick={() => onPickRegion?.(r)}
          >
            <circle cx={cx} cy={cy} r={radius + 4} fill={color} fillOpacity="0.12" />
            <circle cx={cx} cy={cy} r={radius} fill={color} fillOpacity="0.85" />
            <title>{r.name} — score {r.avg}, {r.count} equip.</title>
          </g>
        )
      })}

      {/* callout for highest-risk region */}
      {(() => {
        const cx = highRisk.x * 420
        const cy = highRisk.y * 420
        const lx = Math.min(cx + 30, 340)
        const ly = Math.max(cy - 30, 24)
        return (
          <g>
            <line x1={cx} y1={cy} x2={lx} y2={ly} stroke="var(--fg-dim)" strokeWidth="0.7" strokeDasharray="3,2" />
            <rect x={lx - 2} y={ly - 14} width={100} height={18} rx={3} fill="var(--bg-elev)" stroke="var(--line)" strokeWidth="0.7" />
            <text x={lx + 4} y={ly - 1} fill={WTONE.crit.fg} fontSize="10" fontWeight="700" fontFamily="Inter Tight">
              {highRisk.name} · {highRisk.avg}
            </text>
          </g>
        )
      })()}

      {/* legend */}
      <g transform="translate(290, 370)">
        <circle cx="0" cy="0" r="4" fill={WTONE.safe.fg} />
        <text x="8" y="3" fill="var(--fg-dim)" fontSize="9" fontFamily="Inter Tight">Baixo</text>
        <circle cx="46" cy="0" r="4" fill={WTONE.warn.fg} />
        <text x="54" y="3" fill="var(--fg-dim)" fontSize="9" fontFamily="Inter Tight">Médio</text>
        <circle cx="96" cy="0" r="4" fill={WTONE.crit.fg} />
        <text x="104" y="3" fill="var(--fg-dim)" fontSize="9" fontFamily="Inter Tight">Alto</text>
      </g>
    </svg>
  )
}

/* -- Trend chart sub-component ----------------------------- */

function TrendChart({ data, period }: { data: number[]; period: string }) {
  const W = 480, H = 200, PAD = { t: 16, r: 12, b: 24, l: 12 }
  const cw = W - PAD.l - PAD.r
  const ch = H - PAD.t - PAD.b
  const max = 100, min = 0
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
        {/* risk band backgrounds */}
        <rect x={PAD.l} y={bandY(100)} width={cw} height={bandY(66) - bandY(100)} fill="rgba(232,55,46,0.05)" />
        <rect x={PAD.l} y={bandY(66)} width={cw} height={bandY(33) - bandY(66)} fill="rgba(255,181,38,0.05)" />
        <rect x={PAD.l} y={bandY(33)} width={cw} height={bandY(0) - bandY(33)} fill="rgba(90,224,107,0.05)" />

        {/* threshold lines */}
        <line x1={PAD.l} y1={bandY(33)} x2={W - PAD.r} y2={bandY(33)} stroke="rgba(90,224,107,0.2)" strokeWidth="0.7" strokeDasharray="4,3" />
        <line x1={PAD.l} y1={bandY(66)} x2={W - PAD.r} y2={bandY(66)} stroke="rgba(255,181,38,0.2)" strokeWidth="0.7" strokeDasharray="4,3" />

        {/* data polyline */}
        <polyline points={pts} fill="none" stroke={WTONE[scoreBand(avg)].fg} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {/* last point highlight */}
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

        {/* x-axis labels */}
        <text x={PAD.l} y={H - 4} fill="var(--fg-mute)" fontSize="9" fontFamily="Inter Tight">1</text>
        <text x={PAD.l + cw / 2} y={H - 4} fill="var(--fg-mute)" fontSize="9" fontFamily="Inter Tight" textAnchor="middle">{Math.ceil(data.length / 2)}</text>
        <text x={W - PAD.r} y={H - 4} fill="var(--fg-mute)" fontSize="9" fontFamily="Inter Tight" textAnchor="end">{data.length} d</text>
      </svg>

      {/* stats row */}
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

/* -- Alerts list data -------------------------------------- */

const ALERTS: Array<{ sev: ToneKey; msg: string; time: string }> = [
  { sev: 'crit', msg: 'EQ-0042 · Motor 98 °C — limite excedido', time: '14:37' },
  { sev: 'crit', msg: 'EQ-0023 · Vento 72 km/h em altitude', time: '14:22' },
  { sev: 'warn', msg: 'EQ-0118 · Filtros atrasados 38 %', time: '13:55' },
  { sev: 'warn', msg: 'EQ-0057 · Operador sem pausa > 8 h', time: '13:41' },
  { sev: 'warn', msg: 'EQ-0073 · Inclinação 6.1 % acima do limite', time: '13:12' },
  { sev: 'info', msg: 'EQ-0011 · Revisão 500 h agendada', time: '12:58' },
  { sev: 'safe', msg: 'EQ-0095 · Score normalizado', time: '12:40' },
]

/* -- Main component ---------------------------------------- */

export default function SompoOverview({
  onPickEquip,
  onNav,
}: {
  onPickEquip: (e: Equipment) => void
  onNav: (screen: string) => void
}) {
  const [period, setPeriod] = useState<'30d' | '60d' | '90d'>('30d')
  const [showFilters, setShowFilters] = useState(false)
  const [riskFilter, setRiskFilter] = useState<'all' | 'safe' | 'warn' | 'crit'>('all')
  const [typeFilter, setTypeFilter] = useState<'all' | 'colheitadeira' | 'trator' | 'implemento'>('all')
  const [exporting, setExporting] = useState<null | 'working' | 'done'>(null)

  const highRiskCount = EQUIPMENT.filter((e) => scoreBand(e.score) === 'crit').length

  /* Filtered top 5 */
  const top5 = useMemo(() => {
    let list = [...EQUIPMENT]
    if (riskFilter !== 'all') list = list.filter((e) => scoreBand(e.score) === riskFilter)
    if (typeFilter !== 'all') list = list.filter((e) => e.type === typeFilter)
    return list.sort((a, b) => b.score - a.score).slice(0, 5)
  }, [riskFilter, typeFilter])

  /* Filtered alerts */
  const filteredAlerts = useMemo(() => {
    if (riskFilter === 'all') return ALERTS
    return ALERTS.filter((a) => a.sev === riskFilter)
  }, [riskFilter])

  /* Export button handler */
  const handleExport = () => {
    if (exporting !== null) return
    setExporting('working')
  }

  useEffect(() => {
    if (exporting === 'working') {
      const t = setTimeout(() => setExporting('done'), 1500)
      return () => clearTimeout(t)
    }
    if (exporting === 'done') {
      const t = setTimeout(() => setExporting(null), 1500)
      return () => clearTimeout(t)
    }
  }, [exporting])

  /* Alert click handler */
  const handleAlertClick = (msg: string) => {
    const match = msg.match(/EQ-\d+/)
    if (!match) return
    const eq = EQUIPMENT.find((e) => e.id === match[0])
    if (eq) onPickEquip(eq)
  }

  /* Clear filters */
  const handleClearFilters = () => {
    setRiskFilter('all')
    setTypeFilter('all')
  }

  const filtersActive = riskFilter !== 'all' || typeFilter !== 'all'

  /* Export button label */
  const exportLabel = exporting === 'working' ? 'Exportando...' : exporting === 'done' ? 'Pronto ✓' : 'Exportar'

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* --- Header --- */}
      <SectionHeader
        title="Visão geral da carteira"
        sub="Safra 2025/26 · 338 equipamentos monitorados · atualização há 14 s"
        actions={
          <>
            <Button kind="ghost" onClick={() => setShowFilters((v) => !v)}>{WIco.filter()} Filtros</Button>
            <Button
              kind="ghost"
              onClick={handleExport}
              style={exporting === 'done' ? { color: '#5AE06B', borderColor: '#5AE06B' } : {}}
            >
              {WIco.download()} {exportLabel}
            </Button>
            <Button kind="primary" tone="safe" onClick={() => onNav('simulator')}>Nova análise</Button>
          </>
        }
      />

      {/* --- Filter panel --- */}
      {showFilters && (
        <div style={{
          background: 'var(--bg-elev)',
          border: '1px solid var(--line)',
          borderRadius: 10,
          padding: '14px 18px',
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          flexWrap: 'wrap',
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
              padding: '6px 14px',
              borderRadius: 6,
              border: '1px solid var(--line)',
              background: filtersActive ? 'var(--line)' : 'transparent',
              color: filtersActive ? 'var(--fg)' : 'var(--fg-mute)',
              fontWeight: 600,
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            Limpar
          </button>
        </div>
      )}

      {/* --- KPIs --- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10 }}>
        <KPITile label="Equipamentos" value={338} sub="12 polos ativos" />
        <KPITile label="Score médio" value={34} unit="/100" accent="safe" sub="Baixo risco global" subTone="safe" />
        <KPITile label="Risco alto" value={highRiskCount} accent="crit" sub={`${((highRiskCount / 338) * 100).toFixed(1)} % da frota`} subTone="crit" />
        <KPITile label="Alertas ativos" value={14} accent="warn" sub="5 críticos" subTone="warn" />
        <KPITile label="Prêmio em risco" value="R$ 4.8 M" sub="+12 % vs. mês anterior" subTone="crit" />
      </div>

      {/* --- Map + Trend --- */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 14 }}>
        <Card title="Distribuição geográfica · 12 polos" pad={12}>
          <div style={{ height: 340 }}>
            <BrazilMap regions={REGIONS} />
          </div>
        </Card>

        <Card
          title="Evolução do score médio"
          action={
            <div style={{ display: 'flex', gap: 4 }}>
              {(['30d', '60d', '90d'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  style={{
                    padding: '3px 10px',
                    borderRadius: 4,
                    border: '1px solid var(--line)',
                    background: period === p ? 'var(--line)' : 'transparent',
                    color: period === p ? 'var(--fg)' : 'var(--fg-mute)',
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: 'pointer',
                    }}
                >
                  {p}
                </button>
              ))}
            </div>
          }
          pad={16}
        >
          <TrendChart data={HISTORY} period={period} />
        </Card>
      </div>

      {/* --- Top 5 + Alerts --- */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 14 }}>
        {/* top 5 high-risk */}
        <Card title="Top 5 · risco mais alto" pad={0}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 18 }}>
            {top5.map((eq) => (
              <button
                key={eq.id}
                onClick={() => onPickEquip(eq)}
                style={{
                  background: 'var(--bg-elev-2)', border: '1px solid var(--line)', borderRadius: 8,
                  padding: '10px 12px',
                  display: 'grid', gridTemplateColumns: 'auto 1.5fr 1.2fr 80px 60px',
                  gap: 12, alignItems: 'center',
                  cursor: 'pointer', color: 'var(--fg)',
                }}
              >
                <ScoreBadge score={eq.score} size="sm" />
                <div style={{ textAlign: 'left', minWidth: 0 }}>
                  <div className="mono" style={{ fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 0.5, fontWeight: 600 }}>{eq.id}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{eq.model}</div>
                </div>
                <div style={{ textAlign: 'left', fontSize: 12, color: 'var(--fg-dim)' }}>
                  {eq.client}
                  <div className="mono" style={{ fontSize: 10, color: 'var(--fg-mute)' }}>{eq.region}</div>
                </div>
                <Trend delta={eq.trend} />
                <span className="mono" style={{ fontSize: 11, color: 'var(--fg-mute)', textAlign: 'right' }}>{eq.lastAlert}</span>
              </button>
            ))}
            {top5.length === 0 && (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--fg-mute)', fontSize: 13 }}>
                Nenhum equipamento nesta faixa.
              </div>
            )}
          </div>
        </Card>

        {/* active alerts */}
        <Card title="Alertas ativos" pad={0}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: 18 }}>
            {filteredAlerts.map((a, i) => (
              <button
                key={i}
                onClick={() => handleAlertClick(a.msg)}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  padding: '2px 0 10px',
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