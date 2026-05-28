import type { ReactNode } from 'react'

/**
 * Sobreposição "Em breve" para telas e botões que ainda usam dados
 * mockados ou não estão implementados.
 *
 * - variante padrão (tela): cobre todo o conteúdo com camada semi-transparente
 * - variante `inline` (botão/elemento): desabilita e exibe uma etiqueta "Em breve"
 */
export function ComingSoon({
  children,
  label = 'Em breve',
  note = 'Esta área está em desenvolvimento',
  inline = false,
}: {
  children: ReactNode
  label?: string
  note?: string
  inline?: boolean
}) {
  if (inline) {
    return (
      <span style={{ position: 'relative', display: 'inline-flex', cursor: 'not-allowed' }}>
        <span
          aria-hidden
          style={{ pointerEvents: 'none', opacity: 0.4, filter: 'grayscale(0.5)', display: 'inline-flex' }}
        >
          {children}
        </span>
        <span
          style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
            justifyContent: 'center', pointerEvents: 'none',
          }}
        >
          <span
            style={{
              fontSize: 9, fontWeight: 800, letterSpacing: 0.8, textTransform: 'uppercase',
              color: 'var(--amber)', background: 'rgba(10,12,11,0.86)',
              border: '1px solid rgba(255,181,38,0.45)', borderRadius: 4,
              padding: '2px 7px', whiteSpace: 'nowrap',
            }}
          >
            {label}
          </span>
        </span>
      </span>
    )
  }

  return (
    <div style={{ position: 'relative', height: '100%', overflow: 'hidden' }}>
      <div
        aria-hidden
        style={{
          height: '100%', overflow: 'hidden', pointerEvents: 'none',
          userSelect: 'none', filter: 'blur(2.5px)', opacity: 0.4,
        }}
      >
        {children}
      </div>
      <div
        style={{
          position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: 'rgba(10,12,11,0.55)',
        }}
      >
        <div
          style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
            padding: '26px 36px', borderRadius: 16,
            background: 'var(--bg-elev)', border: '1px solid var(--line-2)',
            boxShadow: '0 20px 56px rgba(0,0,0,0.55)', textAlign: 'center',
          }}
        >
          <span
            style={{
              fontSize: 11, fontWeight: 800, letterSpacing: 1.6, textTransform: 'uppercase',
              color: 'var(--amber)', background: 'rgba(255,181,38,0.1)',
              border: '1px solid rgba(255,181,38,0.35)', borderRadius: 6,
              padding: '6px 14px',
            }}
          >
            {label}
          </span>
          <div style={{ fontSize: 13, color: 'var(--fg-dim)', maxWidth: 260 }}>{note}</div>
        </div>
      </div>
    </div>
  )
}