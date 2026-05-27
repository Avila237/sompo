import { useState } from 'react'
import { MAINT_QUEUE, WTONE, EQUIPMENT } from '../../data/mock'
import { Card, Chip, SectionHeader } from '../../components/shared'
import { WIco } from '../../components/Icons'
import SideNav from '../../components/SideNav'

const techNav = [
  { k: 'queue',     label: 'Fila manutenção',       icon: <WIco.wrench /> },
  { k: 'patterns',  label: 'Padrões pré-dano',      icon: <WIco.chart /> },
  { k: 'recommend', label: 'Recomendações',          icon: <WIco.doc /> },
  { k: 'history',   label: 'Histórico',              icon: <WIco.grid /> },
]

const sectionMap: Record<string, { title: string; sub: string }> = {
  queue:     { title: 'Fila de manutenção',       sub: '6 itens · ordenados por prioridade' },
  patterns:  { title: 'Padrões pré-dano',         sub: 'Padrões operacionais que antecedem falhas — derivados do SHAP' },
  recommend: { title: 'Recomendações',             sub: 'Manutenção preventiva baseada na base de conhecimento' },
  history:   { title: 'Histórico de manutenções',  sub: 'Manutenções declaradas vs intervalos do fabricante' },
}

export default function Technician() {
  const [tab, setTab] = useState('queue')
  const [selected, setSelected] = useState<string | null>(null)
  const sec = sectionMap[tab] ?? sectionMap.queue

  const selectedEquip = selected ? EQUIPMENT.find(e => e.id === selected) : null

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <SideNav items={techNav} active={tab} onPick={setTab} />

      <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 18 }}>
        <SectionHeader title={sec.title} sub={sec.sub} />

        {tab === 'queue' && (
          <>
            <Card title="Manutenções pendentes">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                {/* header */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '28px 90px 1fr 90px 60px 80px', gap: 12,
                  padding: '10px 0', borderBottom: '1px solid var(--line)',
                  fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 1.2, fontWeight: 700,
                  textTransform: 'uppercase' as const,
                }}>
                  <span></span><span>Equip.</span><span>Item</span><span>Prazo</span><span>%</span><span>Sev.</span>
                </div>

                {/* rows */}
                {MAINT_QUEUE.map((m, i) => {
                  const t = WTONE[m.sev]
                  return (
                    <div
                      key={i}
                      onClick={() => setSelected(m.id)}
                      style={{
                        display: 'grid', gridTemplateColumns: '28px 90px 1fr 90px 60px 80px', gap: 12,
                        padding: '12px 0', borderBottom: '1px solid var(--line)', alignItems: 'center', fontSize: 13,
                        cursor: 'pointer',
                        background: selected === m.id ? 'rgba(90,224,107,0.04)' : 'transparent',
                      }}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {WIco.dot(t.fg)}
                      </span>
                      <span className="mono" style={{ fontWeight: 600, color: 'var(--fg)' }}>{m.id}</span>
                      <span style={{ color: 'var(--fg-dim)' }}>{m.item}</span>
                      <span className="tabular" style={{ color: m.sev === 'crit' ? 'var(--red)' : m.sev === 'warn' ? 'var(--amber)' : 'var(--fg-dim)', fontWeight: 600 }}>
                        {m.due}
                      </span>
                      <span className="tabular" style={{ color: m.pct > 0 ? t.fg : 'var(--fg-mute)' }}>
                        {m.pct > 0 ? `${m.pct}%` : '—'}
                      </span>
                      <Chip state={m.sev} label={m.sev === 'crit' ? 'Crítico' : m.sev === 'warn' ? 'Atenção' : 'Normal'} size="sm" />
                    </div>
                  )
                })}
              </div>
            </Card>

            {/* side panel concept: equipment patterns */}
            {selectedEquip && (
              <Card title={`Padrões · ${selectedEquip.id}`}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 13 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--fg-dim)' }}>Modelo</span>
                    <span style={{ fontWeight: 600 }}>{selectedEquip.model}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--fg-dim)' }}>Horas totais</span>
                    <span className="tabular" style={{ fontWeight: 600 }}>{selectedEquip.hours}h</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--fg-dim)' }}>Operador</span>
                    <span style={{ fontWeight: 600 }}>{selectedEquip.opName}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--fg-dim)' }}>Status manutenção</span>
                    <Chip state={selectedEquip.maint === 'atrasada' ? 'crit' : 'safe'} label={selectedEquip.maint} size="sm" />
                  </div>
                  <div style={{
                    marginTop: 8, padding: 12, borderRadius: 8,
                    background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
                    fontSize: 11, color: 'var(--fg-dim)', lineHeight: 1.6,
                  }}>
                    Padrões pré-dano detectados para este equipamento serão listados aqui com base no histórico de sensores e modelo preditivo.
                  </div>
                </div>
              </Card>
            )}
          </>
        )}

        {tab === 'patterns' && (
          <Card title="Padrões identificados">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { pattern: 'RPM elevado (>2400) por +30 min antes de falha mecânica', types: 'Colheitadeiras, Tratores', freq: '12 ocorrências', sev: 'crit' as const },
                { pattern: 'Temperatura do motor acima de 105°C em operações contínuas', types: 'Colheitadeiras', freq: '8 ocorrências', sev: 'warn' as const },
                { pattern: 'Vibração anormal no eixo dianteiro em terreno irregular', types: 'Tratores, Implementos', freq: '6 ocorrências', sev: 'warn' as const },
                { pattern: 'Queda de pressão hidráulica após 800h sem manutenção', types: 'Colheitadeiras', freq: '4 ocorrências', sev: 'info' as const },
              ].map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 0', borderBottom: i < 3 ? '1px solid var(--line)' : 'none' }}>
                  <span style={{ marginTop: 2 }}>{WIco.alert({ s: 14 })}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{p.pattern}</div>
                    <div style={{ fontSize: 11, color: 'var(--fg-mute)', marginTop: 4 }}>Equipamentos: {p.types} · {p.freq}</div>
                  </div>
                  <Chip state={p.sev} label={p.sev === 'crit' ? 'Alto' : p.sev === 'warn' ? 'Médio' : 'Baixo'} size="sm" />
                </div>
              ))}
            </div>
          </Card>
        )}

        {tab === 'recommend' && (
          <Card title="Recomendações ativas">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { desc: 'Antecipar troca de filtro de óleo em colheitadeiras com >1200h', priority: 'Alta', count: 4 },
                { desc: 'Inspeção do sistema hidráulico em tratores com vibração detectada', priority: 'Alta', count: 3 },
                { desc: 'Recalibrar sensores de temperatura em equipamentos EQ-0040 a EQ-0060', priority: 'Média', count: 8 },
                { desc: 'Revisar intervalo de manutenção preventiva para implementos em declive', priority: 'Baixa', count: 5 },
              ].map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: i < 3 ? '1px solid var(--line)' : 'none' }}>
                  <span style={{ color: 'var(--fg-dim)' }}>{WIco.wrench()}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{r.desc}</div>
                    <div style={{ fontSize: 11, color: 'var(--fg-mute)', marginTop: 4 }}>{r.count} equipamentos afetados</div>
                  </div>
                  <Chip state={r.priority === 'Alta' ? 'crit' : r.priority === 'Média' ? 'warn' : 'safe'} label={r.priority} size="sm" />
                </div>
              ))}
            </div>
          </Card>
        )}

        {tab === 'history' && (
          <Card title="Últimas manutenções realizadas">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {/* header */}
              <div style={{
                display: 'grid', gridTemplateColumns: '80px 1fr 110px 120px 90px', gap: 12,
                padding: '10px 0', borderBottom: '1px solid var(--line)',
                fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 1.2, fontWeight: 700,
                textTransform: 'uppercase' as const,
              }}>
                <span>Equip.</span><span>Tipo</span><span>Data</span><span>Técnico</span><span>Status</span>
              </div>

              {[
                { equip: 'EQ-0012', tipo: 'Troca de filtro de óleo', date: '20 mai 2026', tech: 'Carlos S.', status: 'Concluída' },
                { equip: 'EQ-0034', tipo: 'Revisão sistema hidráulico', date: '14 mai 2026', tech: 'Marcos L.', status: 'Concluída' },
                { equip: 'EQ-0051', tipo: 'Calibração de sensores', date: '08 mai 2026', tech: 'Ana P.', status: 'Concluída' },
                { equip: 'EQ-0023', tipo: 'Reparo eixo dianteiro', date: '29 abr 2026', tech: 'Carlos S.', status: 'Concluída' },
                { equip: 'EQ-0042', tipo: 'Manutenção preventiva geral', date: '18 abr 2026', tech: 'Marcos L.', status: 'Parcial' },
              ].map((h, i) => (
                <div key={i} style={{
                  display: 'grid', gridTemplateColumns: '80px 1fr 110px 120px 90px', gap: 12,
                  padding: '12px 0', borderBottom: '1px solid var(--line)', alignItems: 'center', fontSize: 13,
                }}>
                  <span className="mono" style={{ fontWeight: 600 }}>{h.equip}</span>
                  <span style={{ color: 'var(--fg-dim)' }}>{h.tipo}</span>
                  <span className="tabular" style={{ fontSize: 12, color: 'var(--fg-mute)' }}>{h.date}</span>
                  <span style={{ fontSize: 12, fontWeight: 500 }}>{h.tech}</span>
                  <Chip state={h.status === 'Concluída' ? 'safe' : 'warn'} label={h.status} size="sm" />
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}