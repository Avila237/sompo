import { useState, useMemo } from 'react'
import { EQUIPMENT, WTONE, scoreBand, scoreBandLabel } from '../../data/mock'
import type { Equipment } from '../../types'
import { Card, Chip, ScoreBadge, Trend, SectionHeader, Button } from '../../components/shared'
import { WIco } from '../../components/Icons'

/* ── FilterSeg helper ────────────────────────────────────── */

function FilterSeg({
  value,
  onChange,
  opts,
}: {
  value: string
  onChange: (v: string) => void
  opts: Array<{ k: string; l: string; dot?: string }>
}) {
  return (
    <div style={{ display: 'inline-flex', border: '1px solid var(--line)', borderRadius: 6, overflow: 'hidden' }}>
      {opts.map((o) => {
        const active = value === o.k
        return (
          <button
            key={o.k}
            onClick={() => onChange(o.k)}
            style={{
              padding: '6px 12px',
              border: 'none',
              borderRight: '1px solid var(--line)',
              background: active ? 'var(--line)' : 'transparent',
              color: active ? 'var(--fg)' : 'var(--fg-mute)',
              fontWeight: 600,
              fontSize: 12,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {o.dot && (
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: o.dot,
                  flexShrink: 0,
                }}
              />
            )}
            {o.l}
          </button>
        )
      })}
    </div>
  )
}

/* ── Sortable table header helper ────────────────────────── */

type SortDir = 'asc' | 'desc'
type SortKey = 'id' | 'model' | 'opName' | 'client' | 'region' | 'score' | 'trend' | 'lastAlert'

function Th({
  label,
  col,
  sortKey,
  sortDir,
  onSort,
  style = {},
}: {
  label: string
  col: SortKey
  sortKey: SortKey
  sortDir: SortDir
  onSort: (k: SortKey) => void
  style?: React.CSSProperties
}) {
  const active = sortKey === col
  return (
    <button
      onClick={() => onSort(col)}
      style={{
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: 0,
        fontWeight: 700,
        fontSize: 10,
        letterSpacing: 1,
        textTransform: 'uppercase' as const,
        color: active ? 'var(--fg)' : 'var(--fg-mute)',
        whiteSpace: 'nowrap' as const,
        ...style,
      }}
    >
      {label}
      <span style={{ fontSize: 8, opacity: active ? 1 : 0.3 }}>
        {active && sortDir === 'asc' ? '▲' : '▼'}
      </span>
    </button>
  )
}

/* ── Main component ──────────────────────────────────────── */

