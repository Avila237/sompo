import { supabase } from '../lib/supabase'
import { scoreBand } from './mock'
import type { Equipment, Region, ToneKey } from '../types'

/* ── Tipos das linhas vindas do Supabase ──────────────────── */

export interface EquipamentoRow {
  equipamento_id: string
  tipo_equipamento: 'trator' | 'colheitadeira' | 'implemento'
  modelo_equipamento: string
  categoria_manual: string
  idade_equipamento: number
  historico_sinistros: number
  tem_iot: boolean
  intervalo_manut_recomendado_dias: number
  intervalo_manut_recomendado_horas: number
}

export interface AvaliacaoLite {
  avaliacao_id: number
  equipamento_id: string
  operador_id: string
  risco_score: number
  faixa_risco: string
  timestamp: string
  latitude: number
  longitude: number
}

export interface RawData {
  equipamentos: EquipamentoRow[]
  avaliacoes: AvaliacaoLite[]
}

/* ── Visao agregada por equipamento (uma linha por equip.) ── */

export interface EquipamentoView {
  id: string
  modelo: string
  tipo: 'trator' | 'colheitadeira' | 'implemento'
  idade: number
  sinistros: number
  iot: boolean
  score: number          // score da avaliacao mais recente (arredondado)
  scoreMedio: number     // media das avaliacoes do equipamento
  trend: number          // ultima avaliacao - penultima
  faixa: ToneKey         // 'safe' | 'warn' | 'crit'
  avaliacoes: number     // total de avaliacoes do equipamento
  operador: string       // operador da avaliacao mais recente
  ultimaTs: string       // timestamp da avaliacao mais recente
  lat: number
  lon: number
}

/* ── Fetch paginado (PostgREST limita ~1000 linhas/req) ───── */

const PAGE = 1000

async function fetchAvaliacoes(): Promise<AvaliacaoLite[]> {
  const cols =
    'avaliacao_id,equipamento_id,operador_id,risco_score,faixa_risco,timestamp,latitude,longitude'
  const all: AvaliacaoLite[] = []
  let from = 0
  for (;;) {
    const { data, error } = await supabase
      .from('avaliacoes')
      .select(cols)
      .order('avaliacao_id', { ascending: true })
      .range(from, from + PAGE - 1)
    if (error) throw error
    const rows = (data ?? []) as AvaliacaoLite[]
    for (const r of rows) {
      r.risco_score = Number(r.risco_score)
      r.latitude = Number(r.latitude)
      r.longitude = Number(r.longitude)
    }
    all.push(...rows)
    if (rows.length < PAGE) break
    from += PAGE
  }
  return all
}

async function fetchEquipamentos(): Promise<EquipamentoRow[]> {
  const { data, error } = await supabase
    .from('equipamentos')
    .select('*')
    .order('equipamento_id', { ascending: true })
  if (error) throw error
  return (data ?? []) as EquipamentoRow[]
}

/* ── Loader com cache de modulo (busca uma unica vez) ─────── */

let cache: Promise<RawData> | null = null

export function loadRawData(): Promise<RawData> {
  if (!cache) {
    cache = Promise.all([fetchEquipamentos(), fetchAvaliacoes()]).then(
      ([equipamentos, avaliacoes]) => ({ equipamentos, avaliacoes }),
    )
    cache.catch(() => {
      cache = null // permite nova tentativa apos falha
    })
  }
  return cache
}

/* ── Agregacao: uma EquipamentoView por equipamento ───────── */

export function buildEquipamentos(data: RawData): EquipamentoView[] {
  const porEquip = new Map<string, AvaliacaoLite[]>()
  for (const a of data.avaliacoes) {
    const list = porEquip.get(a.equipamento_id)
    if (list) list.push(a)
    else porEquip.set(a.equipamento_id, [a])
  }

  return data.equipamentos.map((eq) => {
    const avals = (porEquip.get(eq.equipamento_id) ?? []).slice().sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
    )
    const latest = avals[0]
    const prev = avals[1]
    const soma = avals.reduce((s, a) => s + a.risco_score, 0)
    const scoreMedio = avals.length ? soma / avals.length : 0
    const score = latest ? latest.risco_score : 0
    const trend =
      latest && prev ? Math.round(latest.risco_score - prev.risco_score) : 0

    return {
      id: eq.equipamento_id,
      modelo: eq.modelo_equipamento,
      tipo: eq.tipo_equipamento,
      idade: eq.idade_equipamento,
      sinistros: eq.historico_sinistros,
      iot: eq.tem_iot,
      score: Math.round(score),
      scoreMedio: Math.round(scoreMedio),
      trend,
      faixa: scoreBand(score),
      avaliacoes: avals.length,
      operador: latest ? latest.operador_id : '—',
      ultimaTs: latest ? latest.timestamp : '',
      lat: latest ? latest.latitude : 0,
      lon: latest ? latest.longitude : 0,
    }
  })
}

