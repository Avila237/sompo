import { CLIENTS } from '../../data/mock'
import { Card, ScoreBadge, Trend, KPITile, SectionHeader } from '../../components/shared'

export default function SompoUBI() {
  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <SectionHeader title="UBI · Usage-Based Insurance" sub="Ajuste de prêmio baseado no comportamento real da frota — dados dos últimos 90 dias" />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10 }}>
        <KPITile label="Prêmio base" value="R$ 6.2" unit="M" sub="Vigência 2025/26" subTone="neut" />
        <KPITile label="Ajuste UBI" value="+2.4" unit="%" accent="crit" sub="Comportamento frota" subTone="crit" />
        <KPITile label="Desconto prevenção" value="−0.8" unit="%" accent="safe" sub="47 incidentes evitados" subTone="safe" />
        <KPITile label="Prêmio ajustado" value="R$ 6.3" unit="M" accent="warn" sub="+R$ 98k vs. base" subTone="warn" />
      </div>

      <Card title="Clientes · impacto no prêmio">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '1.5fr 90px 80px 80px 110px 100px', gap: 12,
            padding: '10px 0', borderBottom: '1px solid var(--line)',
            fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 1.2, fontWeight: 700, textTransform: 'uppercase' as const,
          }}>
            <span>Cliente</span><span>Equipamentos</span><span>Score</span><span>Alertas</span><span>Prêmio</span><span>Δ Prêmio</span>
          </div>
          {CLIENTS.map((c, i) => (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '1.5fr 90px 80px 80px 110px 100px', gap: 12,
              padding: '12px 0', borderBottom: '1px solid var(--line)', alignItems: 'center', fontSize: 13,
            }}>
              <span style={{ fontWeight: 600 }}>{c.name}</span>
              <span className="tabular" style={{ color: 'var(--fg-dim)' }}>{c.equips}</span>
              <ScoreBadge score={c.avg} size="sm" />
              <span className="tabular" style={{ color: c.alerts > 2 ? 'var(--amber)' : 'var(--fg-dim)' }}>{c.alerts}</span>
              <span className="mono" style={{ fontWeight: 600 }}>{c.premium}</span>
              <Trend delta={c.delta} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}