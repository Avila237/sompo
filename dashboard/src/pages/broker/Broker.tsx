import { useState } from 'react'
import { CLIENTS, scoreBand, scoreBandLabel } from '../../data/mock'
import { Card, ScoreBadge, Chip, Trend, SectionHeader } from '../../components/shared'
import { WIco } from '../../components/Icons'
import SideNav from '../../components/SideNav'

const brokerNav = [
  { k: 'clients',   label: 'Clientes',    icon: <WIco.people /> },
  { k: 'quotes',    label: 'Cotações',     icon: <WIco.doc /> },
  { k: 'claims',    label: 'Sinistros',    icon: <WIco.alert /> },
  { k: 'reports',   label: 'Relatórios',   icon: <WIco.chart /> },
]

const sectionMap: Record<string, { title: string; sub: string }> = {
  clients:  { title: 'Meus clientes',   sub: '6 clientes ativos · visão de corretor' },
  quotes:   { title: 'Cotações',        sub: '3 cotações em andamento' },
  claims:   { title: 'Sinistros',       sub: 'Últimos sinistros reportados' },
  reports:  { title: 'Relatórios',      sub: 'Documentos e análises do corretor' },
}

export default function Broker() {
  const [tab, setTab] = useState('clients')
  const sec = sectionMap[tab] ?? sectionMap.clients

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <SideNav items={brokerNav} active={tab} onPick={setTab} />

      <div style={{ flex: 1, overflow: 'auto', padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 18 }}>
        <SectionHeader title={sec.title} sub={sec.sub} />

        {tab === 'clients' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            {CLIENTS.map((c, i) => {
              const band = scoreBand(c.avg)
              return (
                <Card key={i} pad={16}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 700 }}>{c.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--fg-dim)', marginTop: 2 }}>{c.equips} equipamentos</div>
                      </div>
                      <ScoreBadge score={c.avg} size="sm" />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <Chip state={band} label={scoreBandLabel(c.avg)} size="sm" />
                      <span style={{ fontSize: 11, color: c.alerts > 2 ? 'var(--amber)' : 'var(--fg-dim)' }}>
                        {c.alerts} alerta{c.alerts !== 1 ? 's' : ''}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8, borderTop: '1px solid var(--line)' }}>
                      <span className="mono" style={{ fontSize: 14, fontWeight: 700 }}>{c.premium}</span>
                      <Trend delta={c.delta} />
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>
        )}

        {tab === 'quotes' && (
          <Card title="Cotações em andamento">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { client: 'Fazenda Três Pontes', type: 'Renovação', value: 'R$ 142k', status: 'Em análise' },
                { client: 'Grupo Amaggi', type: 'Nova apólice', value: 'R$ 1.82M', status: 'Aguardando docs' },
                { client: 'SLC Agrícola', type: 'Extensão', value: 'R$ 380k', status: 'Aprovada' },
              ].map((q, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: i < 2 ? '1px solid var(--line)' : 'none' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{q.client}</div>
                    <div style={{ fontSize: 11, color: 'var(--fg-dim)', marginTop: 2 }}>{q.type}</div>
                  </div>
                  <span className="mono" style={{ fontSize: 13, fontWeight: 700 }}>{q.value}</span>
                  <Chip state={q.status === 'Aprovada' ? 'safe' : q.status === 'Em análise' ? 'warn' : 'info'} label={q.status} size="sm" />
                </div>
              ))}
            </div>
          </Card>
        )}

        {tab === 'claims' && (
          <Card title="Sinistros recentes">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { equip: 'EQ-0042', desc: 'Colisão com obstáculo — solo instável', date: '12 mai 2026', status: 'Em regulação' },
                { equip: 'EQ-0023', desc: 'Tombamento parcial — declive acentuado', date: '28 abr 2026', status: 'Aprovado' },
                { equip: 'EQ-0118', desc: 'Dano por superaquecimento motor', date: '15 abr 2026', status: 'Concluído' },
              ].map((cl, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: i < 2 ? '1px solid var(--line)' : 'none' }}>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--fg-mute)', fontWeight: 600, width: 70 }}>{cl.equip}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{cl.desc}</div>
                    <div style={{ fontSize: 11, color: 'var(--fg-mute)', marginTop: 2 }}>{cl.date}</div>
                  </div>
                  <Chip state={cl.status === 'Concluído' ? 'safe' : cl.status === 'Aprovado' ? 'info' : 'warn'} label={cl.status} size="sm" />
                </div>
              ))}
            </div>
          </Card>
        )}

        {tab === 'reports' && (
          <Card title="Relatórios do corretor">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { title: 'Resumo mensal — Mai 2026', date: '22 mai', status: 'Pronto' },
                { title: 'Performance UBI — Q1 2026', date: '02 abr', status: 'Pronto' },
                { title: 'Análise de sinistros — 2025', date: '10 jan', status: 'Pronto' },
              ].map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: i < 2 ? '1px solid var(--line)' : 'none' }}>
                  <span style={{ color: 'var(--fg-dim)' }}>{WIco.doc()}</span>
                  <span style={{ flex: 1, fontSize: 13, fontWeight: 600 }}>{r.title}</span>
                  <span className="mono" style={{ fontSize: 11, color: 'var(--fg-mute)' }}>{r.date}</span>
                  <Chip state="safe" label={r.status} size="sm" />
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}