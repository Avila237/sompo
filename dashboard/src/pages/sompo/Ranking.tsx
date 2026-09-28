import { useState, useMemo } from 'react'
import { WTONE, scoreBandLabel, SEM_AVALIACAO } from '../../lib/risco'
import {
  loadEquipamentos,
  type EquipamentoView,
} from '../../data/api'
import { Card, Chip, ScoreBadge, SectionHeader, Button, ErroCarga, FilterSeg, Carregando } from '../../components/shared'
import { useCarga } from '../../lib/useCarga'
import { fmtDiaMes } from '../../lib/formato'
import { WIco } from '../../components/Icons'
import { ComingSoon } from '../../components/ComingSoon'

/* ── Sortable header helper ──────────────────────────────── */

type SortDir = 'asc' | 'desc'
type SortKey = 'id' | 'modelo' | 'tipo' | 'operador' | 'avaliacoes' | 'score' | 'ultimaTs'

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
        background: 'none', border: 'none', cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 4, padding: 0,
        fontWeight: 700, fontSize: 10, letterSpacing: 1,
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
  onPickEquip: (equipamentoId: string) => void
}) {
  const carga = useCarga((recarregar) => loadEquipamentos({ recarregar }))
  const views = useMemo<EquipamentoView[]>(() => carga.dados ?? [], [carga.dados])

  const [search, setSearch] = useState('')
  const [band, setBand] = useState('all')
  const [type, setType] = useState('all')
  const [sortKey, setSortKey] = useState<SortKey>('score')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const handleSort = (k: SortKey) => {
    if (k === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortKey(k); setSortDir('desc') }
  }

  const filtered = useMemo(() => {
    let list = [...views]

    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (e) =>
          e.id.toLowerCase().includes(q) ||
          e.modelo.toLowerCase().includes(q) ||
          e.tipo.toLowerCase().includes(q) ||
          e.operador.toLowerCase().includes(q),
      )
    }

    if (band === 'alto') list = list.filter((e) => e.faixa === 'crit')
    else if (band === 'medio') list = list.filter((e) => e.faixa === 'warn')
    else if (band === 'baixo') list = list.filter((e) => e.faixa === 'safe')

    if (type !== 'all') list = list.filter((e) => e.tipo === type)

    list.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'id': cmp = a.id.localeCompare(b.id); break
        case 'modelo': cmp = a.modelo.localeCompare(b.modelo); break
        case 'tipo': cmp = a.tipo.localeCompare(b.tipo); break
        case 'operador': cmp = a.operador.localeCompare(b.operador); break
        case 'avaliacoes': cmp = a.avaliacoes - b.avaliacoes; break
        // sem avaliação (-1) fica abaixo de qualquer score real, inclusive 0
        case 'score': cmp = (a.score ?? -1) - (b.score ?? -1); break
        case 'ultimaTs': cmp = a.ultimaTs.localeCompare(b.ultimaTs); break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })

    return list
  }, [views, search, band, type, sortKey, sortDir])

  const gridCols = '190px 1fr 90px 90px 70px 90px 70px 110px 30px'

  if (carga.carregando) return <Carregando msg="Carregando equipamentos da API…" />

  if (carga.erro) {
    return <ErroCarga titulo="Não foi possível carregar os equipamentos." msg={carga.erro} onTentar={carga.tentarDeNovo} />
  }

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader
        title="Equipamentos"
        sub={`${views.length} equipamentos cadastrados`}
        actions={
          <ComingSoon inline><Button kind="ghost" onClick={() => {}}>
            {WIco.download()} Exportar CSV
          </Button></ComingSoon>
        }
      />

      {/* ─── Filter bar ─── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px',
            border: '1px solid var(--line)', borderRadius: 6, background: 'var(--bg-elev)', minWidth: 240,
          }}
        >
          <span style={{ color: 'var(--fg-mute)', display: 'flex' }}>{WIco.search()}</span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar ID, modelo, tipo, operador…"
            style={{ background: 'none', border: 'none', outline: 'none', color: 'var(--fg)', fontSize: 13, width: '100%' }}
          />
        </div>

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

        <span style={{ fontSize: 12, color: 'var(--fg-mute)', fontWeight: 600, marginLeft: 'auto' }}>
          {filtered.length} resultado{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* ─── Table ─── */}
      <Card pad={0}>
        <div
          style={{
            display: 'grid', gridTemplateColumns: gridCols, padding: '10px 18px',
            borderBottom: '1px solid var(--line)', alignItems: 'center', gap: 8,
          }}
        >
          <Th label="ID" col="id" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Modelo" col="modelo" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Tipo" col="tipo" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Operador" col="operador" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Score" col="score" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Faixa" col="score" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Aval." col="avaliacoes" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <Th label="Última aval." col="ultimaTs" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
          <span />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {filtered.map((eq, i) => (
            <button
              key={eq.id}
              onClick={() => onPickEquip(eq.id)}
              style={{
                display: 'grid', gridTemplateColumns: gridCols, padding: '10px 18px',
                alignItems: 'center', gap: 8, background: 'none', border: 'none',
                borderTop: i > 0 ? '1px solid var(--line)' : 'none',
                cursor: 'pointer', width: '100%', textAlign: 'left', color: 'var(--fg)',
                transition: 'background 0.15s',
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--bg-elev-2)' }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = 'none' }}
            >
              {/* ID + IoT badge */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700 }}>{eq.id}</span>
                {eq.iot && <Chip state="info" label="IoT" size="sm" />}
              </div>

              {/* Model */}
              <div style={{ fontSize: 12, color: 'var(--fg-dim)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{eq.modelo}</div>

              {/* Type */}
              <div style={{ fontSize: 12, color: 'var(--fg-dim)', textTransform: 'capitalize' }}>{eq.tipo}</div>

              {/* Operator */}
              <div className="mono" style={{ fontSize: 12, color: 'var(--fg-dim)' }}>{eq.operador}</div>

              {/* Score */}
              <ScoreBadge score={eq.score} size="sm" />

              {/* Band chip */}
              <Chip state={eq.faixa} label={eq.score === null ? SEM_AVALIACAO : scoreBandLabel(eq.score)} size="sm" />

              {/* Aval count */}
              <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-dim)' }}>{eq.avaliacoes}</div>

              {/* Last eval date */}
              <div style={{ fontSize: 11, color: 'var(--fg-mute)', fontWeight: 500 }}>{fmtDiaMes(eq.ultimaTs)}</div>

              {/* Arrow */}
              <span style={{ color: 'var(--fg-mute)', display: 'flex', justifyContent: 'center' }}>
                {WIco.chev()}
              </span>
            </button>
          ))}

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