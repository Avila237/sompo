import { useState, type ReactNode } from 'react'
import { WTONE } from '../../data/mock'
import type { ToneKey } from '../../types'
import { Card, Button, SectionHeader, Chip } from '../../components/shared'
import { WIco } from '../../components/Icons'

interface ReportDef {
  icon: () => ReactNode
  title: string
  desc: string
  tone: ToneKey
}

const REPORTS: ReportDef[] = [
  { icon: WIco.chart,     title: 'Carteira completa',       desc: 'Score, tendência e SHAP de todos os equipamentos',              tone: 'info' },
  { icon: WIco.bell,      title: 'Alertas e incidentes',    desc: 'Histórico de alertas, ações tomadas, tempo de resposta',        tone: 'crit' },
  { icon: WIco.wrench,    title: 'Manutenção preventiva',   desc: 'Atrasos, custos evitados, cronograma',                          tone: 'warn' },
  { icon: WIco.people,    title: 'Performance operadores',  desc: 'Score comportamental, fadiga, eventos bruscos',                 tone: 'warn' },
  { icon: WIco.briefcase, title: 'UBI e precificação',      desc: 'Impacto financeiro, Δ prêmio por cliente',                      tone: 'safe' },
  { icon: WIco.doc,       title: 'Trilha de auditoria',     desc: 'Todas as ações do sistema, modelos, versões',                   tone: 'neut' },
]

interface RecentReport {
  title: string
  date: string
  tone: ToneKey
  status: string
}

const RECENT: RecentReport[] = [
  { title: 'Carteira completa — Maio 2026',       date: '22 mai 2026', tone: 'safe', status: 'Pronto' },
  { title: 'Alertas e incidentes — Semana 21',     date: '19 mai 2026', tone: 'safe', status: 'Pronto' },
  { title: 'Manutenção preventiva — Q2 2026',      date: '15 mai 2026', tone: 'safe', status: 'Pronto' },
  { title: 'UBI e precificação — Abr 2026',        date: '02 mai 2026', tone: 'info', status: 'Em revisão' },
]

export default function SompoReports() {
  const [generating, setGenerating] = useState<string | null>(null)

  function handleGenerate(title: string) {
    setGenerating(title)
    setTimeout(() => setGenerating(null), 1500)
  }

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <SectionHeader title="Relatórios e auditoria" sub="Gere relatórios consolidados para governança e compliance" />

      {/* Report cards grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {REPORTS.map((r) => {
          const t = WTONE[r.tone]
          return (
            <div key={r.title} style={{
              background: 'var(--bg-elev)', border: '1px solid var(--line)', borderRadius: 10,
              padding: '20px 18px', display: 'flex', flexDirection: 'column', gap: 12,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: t.bg, border: `1px solid ${t.ring}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', color: t.fg,
                }}>
                  {r.icon()}
                </div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>{r.title}</div>
              </div>
              <div style={{ fontSize: 12, color: 'var(--fg-dim)', lineHeight: 1.5, flex: 1 }}>{r.desc}</div>
              <Button
                kind="secondary"
                tone={r.tone}
                size="sm"
                onClick={() => handleGenerate(r.title)}
              >
                {WIco.download()}
                {generating === r.title ? 'Gerando…' : 'Gerar'}
              </Button>
            </div>
          )
        })}
      </div>

      {/* Recent reports */}
      <Card title="Relatórios recentes">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {RECENT.map((r, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px 0',
              borderBottom: i < RECENT.length - 1 ? '1px solid var(--line)' : 'none',
              fontSize: 13,
            }}>
              <span style={{ display: 'flex', alignItems: 'center', color: 'var(--fg-dim)' }}>
                {WIco.doc()}
              </span>
              <span style={{ flex: 1, fontWeight: 600 }}>{r.title}</span>
              <span style={{ fontSize: 11, color: 'var(--fg-mute)', fontFamily: 'var(--font-mono)' }}>{r.date}</span>
              <Chip state={r.tone} label={r.status} size="sm" />
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}