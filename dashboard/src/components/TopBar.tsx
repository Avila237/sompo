import { useState, useRef, useEffect } from 'react'
import { WTONE } from '../data/mock'
import { WIco } from './Icons'
import { SompoMark } from './shared'
import type { ToneKey } from '../types'

/* ── notification data ── */
interface Notif { sev: ToneKey; title: string; body: string; time: string }

const NOTIFS: Notif[] = [
  { sev: 'crit', title: 'EQ-0042 · Alerta crítico',      body: 'Filtros hidráulicos com 38% de atraso na troca', time: '14:37' },
  { sev: 'crit', title: 'EQ-0023 · Revisão vencida',      body: 'Revisão de 500h atrasada há 28 horas',           time: '12:05' },
  { sev: 'warn', title: 'EQ-0011 · Óleo motor',           body: 'Troca de óleo do motor com 14h de atraso',       time: '10:22' },
  { sev: 'warn', title: 'EQ-0057 · Calibração injetores', body: 'Atraso de 9h na calibração programada',          time: '08:50' },
  { sev: 'info', title: 'Relatório semanal pronto',        body: '28 relatórios disponíveis para download',        time: 'ontem' },
]

/* ── persona config ── */
const PERSONAS: { key: string; label: string; icon: () => JSX.Element }[] = [
  { key: 'sompo',  label: 'Sompo · Seguradora',  icon: WIco.briefcase },
  { key: 'broker', label: 'Corretor',             icon: WIco.people },
  { key: 'tech',   label: 'Técnico manutenção',   icon: WIco.wrench },
]

/* ── TopBar ── */
export default function TopBar({ persona, setPersona }: { persona: string; setPersona: (p: string) => void }) {
  const [showNotifs, setShowNotifs] = useState(false)
  const [unread, setUnread] = useState(NOTIFS.length)
  const dropRef = useRef<HTMLDivElement>(null)

  /* close dropdown on outside click */
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (dropRef.current && !dropRef.current.contains(e.target as Node)) setShowNotifs(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <header style={{
      height: 52, minHeight: 52, display: 'flex', alignItems: 'center',
      justifyContent: 'space-between', padding: '0 20px',
      borderBottom: '1px solid var(--line)', background: 'var(--bg)',
      fontFamily: 'var(--font-ui)', position: 'relative', zIndex: 100,
    }}>

      {/* ── LEFT: brand ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: 'var(--green)', boxShadow: '0 0 6px var(--green)',
        }} />
        <span style={{
          fontWeight: 800, fontSize: 13, letterSpacing: 1.4,
          color: 'var(--fg)',
        }}>SAFEFIELD</span>
        <span style={{
          fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--fg-mute)',
          background: 'var(--bg-elev-3)', borderRadius: 4, padding: '2px 6px',
        }}>v2.4.1</span>
      </div>

      {/* ── CENTER: persona switcher ── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 2,
        background: 'var(--bg-elev-2)', borderRadius: 8, padding: 3,
        border: '1px solid var(--line)',
      }}>
        {PERSONAS.map(p => {
          const active = persona === p.key
          const Icon = p.icon
          return (
            <button key={p.key} onClick={() => setPersona(p.key)} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 14px', borderRadius: 6, border: 'none',
              cursor: 'pointer', fontSize: 12, fontWeight: active ? 600 : 500,
              color: active ? 'var(--fg)' : 'var(--fg-dim)',
              background: active ? 'var(--bg-elev-3)' : 'transparent',
              transition: 'all .15s',
            }}>
              <Icon />{p.label}
            </button>
          )
        })}
      </div>

      {/* ── RIGHT: bell + avatar ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>

        {/* notification bell */}
        <div ref={dropRef} style={{ position: 'relative' }}>
          <button onClick={() => setShowNotifs(v => !v)} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--fg-dim)', position: 'relative', padding: 4,
          }}>
            <WIco.bell />
            {unread > 0 && (
              <span style={{
                width: 7, height: 7, borderRadius: 4,
                background: 'var(--red)', border: '2px solid var(--bg)',
                position: 'absolute', top: 2, right: 2,
              }} />
            )}
          </button>

          {/* dropdown */}
          {showNotifs && (
            <div style={{
              position: 'absolute', top: 40, right: 0, width: 360,
              background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
              borderRadius: 10, overflow: 'hidden',
              boxShadow: '0 12px 32px rgba(0,0,0,.5)',
            }}>
              <div style={{
                padding: '12px 16px', display: 'flex', alignItems: 'center',
                justifyContent: 'space-between', borderBottom: '1px solid var(--line)',
              }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg)' }}>
                  Notificações
                </span>
                <button onClick={() => setUnread(0)} style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  fontSize: 11, color: 'var(--green)', fontWeight: 600,
                }}>Marcar todas</button>
              </div>
              {NOTIFS.map((n, i) => (
                <div key={i} style={{
                  padding: '10px 16px', display: 'flex', gap: 10,
                  borderBottom: i < NOTIFS.length - 1 ? '1px solid var(--line)' : 'none',
                }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%', marginTop: 5, flexShrink: 0,
                    background: WTONE[n.sev].fg,
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg)', marginBottom: 2 }}>
                      {n.title}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--fg-dim)', lineHeight: 1.4 }}>
                      {n.body}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--fg-mute)', marginTop: 4 }}>
                      {n.time}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* user avatar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 14,
            background: 'var(--bg-elev-3)', border: '1px solid var(--line-2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 11, fontWeight: 700, color: 'var(--fg-dim)',
          }}>LA</div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg)', lineHeight: 1.2 }}>
              Luisa Andrade
            </div>
            <div style={{ fontSize: 10, color: 'var(--fg-mute)' }}>
              Analista de riscos
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}