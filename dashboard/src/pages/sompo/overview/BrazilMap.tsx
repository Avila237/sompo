import { WTONE, faixaDaMedia } from '../../../lib/risco'
import type { Region } from '../../../types'

/* -- Brazil map sub-component ------------------------------ */

export function BrazilMap({ regions, onPickRegion }: { regions: Region[]; onPickRegion?: (r: Region) => void }) {
  const highRisk = regions.length
    ? regions.reduce((a, b) => (b.avg > a.avg ? b : a), regions[0])
    : null
  return (
    <svg viewBox="0 0 420 420" width="100%" height="100%" style={{ display: 'block' }}>
      <path
        d="M160,40 C120,50 90,80 70,110 C50,140 40,180 45,220 C50,260 70,300 100,330
           C130,360 170,380 210,390 C250,380 290,360 310,340 C340,310 360,270 365,230
           C370,190 360,150 340,120 C320,90 290,60 250,45 C220,35 190,35 160,40 Z"
        fill="rgba(255,255,255,0.03)"
        stroke="var(--line)"
        strokeWidth="1.5"
      />

      {regions.map((r) => {
        const cx = r.x * 420
        const cy = r.y * 420
        const radius = Math.sqrt(r.count) * 2.4 + 4
        const band = faixaDaMedia(r.avg)
        const color = WTONE[band].fg
        return (
          <g
            key={r.name}
            style={{ cursor: onPickRegion ? 'pointer' : 'default' }}
            onClick={() => onPickRegion?.(r)}
          >
            <circle cx={cx} cy={cy} r={radius + 4} fill={color} fillOpacity="0.12" />
            <circle cx={cx} cy={cy} r={radius} fill={color} fillOpacity="0.85" />
            <title>{r.name} — score {r.avg}, {r.count} equip.</title>
          </g>
        )
      })}

      {highRisk && (() => {
        const cx = highRisk.x * 420
        const cy = highRisk.y * 420
        const lx = Math.min(cx + 30, 320)
        const ly = Math.max(cy - 30, 24)
        return (
          <g>
            <line x1={cx} y1={cy} x2={lx} y2={ly} stroke="var(--fg-dim)" strokeWidth="0.7" strokeDasharray="3,2" />
            <rect x={lx - 2} y={ly - 14} width={118} height={18} rx={3} fill="var(--bg-elev)" stroke="var(--line)" strokeWidth="0.7" />
            <text x={lx + 4} y={ly - 1} fill={WTONE.crit.fg} fontSize="10" fontWeight="700" fontFamily="Inter Tight">
              {highRisk.name} · {highRisk.avg}
            </text>
          </g>
        )
      })()}

      <g transform="translate(290, 370)">
        <circle cx="0" cy="0" r="4" fill={WTONE.safe.fg} />
        <text x="8" y="3" fill="var(--fg-dim)" fontSize="9" fontFamily="Inter Tight">Baixo</text>
        <circle cx="46" cy="0" r="4" fill={WTONE.warn.fg} />
        <text x="54" y="3" fill="var(--fg-dim)" fontSize="9" fontFamily="Inter Tight">Médio</text>
        <circle cx="96" cy="0" r="4" fill={WTONE.crit.fg} />
        <text x="104" y="3" fill="var(--fg-dim)" fontSize="9" fontFamily="Inter Tight">Alto</text>
      </g>
    </svg>
  )
}
