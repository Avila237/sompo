import type { ReactNode } from 'react'
import { SompoMark } from './shared'

export interface NavItem {
  k: string
  label: string
  icon: ReactNode
  count?: string | number
}

interface Props {
  items: NavItem[]
  active: string
  onPick: (k: string) => void
}

export default function SideNav({ items, active, onPick }: Props) {
  return (
    <nav style={{
      width: 200, minWidth: 200, height: '100%',
      borderRight: '1px solid var(--line)',
      background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'var(--font-ui)',
    }}>
      {/* section label */}
      <div style={{
        padding: '18px 10px 8px',
        fontSize: 10, fontWeight: 700, letterSpacing: 1.2,
        textTransform: 'uppercase', color: 'var(--fg-mute)',
      }}>DASHBOARD</div>

      {/* nav items */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2, padding: '0 8px' }}>
        {items.map(item => {
          const isActive = item.k === active
          return (
            <button
              key={item.k}
              onClick={() => onPick(item.k)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '9px 10px', borderRadius: 6,
                border: 'none', cursor: 'pointer',
                background: isActive ? 'rgba(90,224,107,0.08)' : 'transparent',
                color: isActive ? 'var(--green)' : 'var(--fg-dim)',
                fontSize: 13, fontWeight: isActive ? 600 : 500,
                textAlign: 'left', width: '100%',
                transition: 'all .15s',
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
                {item.icon}
              </span>
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.count !== undefined && (
                <span style={{
                  fontSize: 10, fontFamily: 'var(--font-mono)',
                  color: 'var(--fg-mute)',
                  padding: '2px 6px',
                  border: '1px solid var(--line-2)',
                  borderRadius: 3,
                }}>{item.count}</span>
              )}
            </button>
          )
        })}
      </div>

      {/* bottom: "Respaldado por" + Sompo mark */}
      <div style={{
        padding: '10px', borderTop: '1px solid var(--line)',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <span style={{ fontSize: 10, color: 'var(--fg-mute)' }}>Respaldado por</span>
        <SompoMark size={9} />
      </div>
    </nav>
  )
}