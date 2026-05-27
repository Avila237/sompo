import { useState, useMemo } from 'react'
import { WTONE, scoreBand, scoreBandLabel } from '../../data/mock'
import { Card, Chip, ScoreBar, Button, SectionHeader } from '../../components/shared'

/* ── Local: FilterSeg ──────────────────────────────────────────────── */
function FilterSeg({ options, value, onChange }: {
  options: string[]; value: string; onChange: (v: string) => void
}) {
  return (
    <div style={{ display: 'inline-flex', gap: 0, borderRadius: 6, overflow: 'hidden', border: '1px solid var(--line)' }}>
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          style={{
            padding: '6px 14px',
            fontSize: 12,
            fontWeight: 600,
            cursor: 'pointer',
            border: 'none',
            background: value === o ? 'var(--fg)' : 'var(--bg-elev)',
            color: value === o ? 'var(--bg)' : 'var(--fg-dim)',
            letterSpacing: 0.3,
          }}
        >
          {o}
        </button>
      ))}
    </div>
  )
}

/* ── Local: Slider ─────────────────────────────────────────────────── */
interface SliderProps {
  label: string
  value: number
  unit: string
  min: number
  max: number
  step: number
  onChange: (v: number) => void
  warnAt?: number
}

function Slider({ label, value, unit, min, max, step, onChange, warnAt }: SliderProps) {
  const pct = ((value - min) / (max - min)) * 100
  const isWarn = warnAt !== undefined && value >= warnAt
  const trackColor = isWarn ? 'var(--red)' : 'var(--blue)'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-dim)', letterSpacing: 0.3 }}>{label}</span>
        <span
          className="tabular"
          style={{ fontSize: 13, fontWeight: 700, color: isWarn ? 'var(--red)' : 'var(--fg)', letterSpacing: -0.3 }}
        >
          {value}{unit}
        </span>
      </div>
      <div style={{ position: 'relative', height: 20, display: 'flex', alignItems: 'center' }}>
        <div style={{ position: 'absolute', left: 0, right: 0, height: 4, borderRadius: 2, background: 'var(--bg-elev-2)' }} />
        <div style={{ position: 'absolute', left: 0, width: `${pct}%`, height: 4, borderRadius: 2, background: trackColor, opacity: 0.7 }} />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{
            position: 'absolute',
            left: 0,
            width: '100%',
            height: 20,
            opacity: 0,
            cursor: 'pointer',
            margin: 0,
          }}
        />
        <div
          style={{
            position: 'absolute',
            left: `calc(${pct}% - 8px)`,
            width: 16,
            height: 16,
            borderRadius: '50%',
            background: trackColor,
            border: '2px solid var(--bg-elev)',
            boxShadow: `0 0 6px ${trackColor}`,
            pointerEvents: 'none',
          }}
        />
      </div>
    </div>
  )
}

/* ── Local: SoilPicker ─────────────────────────────────────────────── */
type SoilType = 'argiloso' | 'arenoso' | 'misto'

