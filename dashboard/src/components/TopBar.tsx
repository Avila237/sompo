import { useState, useRef, useEffect, type JSX } from 'react'
import { WTONE } from '../lib/risco'
import { loadAlertas, type Alerta } from '../data/api'
import { WIco } from './Icons'
import { fmtDataHora } from '../lib/formato'

/* ── alertas do sino: GET /alertas, buscados a cada abertura do dropdown ── */
type AlertasState =
  | { status: 'loading' }
  | { status: 'ok'; itens: Alerta[] }
  | { status: 'error'; msg: string }

/* ── persona config ── */
const PERSONAS: { key: string; label: string; icon: () => JSX.Element }[] = [
  { key: 'sompo',  label: 'Sompo · Seguradora',  icon: WIco.briefcase },
  { key: 'broker', label: 'Corretor',             icon: WIco.people },
  { key: 'tech',   label: 'Técnico manutenção',   icon: WIco.wrench },
]

/* ── TopBar ── */
export default function TopBar({ persona, setPersona, perfil, usuario, onSair }: {
  persona: string
  setPersona: (p: string) => void
  /** Perfil da sessao autenticada (operador | gestor | analista). */
  perfil?: string
  /** Usuário que entrou (vem do login). */
  usuario?: string
  onSair?: () => void
}) {
  const [showNotifs, setShowNotifs] = useState(false)
  const [alertas, setAlertas] = useState<AlertasState>({ status: 'loading' })
  const dropRef = useRef<HTMLDivElement>(null)
  const reqId = useRef(0)

  /* A API não guarda estado de "lido", então não há contador de não-lidas:
     o sino só lista o que /alertas devolve no momento da abertura.
     reqId descarta a resposta de uma abertura anterior que chegue atrasada. */
  function toggleNotifs() {
    if (showNotifs) { setShowNotifs(false); return }
    setShowNotifs(true)
    setAlertas({ status: 'loading' })
    const id = ++reqId.current
    loadAlertas()
      .then((itens) => { if (id === reqId.current) setAlertas({ status: 'ok', itens }) })
      .catch((e) => { if (id === reqId.current) setAlertas({ status: 'error', msg: String(e?.message ?? e) }) })
  }

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
          <button
            onClick={toggleNotifs}
            aria-label="Alertas recentes"
            aria-expanded={showNotifs}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--fg-dim)', position: 'relative', padding: 4,
            }}
          >
            <WIco.bell />
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
                  Alertas recentes
                </span>
                <span style={{ fontSize: 10, color: 'var(--fg-mute)' }}>risco médio ou alto</span>
              </div>
              {alertas.status === 'loading' && (
                <div style={{ padding: '14px 16px', fontSize: 12, color: 'var(--fg-mute)' }}>
                  Carregando alertas…
                </div>
              )}
              {alertas.status === 'error' && (
                <div style={{ padding: '14px 16px', fontSize: 12, color: 'var(--red)' }}>
                  Não foi possível carregar os alertas: {alertas.msg}
                </div>
              )}
              {alertas.status === 'ok' && alertas.itens.length === 0 && (
                <div style={{ padding: '14px 16px', fontSize: 12, color: 'var(--fg-mute)' }}>
                  Nenhum alerta no momento.
                </div>
              )}
              {alertas.status === 'ok' && alertas.itens.map((a, i) => (
                <div key={`${a.equipamentoId}-${a.ts}`} style={{
                  padding: '10px 16px', display: 'flex', gap: 10,
                  borderBottom: i < alertas.itens.length - 1 ? '1px solid var(--line)' : 'none',
                }}>
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%', marginTop: 5, flexShrink: 0,
                    background: WTONE[a.sev].fg,
                  }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg)', marginBottom: 2 }}>
                      {a.msg}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--fg-mute)', marginTop: 4 }}>
                      {fmtDataHora(a.ts)}
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
          }}>{(usuario ?? perfil ?? '?').slice(0, 2).toUpperCase()}</div>
          <div>
            {usuario && (
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg)', lineHeight: 1.2 }}>
                {usuario}
              </div>
            )}
            {perfil && (
              <div style={{ fontSize: usuario ? 10 : 12, color: usuario ? 'var(--fg-mute)' : 'var(--fg)' }}>
                Perfil: {perfil}
              </div>
            )}
          </div>
          {onSair && (
            <button
              onClick={onSair}
              title="Encerrar sessão"
              style={{
                marginLeft: 6, padding: '5px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                cursor: 'pointer', background: 'transparent', color: 'var(--fg-dim)',
                border: '1px solid var(--line-2)',
              }}
            >
              Sair
            </button>
          )}
        </div>
      </div>
    </header>
  )
}