/* ── KPIs da Visao geral ──────────────────────────────────── */

export interface Kpis {
  totalEquip: number
  totalAval: number
  scoreMedio: number
  riscoAlto: number
  pctRiscoAlto: number
}

export function computeKpis(data: RawData, views: EquipamentoView[]): Kpis {
  const totalAval = data.avaliacoes.length
  const soma = data.avaliacoes.reduce((s, a) => s + a.risco_score, 0)
  const scoreMedio = totalAval ? soma / totalAval : 0
  const riscoAlto = views.filter((v) => v.faixa === 'crit').length
  const totalEquip = views.length
  return {
    totalEquip,
    totalAval,
    scoreMedio: Math.round(scoreMedio),
    riscoAlto,
    pctRiscoAlto: totalEquip ? (riscoAlto / totalEquip) * 100 : 0,
  }
}

/* ── Tendencia: media diaria nos ultimos N dias do dataset ── */

export function buildTrend(data: RawData, days: number): number[] {
  if (data.avaliacoes.length === 0) return []
  let maxTs = 0
  for (const a of data.avaliacoes) {
    const t = new Date(a.timestamp).getTime()
    if (t > maxTs) maxTs = t
  }
  const start = maxTs - days * 86400000
  const porDia = new Map<string, { soma: number; n: number }>()
  for (const a of data.avaliacoes) {
    const t = new Date(a.timestamp).getTime()
    if (t < start) continue
    const dia = a.timestamp.slice(0, 10)
    const acc = porDia.get(dia)
    if (acc) {
      acc.soma += a.risco_score
      acc.n++
    } else {
      porDia.set(dia, { soma: a.risco_score, n: 1 })
    }
  }
  return [...porDia.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([, v]) => v.soma / v.n)
}

/* ── Distribuicao geografica a partir de lat/long reais ───── */

const LAT_MIN = -33.75
const LAT_MAX = -2.5
const LON_MIN = -73.99
const LON_MAX = -34.79

function clamp01(v: number): number {
  return Math.max(0.04, Math.min(0.96, v))
}

export function buildRegions(views: EquipamentoView[]): Region[] {
  const cells = new Map<string, { soma: number; n: number; lat: number; lon: number }>()
  for (const v of views) {
    if (!v.ultimaTs) continue
    const rlat = Math.round(v.lat / 3) * 3
    const rlon = Math.round(v.lon / 3) * 3
    const key = `${rlat},${rlon}`
    const c = cells.get(key)
    if (c) {
      c.soma += v.score
      c.n++
    } else {
      cells.set(key, { soma: v.score, n: 1, lat: rlat, lon: rlon })
    }
  }
  return [...cells.values()]
    .map((c) => ({
      name: `${Math.abs(c.lat).toFixed(0)}°S ${Math.abs(c.lon).toFixed(0)}°O`,
      x: clamp01((c.lon - LON_MIN) / (LON_MAX - LON_MIN)),
      y: clamp01((LAT_MAX - c.lat) / (LAT_MAX - LAT_MIN)),
      count: c.n,
      avg: Math.round(c.soma / c.n),
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 14)
}

/* ── Alertas: avaliacoes recentes de maior risco ──────────── */

export interface Alerta {
  sev: ToneKey
  msg: string
  time: string
}

export function buildAlertas(data: RawData, limit = 7): Alerta[] {
  return data.avaliacoes
    .slice()
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .filter((a) => a.faixa_risco !== 'baixo')
    .slice(0, limit)
    .map((a) => {
      const d = new Date(a.timestamp)
      const hh = String(d.getHours()).padStart(2, '0')
      const mm = String(d.getMinutes()).padStart(2, '0')
      return {
        sev: scoreBand(a.risco_score),
        msg: `${a.equipamento_id} · score ${Math.round(a.risco_score)} · risco ${a.faixa_risco}`,
        time: `${hh}:${mm}`,
      }
    })
}

/* ── Adapta EquipamentoView ao tipo Equipment (tela Detalhe) ─ */

export function toEquipment(v: EquipamentoView): Equipment {
  return {
    id: v.id,
    model: v.modelo,
    type: v.tipo,
    op: v.operador,
    opName: v.operador,
    client: '—',
    region: v.ultimaTs ? `${Math.abs(v.lat).toFixed(1)}°S ${Math.abs(v.lon).toFixed(1)}°O` : '—',
    score: v.score,
    trend: v.trend,
    lastAlert: v.ultimaTs ? new Date(v.ultimaTs).toLocaleDateString('pt-BR') : '—',
    hours: 0,
    maint: 'em dia',
    maintPct: 0,
  }
}