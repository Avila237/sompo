import { type ReactNode, type CSSProperties } from 'react'
import type { ToneKey } from '../types'
import { WTONE, scoreBand } from '../data/mock'

// Card wrapper
export function Card({ title, action, children, style = {}, pad = 18 }: {
  title?: string; action?: ReactNode; children: ReactNode; style?: CSSProperties; pad?: number
}) {
  return (
    <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--line)', borderRadius: 10, ...style }}>
      {(title || action) && (
        <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: 11, color: 'var(--fg-dim)', letterSpacing: 1.2, textTransform: 'uppercase', fontWeight: 700 }}>{title}</div>
          {action}
        </div>
      )}
      <div style={{ padding: pad }}>{children}</div>
    </div>
  )
}

// Status chip
export function Chip({ state = 'neut', label, icon, size = 'md' }: {
  state?: ToneKey; label: string; icon?: ReactNode; size?: 'sm' | 'md'
}) {
  const t = WTONE[state]
  const pad = size === 'sm' ? '2px 7px' : '4px 9px'
  const fs = size === 'sm' ? 10 : 11
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: pad, borderRadius: 4, background: t.bg, color: t.fg, fontWeight: 700, fontSize: fs, letterSpacing: 0.8, textTransform: 'uppercase', border: `1px solid ${t.ring}` }}>
      {icon}{label}
    </span>
  )
}

// Score badge
export function ScoreBadge({ score, size = 'md' }: { score: number; size?: 'xl' | 'lg' | 'md' | 'sm' }) {
  const band = scoreBand(score)
  const color = WTONE[band].fg
  const S = size === 'xl' ? 80 : size === 'lg' ? 48 : size === 'sm' ? 28 : 36
  const FS = size === 'xl' ? 34 : size === 'lg' ? 22 : size === 'sm' ? 13 : 17
  return (
    <div className="tabular" style={{
      width: S, height: S, borderRadius: 8,
      background: WTONE[band].bg, border: `1px solid ${WTONE[band].ring}`,
      color, fontSize: FS, fontWeight: 800, letterSpacing: -0.4,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    }}>{Math.round(score)}</div>
  )
}

// Score bar
export function ScoreBar({ score, height = 8, showLabel = false }: { score: number; height?: number; showLabel?: boolean }) {
  const band = scoreBand(score)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
      <div style={{ flex: 1, height, background: 'var(--bg-elev-2)', borderRadius: height / 2, overflow: 'hidden', position: 'relative' }}>
        <div style={{ position: 'absolute', left: 0, width: '33%', top: 0, bottom: 0, background: 'rgba(90,224,107,0.08)' }} />
        <div style={{ position: 'absolute', left: '33%', width: '33%', top: 0, bottom: 0, background: 'rgba(255,181,38,0.08)' }} />
        <div style={{ position: 'absolute', left: '66%', right: 0, top: 0, bottom: 0, background: 'rgba(232,55,46,0.08)' }} />
        <div style={{ position: 'absolute', left: `calc(${score}% - 3px)`, top: -2, width: 6, height: height + 4, borderRadius: 3, background: WTONE[band].fg, boxShadow: `0 0 8px ${WTONE[band].fg}` }} />
      </div>
      {showLabel && <span className="tabular" style={{ fontSize: 12, fontWeight: 700, color: WTONE[band].fg, width: 28, textAlign: 'right' }}>{Math.round(score)}</span>}
    </div>
  )
}

// Trend indicator (score = risco, up = bad, down = good)
export function Trend({ delta }: { delta: number }) {
  const up = delta > 0, flat = delta === 0
  const color = flat ? 'var(--fg-mute)' : up ? 'var(--red)' : 'var(--green)'
  const arrow = flat ? '—' : up ? '▲' : '▼'
  return (
    <span className="tabular" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color, fontWeight: 700, fontSize: 12 }}>
      <span style={{ fontSize: 9 }}>{arrow}</span>
      {flat ? '0' : (up ? '+' : '') + delta}
    </span>
  )
}

// KPI tile
export function KPITile({ label, value, unit, sub, subTone = 'neut', accent }: {
  label: string; value: string | number; unit?: string; sub?: string; subTone?: ToneKey; accent?: ToneKey
}) {
  const aColor = accent ? WTONE[accent].fg : 'var(--fg)'
  return (
    <div style={{ background: 'var(--bg-elev)', border: '1px solid var(--line)', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
      <div style={{ fontSize: 10, color: 'var(--fg-mute)', letterSpacing: 1.3, textTransform: 'uppercase', fontWeight: 700 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4 }}>
        <span className="tabular" style={{ fontSize: 34, fontWeight: 800, color: aColor, letterSpacing: -1, lineHeight: 1 }}>{value}</span>
        {unit && <span style={{ fontSize: 13, color: 'var(--fg-mute)', fontWeight: 500 }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 11, color: WTONE[subTone].fg, fontWeight: 600, letterSpacing: 0.2 }}>{sub}</div>}
    </div>
  )
}

// Sparkline SVG
export function Sparkline({ data, color = 'var(--green)', height = 40, fill = true }: {
  data: number[]; color?: string; height?: number; fill?: boolean
}) {
  const max = Math.max(...data), min = Math.min(...data)
  const w = 200, h = height
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 4) - 2}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height={h} preserveAspectRatio="none" style={{ display: 'block' }}>
      {fill && <polyline points={`0,${h} ${pts} ${w},${h}`} fill={color} fillOpacity="0.14" stroke="none" />}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// Sompo mark logo
export function SompoMark({ size = 12, muted = false }: { size?: number; muted?: boolean }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 800, fontSize: size, letterSpacing: 1.2, color: muted ? 'var(--fg-dim)' : 'var(--fg)' }}>
      <span style={{ display: 'inline-block', width: size, height: size, borderRadius: 2, background: '#E8372E', position: 'relative' }}>
        <span style={{ position: 'absolute', inset: 2, border: '1.5px solid #0A0C0B', borderRadius: 1 }} />
      </span>
      SOMPO
    </span>
  )
}

// Button with tone
export function Button({ kind = 'secondary', children, onClick, tone = 'neut', style = {}, size = 'md' }: {
  kind?: 'primary' | 'secondary' | 'ghost'; children: ReactNode; onClick?: () => void; tone?: ToneKey; style?: CSSProperties; size?: 'sm' | 'md'
}) {
  const t = WTONE[tone]
  const isPri = kind === 'primary'
  const pad = size === 'sm' ? '6px 10px' : '8px 14px'
  const fs = size === 'sm' ? 12 : 13
  const styles = isPri
    ? { background: t.fg, color: '#0A0C0B', border: `1px solid ${t.fg}` }
    : kind === 'ghost'
    ? { background: 'transparent', color: 'var(--fg)', border: '1px solid var(--line-2)' }
    : { background: t.bg, color: t.fg, border: `1px solid ${t.ring}` }
  return (
    <button onClick={onClick} style={{ padding: pad, borderRadius: 6, fontWeight: 600, fontSize: fs, letterSpacing: 0.2, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, ...styles, ...style }}>
      {children}
    </button>
  )
}

// Section header
export function SectionHeader({ title, sub, actions }: { title: string; sub?: string; actions?: ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 16 }}>
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.4 }}>{title}</div>
        {sub && <div style={{ fontSize: 13, color: 'var(--fg-dim)', marginTop: 4 }}>{sub}</div>}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>{actions}</div>
    </div>
  )
}