export default function SompoRanking({
  onPickEquip,
}: {
  onPickEquip: (e: Equipment) => void
}) {
  const [search, setSearch] = useState('')
  const [exportState, setExportState] = useState<null | 'working' | 'done'>(null)
  const [band, setBand] = useState('all')
  const [type, setType] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const handleSort = (k: SortKey) => {
    if (k === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(k)
      setSortDir('desc')
    }
  }

  const filtered = useMemo(() => {
    let list = [...EQUIPMENT]

    // search
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (e) =>
          e.id.toLowerCase().includes(q) ||
          e.model.toLowerCase().includes(q) ||
          e.opName.toLowerCase().includes(q) ||
          e.client.toLowerCase().includes(q) ||
          e.region.toLowerCase().includes(q),
      )
    }

    // risk band
    if (band === 'alto') list = list.filter((e) => scoreBand(e.score) === 'crit')
    else if (band === 'medio') list = list.filter((e) => scoreBand(e.score) === 'warn')
    else if (band === 'baixo') list = list.filter((e) => scoreBand(e.score) === 'safe')

    // type
    if (type !== 'all') list = list.filter((e) => e.type === type)

    // sort
    list.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'id': cmp = a.id.localeCompare(b.id); break
        case 'model': cmp = a.model.localeCompare(b.model); break
        case 'opName': cmp = a.opName.localeCompare(b.opName); break
        case 'client': cmp = a.client.localeCompare(b.client); break
        case 'region': cmp = a.region.localeCompare(b.region); break
        case 'score': cmp = a.score - b.score; break
        case 'trend': cmp = a.trend - b.trend; break
        case 'lastAlert': cmp = a.lastAlert.localeCompare(b.lastAlert); break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })

    return list
  }, [search, band, type, sortKey, sortDir])

  const gridCols = '180px 1.6fr 1fr 1.3fr 70px 90px 90px 110px 30px'

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* ─── Header ─── */}
      <SectionHeader
        title="Ranking de risco"
        sub={`${EQUIPMENT.length} equipamentos cadastrados`}
        actions={
          <Button kind="ghost" onClick={() => {}}>
            {WIco.download()} Exportar CSV
          </Button>
        }
      />

      {/* ─── Filter bar ─── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        {/* search input */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '7px 12px',
            border: '1px solid var(--line)',
            borderRadius: 6,
            background: 'var(--bg-elev)',
            minWidth: 220,
          }}
        >
          <span style={{ color: 'var(--fg-mute)', display: 'flex' }}>{WIco.search()}</span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar ID, modelo, operador…"
            style={{
              background: 'none',
              border: 'none',
              outline: 'none',
              color: 'var(--fg)',
              fontSize: 13,
              width: '100%',
            }}
          />
        </div>

        {/* risk band filter */}
        <FilterSeg
          value={band}
          onChange={setBand}
          opts={[
            { k: 'all', l: 'Todos' },
            { k: 'alto', l: 'Alto', dot: WTONE.crit.fg },
            { k: 'medio', l: 'Médio', dot: WTONE.warn.fg },
            { k: 'baixo', l: 'Baixo', dot: WTONE.safe.fg },
          ]}
        />

        {/* type filter */}
        <FilterSeg
          value={type}
          onChange={setType}
          opts={[
            { k: 'all', l: 'Todos tipos' },
            { k: 'colheitadeira', l: 'Colheitadeira' },
            { k: 'trator', l: 'Trator' },
            { k: 'implemento', l: 'Implemento' },
          ]}
        />

        {/* result count */}
        <span style={{ fontSize: 12, color: 'var(--fg-mute)', fontWeight: 600, marginLeft: 'auto' }}>
          {filtered.length} resultado{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* ─── Table ─── */}
      <Card pad={0}>
        {/* header row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: gridCols,
            padding: '10px 18px',
            borderBottom: '1px solid var(--line)',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Th label="ID · Modelo" col="id" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Operador" col="opName" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Cliente" col="client" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Região" col="region" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Score" col="score" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Faixa" col="score" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Tendência" col="trend" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Último alerta" col="lastAlert" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <span />
        </div>

        {/* data rows */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {filtered.map((eq, i) => {
            const bandKey = scoreBand(eq.score)
            return (
              <button
                key={eq.id}
                onClick={() => onPickEquip(eq)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: gridCols,
                  padding: '10px 18px',
                  alignItems: 'center',
                  gap: 8,
                  background: 'none',
                  border: 'none',
                  borderTop: i > 0 ? '1px solid var(--line)' : 'none',
                  cursor: 'pointer',
                  width: '100%',
                  textAlign: 'left',
                  color: 'var(--fg)',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={(e) => {
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-elev-2)'
                }}
                onMouseLeave={(e) => {
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'none'
                }}
              >
                {/* ID + Model */}
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{eq.id}</div>
                  <div style={{ fontSize: 11, color: 'var(--fg-dim)', marginTop: 1 }}>{eq.model}</div>
                </div>

                {/* Operator */}
                <div style={{ fontSize: 12, fontWeight: 500 }}>{eq.opName}</div>

                {/* Client */}
                <div style={{ fontSize: 12, color: 'var(--fg-dim)' }}>{eq.client}</div>

                {/* Region */}
                <div style={{ fontSize: 12, color: 'var(--fg-dim)' }}>{eq.region}</div>

                {/* Score */}
                <ScoreBadge score={eq.score} size="sm" />

                {/* Band chip */}
                <Chip state={bandKey} label={scoreBandLabel(eq.score)} size="sm" />

                {/* Trend */}
                <Trend delta={eq.trend} />

                {/* Last alert */}
                <div style={{ fontSize: 11, color: 'var(--fg-mute)', fontWeight: 500 }}>{eq.lastAlert}</div>

                {/* Arrow */}
                <span style={{ color: 'var(--fg-mute)', display: 'flex', justifyContent: 'center' }}>
                  {WIco.chev()}
                </span>
              </button>
            )
          })}

          {filtered.length === 0 && (
            <div style={{ padding: '32px 18px', textAlign: 'center', color: 'var(--fg-mute)', fontSize: 13 }}>
              Nenhum equipamento encontrado.
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}