function SoilPicker({ value, onChange }: { value: SoilType; onChange: (v: SoilType) => void }) {
  const opts: SoilType[] = ['argiloso', 'arenoso', 'misto']
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-dim)', letterSpacing: 0.3 }}>Tipo de solo</span>
      <div style={{ display: 'flex', gap: 6 }}>
        {opts.map((o) => (
          <button
            key={o}
            onClick={() => onChange(o)}
            style={{
              flex: 1,
              padding: '8px 0',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              textTransform: 'capitalize',
              border: value === o ? '1px solid var(--blue)' : '1px solid var(--line)',
              background: value === o ? 'rgba(110,185,255,0.1)' : 'var(--bg-elev)',
              color: value === o ? 'var(--blue)' : 'var(--fg-dim)',
            }}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── State shape ───────────────────────────────────────────────────── */
interface Scenario {
  rain: number
  temp: number
  water: number
  soil: SoilType
  speed: number
  hours: number
  delay: number
}

const DEFAULTS: Scenario = {
  rain: 12,
  temp: 28,
  water: 250,
  soil: 'argiloso',
  speed: 14,
  hours: 7,
  delay: 0,
}

const SAVED: (Scenario & { name: string })[] = [
  { name: 'Pulverização · janela ideal', rain: 5, temp: 24, water: 600, soil: 'argiloso' as const, speed: 11, hours: 6, delay: 0 },
  { name: 'Colheita · vento forte', rain: 0, temp: 32, water: 200, soil: 'misto' as const, speed: 18, hours: 10, delay: 8 },
  { name: 'Trator · atraso manutenção', rain: 8, temp: 29, water: 400, soil: 'arenoso' as const, speed: 13, hours: 9, delay: 40 },
  { name: 'Período chuvoso', rain: 35, temp: 22, water: 100, soil: 'argiloso' as const, speed: 9, hours: 5, delay: 5 },
]

/* ── Main component ────────────────────────────────────────────────── */
export default function SompoSimulator() {
  const [target, setTarget] = useState('Equipamento')
  const [s, setS] = useState<Scenario>(DEFAULTS)

  const [showScenarios, setShowScenarios] = useState(false)
  const [loadLabel, setLoadLabel] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<null | 'saving' | 'done'>(null)

  const patch = (partial: Partial<Scenario>) => setS((prev) => ({ ...prev, ...partial }))

  const handleLoadScenario = (sc: Scenario & { name: string }) => {
    const { name: _name, ...values } = sc
    setS(values)
    setShowScenarios(false)
    setLoadLabel('Cenário carregado ✓')
    setTimeout(() => setLoadLabel(null), 2000)
  }

  const handleSave = () => {
    setSaveState('saving')
    setTimeout(() => {
      setSaveState('done')
      setTimeout(() => setSaveState(null), 1500)
    }, 1500)
  }

  /* ── Score calculation ─────────────────────────────────────────── */
  const score = useMemo(() => {
    let sc = 15
    sc += Math.max(0, s.rain - 15) * 1.2
    sc += Math.max(0, s.temp - 30) * 0.8
    sc += Math.max(0, s.speed - 15) * 2
    sc += Math.max(0, s.hours - 8) * 3
    sc += s.delay * 1.1
    sc += (300 - Math.min(s.water, 300)) / 8
    if (s.soil === 'arenoso') sc += 3
    return Math.round(Math.max(2, Math.min(92, sc)) * 10) / 10
  }, [s])

  const band = scoreBand(score)
  const bandLabel = scoreBandLabel(score)
  const tone = WTONE[band]

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 18 }}>

      <SectionHeader
        title="Simulador de cenários"
        actions={
          <>
            <Button kind="ghost" onClick={() => setShowScenarios((v) => !v)}>
              {loadLabel ?? 'Carregar cenário'}
            </Button>
            <Button kind="secondary" tone="info" onClick={handleSave}>
              {saveState === 'saving' ? 'Salvando...' : saveState === 'done' ? 'Salvo ✓' : 'Salvar'}
            </Button>
          </>
        }
      />

      {/* Saved scenarios panel */}
      {showScenarios && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 10,
        }}>
          {SAVED.map((sc) => (
            <button
              key={sc.name}
              onClick={() => handleLoadScenario(sc)}
              style={{
                background: 'var(--bg-elev)',
                border: '1px solid var(--line)',
                borderRadius: 8,
                padding: 16,
                cursor: 'pointer',
                textAlign: 'left',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                transition: 'border-color 0.15s',
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--blue)' }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--line)' }}
            >
              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--fg)' }}>{sc.name}</span>
              <span style={{ fontSize: 11, color: 'var(--fg-dim)' }}>
                Chuva {sc.rain}mm · {sc.temp}°C · Solo {sc.soil} · {sc.speed}km/h · {sc.hours}h · Atraso {sc.delay}d
              </span>
            </button>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: 14, alignItems: 'start' }}>

        {/* LEFT: Parameters */}
        <Card title="Parâmetros do cenário">
          {/* Target selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-dim)' }}>Alvo</span>
            <FilterSeg options={['Equipamento', 'Frota', 'Região']} value={target} onChange={setTarget} />
          </div>

          {/* Sliders grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <Slider label="Precipitação 72 h" value={s.rain} unit=" mm" min={0} max={120} step={1} onChange={(v) => patch({ rain: v })} warnAt={40} />
            <Slider label="Temperatura" value={s.temp} unit="°C" min={10} max={50} step={0.5} onChange={(v) => patch({ temp: v })} warnAt={35} />
            <Slider label="Distância à água" value={s.water} unit=" m" min={0} max={500} step={10} onChange={(v) => patch({ water: v })} warnAt={undefined} />
            <SoilPicker value={s.soil} onChange={(v) => patch({ soil: v })} />
            <Slider label="Velocidade média" value={s.speed} unit=" km/h" min={0} max={40} step={0.5} onChange={(v) => patch({ speed: v })} warnAt={20} />
            <Slider label="Horas de operação" value={s.hours} unit=" h" min={0} max={18} step={0.5} onChange={(v) => patch({ hours: v })} warnAt={10} />
            <Slider label="Atraso de manutenção" value={s.delay} unit=" d" min={0} max={60} step={1} onChange={(v) => patch({ delay: v })} warnAt={14} />
          </div>
        </Card>

        {/* RIGHT column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Predicted score */}
          <Card title="Score previsto">
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '12px 0 8px' }}>
              {/* Huge score number */}
              <div
                className="tabular"
                style={{
                  fontSize: 120,
                  fontWeight: 900,
                  lineHeight: 1,
                  letterSpacing: -4,
                  color: tone.fg,
                  textShadow: `0 0 40px ${tone.fg}, 0 0 80px ${tone.ring}`,
                }}
              >
                {Math.round(score)}
              </div>
              <Chip state={band} label={bandLabel} />
              <div style={{ width: '100%', padding: '0 8px' }}>
                <ScoreBar score={score} height={10} showLabel />
              </div>
              <p style={{ fontSize: 12, color: 'var(--fg-dim)', textAlign: 'center', lineHeight: 1.6, marginTop: 4, padding: '0 8px' }}>
                Com os parâmetros selecionados, o modelo prevê risco <strong style={{ color: tone.fg }}>{bandLabel.toLowerCase()}</strong>.
                {score > 66 && ' Recomenda-se ação preventiva imediata.'}
                {score <= 33 && ' Condições dentro da faixa de segurança.'}
                {score > 33 && score <= 66 && ' Monitoramento contínuo recomendado.'}
              </p>
            </div>
          </Card>

          {/* Financial impact */}
          <Card title="Impacto financeiro">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <div style={{ fontSize: 10, color: 'var(--fg-mute)', fontWeight: 700, letterSpacing: 1.2, textTransform: 'uppercase', marginBottom: 4 }}>Exposição</div>
                <div className="tabular" style={{ fontSize: 28, fontWeight: 800, color: 'var(--fg)', letterSpacing: -0.8 }}>
                  R$ {(score * 1.8).toFixed(0)}k
                </div>
              </div>
              <div style={{ borderTop: '1px solid var(--line)', paddingTop: 14 }}>
                <div style={{ fontSize: 10, color: 'var(--fg-mute)', fontWeight: 700, letterSpacing: 1.2, textTransform: 'uppercase', marginBottom: 4 }}>Δ Prêmio</div>
                <div className="tabular" style={{ fontSize: 28, fontWeight: 800, color: score > 50 ? 'var(--red)' : 'var(--green)', letterSpacing: -0.8 }}>
                  {score > 50 ? '+' : '−'}R$ {Math.abs(Math.round((score - 50) * 0.42))}k
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}